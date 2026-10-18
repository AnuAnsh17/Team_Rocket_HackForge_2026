/**
 * Console API access.
 *
 * The console talks to the backend and to nothing else: it holds no database URL, no
 * service-role key and no extraction credential. Everything it can see and do is
 * whatever the backend returns for the current actor.
 *
 * Demo mode is a development affordance, available only when no Supabase project is
 * configured. See `src/lib/supabase/config.ts`.
 *
 * TWO IDENTITY PATHS, IN PRIORITY ORDER
 *
 * 1. Supabase (the real path). A session cookie set by `@supabase/ssr` is exchanged for an
 *    access token, and that token is attached as `Authorization: Bearer <token>` on every
 *    request. The token is read per request through `readAccessToken`, so a refreshed or
 *    changed session is picked up without rebuilding the client. The token is never
 *    stored, decoded or asserted here: the backend is the only verifier.
 *
 * 2. Demo mode. It identifies an actor by id through the `X-Demo-Actor-Id` header, and is
 *    available ONLY when no Supabase project is configured and `NEXT_PUBLIC_DEMO_MODE=true`.
 *    When a project IS configured the demo header is not sent at all - not as a fallback,
 *    not on error.
 *
 * Demo mode is deliberately NOT a role selector: the backend resolves that actor's roles,
 * permissions and scope from its own database, so choosing a different id in the UI cannot
 * grant a capability the database has not granted.
 */

import { createApiClient, type ApiClientOptions } from "@proofline/api-client";

import { CONSOLE_AUTH } from "@/lib/supabase/config";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Re-exported so callers keep importing the one module they always have.
export { CONSOLE_AUTH, SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/config";

/** Whether a Supabase project is configured for this build. When true, it is the only way in. */
export const SUPABASE_CONFIGURED = CONSOLE_AUTH.supabaseConfigured;

/**
 * Whether the demo identity switcher may be offered at all.
 *
 * A UI convenience, never a boundary. When the backend has demo mode disabled it does not
 * register the demo routes at all, and the demo auth provider is not constructed, so a
 * build with this flag set against a non-demo backend simply receives 401/404 - it cannot
 * grant anything.
 */
export const DEMO_MODE_ENABLED = CONSOLE_AUTH.demoModeEnabled;

/**
 * Whether the demo identity path is actually usable.
 *
 * False whenever a Supabase project is configured: an operator who has set up real
 * authentication must not be able to fall back to a header the backend no longer honours.
 */
export const DEMO_MODE_ACTIVE = CONSOLE_AUTH.demoModeActive;

export const DEMO_ACTOR_STORAGE_KEY = "proofline.console.demoActorId";

/** Read the currently selected demo actor id, if any. */
export function readDemoActorId(
  active: boolean = DEMO_MODE_ACTIVE,
  storage: Pick<Storage, "getItem"> | null = demoStorage(),
): string | null {
  if (!active || !storage) return null;
  return storage.getItem(DEMO_ACTOR_STORAGE_KEY);
}

/** Select a demo actor id. Reloads so server components re-read the value. */
export function writeDemoActorId(actorId: string | null): void {
  if (typeof window === "undefined") return;
  if (actorId) {
    window.localStorage.setItem(DEMO_ACTOR_STORAGE_KEY, actorId);
  } else {
    window.localStorage.removeItem(DEMO_ACTOR_STORAGE_KEY);
  }
  window.location.reload();
}

function demoStorage(): Pick<Storage, "getItem"> | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    // A browser with storage disabled must not break the whole console.
    return null;
  }
}

// ---------------------------------------------------------------------------
// Access-token seam
//
// The Supabase browser client registers a provider here when it is imported. Keeping the
// seam a registered function - rather than an imported Supabase client - means this module
// stays free of the SDK, so it loads in a plain Node test and cannot smuggle a credential
// into a place that only meant to read a URL.
// ---------------------------------------------------------------------------

export type AccessTokenProvider = () => Promise<string | null | undefined>;

let accessTokenProvider: AccessTokenProvider | null = null;

/**
 * Register the function that supplies the current Supabase access token.
 *
 * Called once, at import, by `src/lib/supabase/client.ts`. The provider reads the session
 * per request; it is never cached here, so a refresh or a sign-out is reflected immediately
 * and one account's token is never reused for another.
 */
export function setAccessTokenProvider(provider: AccessTokenProvider | null): void {
  accessTokenProvider = provider;
}

/** The current bearer token, or null when there is no usable session. */
export async function readAccessToken(): Promise<string | null> {
  if (!accessTokenProvider) return null;
  const token = await accessTokenProvider();
  return typeof token === "string" && token.length > 0 ? token : null;
}

// ---------------------------------------------------------------------------
// Unauthorized (401) handling
//
// A 401 means there is no valid identity. The console returns to sign-in and does NOT
// retry: retrying with the same (absent or expired) credential only multiplies the
// failure. A 403 is deliberately NOT handled here - the identity is valid but lacks
// authority, so navigating to sign-in would be wrong and hiding the refusal would be
// worse. 403s are rendered as a forbidden state where they occur.
// ---------------------------------------------------------------------------

export type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

/** Notify the registered handler that a request was refused as unauthenticated. */
export function notifyUnauthorized(): void {
  const handler = unauthorizedHandler;
  if (!handler) return;
  try {
    handler();
  } catch {
    // A failing handler must not turn one 401 into an unhandled rejection.
  }
}

/**
 * `fetch` used by the console client: it reports a 401 so the session can be reset.
 *
 * Only the status is inspected; the body is passed through untouched, so nothing about a
 * response is rewritten on the way to the caller.
 */
export const consoleFetch: typeof globalThis.fetch = async (input, init) => {
  const response = await globalThis.fetch(input, init);
  if (response.status === 401) notifyUnauthorized();
  return response;
};

/**
 * Headers for an authorized request that is not made through the typed client.
 *
 * The receipt-content endpoint streams a binary the generated client has no response type
 * for, so it is called with `fetch` directly. That must not become a second, quietly
 * different identity path: this uses the same token seam and the same demo gate, so
 * "bearer when Supabase is configured, demo header otherwise" holds for every request the
 * console makes.
 */
export async function consoleAuthHeaders(): Promise<Headers> {
  const headers = new Headers();
  const token = await readAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const demoActorId = readDemoActorId();
  if (demoActorId) headers.set("X-Demo-Actor-Id", demoActorId);
  return headers;
}

export function consoleApiOptions(
  overrides: Partial<ApiClientOptions> = {},
): ApiClientOptions {
  return {
    // OpenAPI paths already include /api/v1, so openapi-fetch needs only the origin.
    baseUrl: API_BASE_URL.replace(/\/api\/v1\/?$/, ""),
    // The demo header is suppressed whenever Supabase is configured: `readDemoActorId`
    // returns null unless demo mode is the active path.
    getDemoActorId: () => readDemoActorId(),
    // The real identity: the current Supabase access token, awaited per request.
    getToken: () => readAccessToken(),
    // A 401 on any console request sends the session back to sign-in.
    fetch: consoleFetch,
    ...overrides,
  };
}

export function createConsoleApi(overrides: Partial<ApiClientOptions> = {}) {
  return createApiClient(consoleApiOptions(overrides));
}

/** Shape of a value the console derives from the backend rather than hard-coding. */
export interface UnavailableValue {
  unavailable: true;
  reason: string;
}

export function unavailable(reason: string): UnavailableValue {
  return { unavailable: true, reason };
}

export function isUnavailable(value: unknown): value is UnavailableValue {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as UnavailableValue).unavailable === true
  );
}
