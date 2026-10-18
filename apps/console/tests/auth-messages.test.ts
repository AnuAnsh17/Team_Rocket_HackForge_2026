/**
 * Sign-in error mapping and redaction.
 *
 * Two properties are asserted: a person gets actionable wording, and no token or password
 * can reach the screen - even when the provider's own error message contains one.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { describeSignInFailure, mapSignInError, redactSensitive } from "../src/lib/auth/messages";

/** A well-formed-looking JWT, used here only as a value that must never survive. */
const FAKE_JWT =
  "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJlLXNlZ21lbnQ";
const FAKE_PASSWORD = "correct-horse-battery-staple";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("redactSensitive", () => {
  it("removes a JWT", () => {
    const output = redactSensitive(`token ${FAKE_JWT} rejected`);
    expect(output).not.toContain(FAKE_JWT);
    expect(output).toContain("[redacted]");
  });

  it("removes a bearer credential", () => {
    expect(redactSensitive(`Authorization: Bearer ${FAKE_JWT}`)).not.toContain(FAKE_JWT);
  });

  it("removes a keyed secret value", () => {
    const output = redactSensitive(`access_token=${FAKE_JWT} refresh_token=abc123`);
    expect(output).not.toContain(FAKE_JWT);
    expect(output).not.toContain("abc123");
  });

  it("leaves ordinary text alone", () => {
    expect(redactSensitive("Invalid login credentials")).toBe("Invalid login credentials");
  });
});

describe("mapSignInError", () => {
  it("maps a rejected password without echoing the provider message", () => {
    const message = mapSignInError({ status: 400, message: "Invalid login credentials" });
    expect(message).toMatch(/email address and password combination was not accepted/i);
    expect(message).not.toMatch(/invalid login credentials/i);
  });

  it("maps an unconfirmed email", () => {
    expect(mapSignInError({ message: "Email not confirmed" })).toMatch(/not been confirmed/i);
  });

  it("maps a rate limit", () => {
    expect(mapSignInError({ status: 429, message: "Too Many Requests" })).toMatch(
      /Too many sign-in attempts/i,
    );
  });

  it("maps a network failure, including a thrown fetch error", () => {
    expect(mapSignInError(new TypeError("fetch failed"))).toMatch(/could not be reached/i);
    expect(mapSignInError({ name: "AuthRetryableFetchError" })).toMatch(/could not be reached/i);
  });

  it("maps a weak-password refusal", () => {
    expect(mapSignInError({ message: "Password should be at least 6 characters" })).toMatch(
      /minimum length/i,
    );
  });

  it("maps an unknown failure to a generic sentence", () => {
    expect(mapSignInError(new Error("something unexpected"))).toMatch(/Sign-in failed/i);
  });

  it("never returns a credential, even when the provider's message carries one", () => {
    const leaky = {
      status: 401,
      message: `Invalid login credentials for password ${FAKE_PASSWORD} (token ${FAKE_JWT})`,
    };
    const message = mapSignInError(leaky);
    // The password VALUE and the token are what must never survive; the word "password" is
    // ordinary product copy.
    expect(message).not.toContain(FAKE_PASSWORD);
    expect(message).not.toContain(FAKE_JWT);
    expect(message).not.toContain("Invalid login credentials");
  });
});

describe("describeSignInFailure", () => {
  it("returns only a status/code/name triple, with the token inside the code redacted", () => {
    const described = describeSignInFailure({
      status: 400,
      code: `bad-${FAKE_JWT}`,
      name: "AuthApiError",
      message: `password ${FAKE_PASSWORD}`,
    });
    expect(described).toBe("status=400 code=bad-[redacted] name=AuthApiError");
    expect(described).not.toContain(FAKE_PASSWORD);
    expect(described).not.toContain(FAKE_JWT);
  });

  it("is safe for an unrecognized value", () => {
    expect(describeSignInFailure("a bare string")).toContain("status=unknown");
  });
});
