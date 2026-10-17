/**
 * Console API access.
 *
 * The console talks to the backend and to nothing else: it holds no database URL, no
 * service-role key and no extraction credential. Everything it can see and do is
 * whatever the backend returns for the current actor.
 *
 * Demo mode identifies an actor by id. It is deliberately NOT a role selector: the
 * backend resolves that actor's roles, permissions and scope from its own database, so
 * choosing a different id in the UI cannot grant a capability the database has not
 * granted.
 */

import { createApiClient, type ApiClientOptions } from "@proofline/api-client";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/**
 * Whether the demo identity switcher may be offered at all.
 *
 * This flag is a UI convenience, never a boundary. When the backend has demo mode
 * disabled it does not register the demo routes at all, and the demo auth provider is
 * not constructed, so a build with this flag set against a non-demo backend simply
 * receives 401/404 - it cannot grant anything.
 */
export const DEMO_MODE_ENABLED = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const DEMO_ACTOR_STORAGE_KEY = "proofline.console.demoActorId";

/** Read the currently selected demo actor id, if any. */
export function readDemoActorId(): string | null {
  if (!DEMO_MODE_ENABLED || typeof window === "undefined") return null;
  return window.localStorage.getItem(DEMO_ACTOR_STORAGE_KEY);
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

export function consoleApiOptions(
  overrides: Partial<ApiClientOptions> = {},
): ApiClientOptions {
  return {
    baseUrl: API_BASE_URL,
    getDemoActorId: readDemoActorId,
    // A token provider is wired here rather than in each page, so replacing demo mode
    // with real authentication is a change to this one function.
    getToken: () => null,
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
