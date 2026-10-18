/**
 * Session rules and navigation decisions, exercised as pure functions.
 *
 * These are the rules that decide whether a token is sent and whether a request may reach
 * the console, so they are tested directly rather than through a browser.
 */

import { describe, expect, it } from "vitest";

import {
  EXPIRY_SKEW_SECONDS,
  LOGIN_PATH,
  accessTokenFromSession,
  decideNavigation,
  identityKeyFromMembership,
  identityKeyFromSession,
  isSessionExpired,
  safeNextPath,
} from "../src/lib/auth/session";

const NOW = 1_700_000_000;

function session(overrides: Record<string, unknown> = {}) {
  return {
    access_token: "header.payload.signature",
    expires_at: NOW + 3600,
    user: { id: "user-a", email: "a@example.com" },
    ...overrides,
  };
}

describe("accessTokenFromSession", () => {
  it("returns the token of a current session", () => {
    expect(accessTokenFromSession(session(), NOW)).toBe("header.payload.signature");
  });

  it("returns null for an absent session", () => {
    expect(accessTokenFromSession(null, NOW)).toBeNull();
    expect(accessTokenFromSession(undefined, NOW)).toBeNull();
  });

  it("returns null for an expired session rather than sending a dead credential", () => {
    expect(accessTokenFromSession(session({ expires_at: NOW - 1 }), NOW)).toBeNull();
    // Within the skew window counts as expired, so a token about to die is not sent.
    expect(
      accessTokenFromSession(session({ expires_at: NOW + EXPIRY_SKEW_SECONDS }), NOW),
    ).toBeNull();
    expect(
      accessTokenFromSession(session({ expires_at: NOW + EXPIRY_SKEW_SECONDS + 1 }), NOW),
    ).not.toBeNull();
  });

  it("returns null when the token is missing or empty", () => {
    expect(accessTokenFromSession(session({ access_token: "" }), NOW)).toBeNull();
    expect(accessTokenFromSession(session({ access_token: "   " }), NOW)).toBeNull();
    expect(accessTokenFromSession(session({ access_token: null }), NOW)).toBeNull();
  });

  it("treats a session with no expiry as usable", () => {
    // Supabase always sets `expires_at`; if it were ever absent, refusing every request
    // would be worse than sending a token the backend will verify anyway.
    expect(accessTokenFromSession(session({ expires_at: null }), NOW)).toBe(
      "header.payload.signature",
    );
  });
});

describe("isSessionExpired", () => {
  it("treats a missing session as expired", () => {
    expect(isSessionExpired(null, NOW)).toBe(true);
  });
});

describe("identity keys", () => {
  it("keys an authenticated session by user id", () => {
    expect(identityKeyFromSession(session())).toBe("user-a");
  });

  it("keys an anonymous or token-less session as anonymous", () => {
    expect(identityKeyFromSession(null)).toBe("anonymous");
    expect(identityKeyFromSession({ user: {} })).toBe("anonymous");
  });

  it("uses the server's own identifiers for a resolved membership", () => {
    const key = identityKeyFromMembership({
      id: "membership-1",
      organization_id: "org-1",
      user: { id: "user-1" },
    });
    expect(key).toBe("org-1:membership-1:user-1");
  });

  it("changes when the account changes, so a subtree is remounted", () => {
    const first = identityKeyFromMembership({ id: "m1", organization_id: "org1", user: { id: "u1" } });
    const second = identityKeyFromMembership({ id: "m2", organization_id: "org1", user: { id: "u2" } });
    expect(first).not.toBe(second);
  });

  it("has a defined key before an identity is resolved", () => {
    expect(identityKeyFromMembership(null)).toBe("unresolved");
  });
});

describe("decideNavigation", () => {
  it("allows everything when no project is configured", () => {
    for (const pathname of ["/", "/review", LOGIN_PATH]) {
      expect(decideNavigation({ configured: false, hasUser: false, pathname })).toEqual({
        action: "allow",
      });
    }
  });

  it("sends an unauthenticated visitor to the sign-in route", () => {
    const decision = decideNavigation({ configured: true, hasUser: false, pathname: "/review" });
    expect(decision).toEqual({ action: "redirect", to: LOGIN_PATH, next: "/review" });
  });

  it("lets an unauthenticated visitor see the sign-in route", () => {
    expect(
      decideNavigation({ configured: true, hasUser: false, pathname: LOGIN_PATH }),
    ).toEqual({ action: "allow" });
  });

  it("moves an authenticated visitor off the sign-in route", () => {
    expect(
      decideNavigation({ configured: true, hasUser: true, pathname: LOGIN_PATH }),
    ).toEqual({ action: "redirect", to: "/", next: null });
  });

  it("allows an authenticated visitor into the console", () => {
    expect(
      decideNavigation({ configured: true, hasUser: true, pathname: "/" }),
    ).toEqual({ action: "allow" });
  });
});

describe("safeNextPath", () => {
  it("accepts a same-origin path", () => {
    expect(safeNextPath("/review/abc")).toBe("/review/abc");
  });

  it("refuses an open redirect", () => {
    // A protocol-relative or absolute URL would turn the sign-in redirect into an open one.
    expect(safeNextPath("//evil.example.com")).toBe("/");
    expect(safeNextPath("https://evil.example.com")).toBe("/");
    expect(safeNextPath("javascript:alert(1)")).toBe("/");
  });

  it("defaults to the console root, and never back to sign-in", () => {
    expect(safeNextPath(null)).toBe("/");
    expect(safeNextPath("")).toBe("/");
    expect(safeNextPath(LOGIN_PATH)).toBe("/");
  });
});
