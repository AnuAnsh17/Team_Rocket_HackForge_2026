/**
 * Session and navigation decisions, as pure functions.
 *
 * Nothing here imports Next, React or Supabase, so every rule that decides "may this
 * request see the console?" and "is this token still usable?" can be tested directly,
 * without a running server and without a live identity provider. The middleware and the
 * client components are thin wrappers over these functions.
 */

/** The route an unauthenticated visitor is sent to. */
export const LOGIN_PATH = "/login";

/**
 * The subset of a Supabase session this module reasons about.
 *
 * Structural rather than the SDK type, so a test can supply a literal and so the module
 * does not depend on the SDK being present.
 */
export interface SessionLike {
  access_token?: string | null;
  expires_at?: number | null;
  user?: { id?: string | null; email?: string | null } | null;
}

/**
 * Clock skew allowed when deciding a token is still current.
 *
 * Small on purpose. A generous allowance is an extended token lifetime under another
 * name, and the backend would reject the token anyway.
 */
export const EXPIRY_SKEW_SECONDS = 5;

export function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

/** Whether a session's access token is at or past its expiry. */
export function isSessionExpired(
  session: SessionLike | null | undefined,
  now: number = nowSeconds(),
): boolean {
  if (!session) return true;
  const expiresAt = session.expires_at;
  if (typeof expiresAt !== "number" || !Number.isFinite(expiresAt)) return false;
  return expiresAt <= now + EXPIRY_SKEW_SECONDS;
}

/**
 * The bearer token to send for a session, or null.
 *
 * Returns null for an absent session, an empty token, or a token that has already
 * expired. An expired token must not be sent: the backend would reject it, and sending a
 * credential that cannot work turns "please sign in again" into an opaque server error.
 * Supabase refreshes a session before `getSession()` returns it, so an expired value
 * reaching here means the refresh did not happen and signing in again is the real fix.
 */
export function accessTokenFromSession(
  session: SessionLike | null | undefined,
  now: number = nowSeconds(),
): string | null {
  if (!session) return null;
  const token = session.access_token;
  if (typeof token !== "string" || token.trim().length === 0) return null;
  if (isSessionExpired(session, now)) return null;
  return token;
}

/**
 * A stable key for the signed-in identity.
 *
 * Used to key the console's content so a different account cannot inherit the previous
 * account's rendered state: when this value changes, React unmounts the subtree and any
 * cached query results go with it.
 */
export function identityKeyFromSession(session: SessionLike | null | undefined): string {
  const id = session?.user?.id;
  return typeof id === "string" && id.length > 0 ? id : "anonymous";
}

/** The backend-resolved identity, as far as keying is concerned. */
export interface BackendIdentityLike {
  id?: string | null;
  organization_id?: string | null;
  user?: { id?: string | null } | null;
}

/**
 * A stable key for the backend-resolved identity.
 *
 * Prefers the server's own identifiers (organization + membership + user) over anything
 * the client believes, because the backend is what actually decides who the caller is.
 */
export function identityKeyFromMembership(
  membership: BackendIdentityLike | null | undefined,
): string {
  if (!membership) return "unresolved";
  const organization = membership.organization_id ?? "no-org";
  const membershipId = membership.id ?? "no-membership";
  const userId = membership.user?.id ?? "no-user";
  return `${organization}:${membershipId}:${userId}`;
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export type NavigationDecision =
  | { action: "allow" }
  /** Send the request to `to`, optionally remembering where the visitor was headed. */
  | { action: "redirect"; to: string; next: string | null };

/**
 * Decide whether a request may proceed.
 *
 * When no Supabase project is configured the console is not gated at all: local demo
 * development must not be forced through a sign-in screen that cannot be completed. When
 * a project *is* configured the gate is absolute - an unauthenticated visitor sees only
 * the sign-in route, and an authenticated visitor is moved off it.
 */
export function decideNavigation(input: {
  configured: boolean;
  hasUser: boolean;
  pathname: string;
}): NavigationDecision {
  if (!input.configured) return { action: "allow" };
  if (!input.hasUser) {
    if (input.pathname === LOGIN_PATH) return { action: "allow" };
    return { action: "redirect", to: LOGIN_PATH, next: input.pathname };
  }
  if (input.pathname === LOGIN_PATH) {
    return { action: "redirect", to: "/", next: null };
  }
  return { action: "allow" };
}

/** The post-sign-in destination, from a `next` query parameter, validated. */
export function safeNextPath(candidate: string | null | undefined): string {
  if (!candidate) return "/";
  // Only same-origin absolute paths. A protocol-relative or absolute URL would turn the
  // sign-in redirect into an open redirect.
  if (!candidate.startsWith("/") || candidate.startsWith("//")) return "/";
  if (candidate.startsWith(LOGIN_PATH)) return "/";
  return candidate;
}
