/**
 * The token provider, exercised through the real API client.
 *
 * `createConsoleApi` passes `getToken` into the shared `@proofline/api-client`, so these
 * assertions are on the HTTP requests that were actually issued - the Authorization header
 * a stub transport received - rather than on a mock of the provider. That is what proves the
 * token reaches the backend, and that an asynchronous provider is awaited rather than
 * stringified.
 */

import { unwrap } from "@proofline/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createConsoleApi, consoleAuthHeaders, readAccessToken, setAccessTokenProvider } from "../src/lib/api";
import { restoreSession, type AuthClient } from "../src/lib/auth/actions";
import { accessTokenFromSession } from "../src/lib/auth/session";

/** A minimal auth client, enough for the restoration path. */
function stubAuth(script: { session: unknown }) {
  const client = {
    auth: {
      getSession: vi.fn(async () => ({ data: { session: script.session } })),
    },
  } as unknown as AuthClient;
  return { client };
}

const MEMBERSHIP = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: "22222222-2222-4222-8222-222222222222",
  user: { id: "33333333-3333-4333-8333-333333333333", display_name: "Aditi Rao", is_active: true },
  employee_code: "E-001",
  status: "active",
  manager_membership_id: null,
  joined_on: "2026-01-05",
};

interface RecordedCall {
  url: string;
  headers: Headers;
}

function stubTransport(): { calls: RecordedCall[]; fetch: typeof globalThis.fetch } {
  const calls: RecordedCall[] = [];
  const fetch: typeof globalThis.fetch = async (input, init) => {
    const request = input instanceof Request ? input : null;
    calls.push({
      url: request ? request.url : String(input),
      headers: request ? request.headers : new Headers(init?.headers),
    });
    return new Response(JSON.stringify(MEMBERSHIP), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  return { calls, fetch };
}

afterEach(() => {
  setAccessTokenProvider(null);
});

describe("token provider", () => {
  it("reads no token when no provider is registered", async () => {
    expect(await readAccessToken()).toBeNull();

    const { calls, fetch } = stubTransport();
    await unwrap(createConsoleApi({ baseUrl: "http://api.test", fetch }).GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBeNull();
  });

  it("awaits an asynchronous provider and sends the resolved token", async () => {
    // The failure this guards against: an unawaited provider sets the header to
    // "Bearer [object Promise]".
    setAccessTokenProvider(async () => {
      await Promise.resolve();
      return "access-token-from-session";
    });

    const { calls, fetch } = stubTransport();
    await unwrap(createConsoleApi({ baseUrl: "http://api.test", fetch }).GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBe("Bearer access-token-from-session");
    expect(calls[0]!.headers.get("authorization")).not.toContain("Promise");
  });

  it("sends nothing for an absent or expired session", async () => {
    // What the real provider returns when `getSession()` has no usable session.
    setAccessTokenProvider(async () => null);

    const { calls, fetch } = stubTransport();
    await unwrap(createConsoleApi({ baseUrl: "http://api.test", fetch }).GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBeNull();
  });

  it("treats an empty-string token as no token", async () => {
    setAccessTokenProvider(async () => "");
    expect(await readAccessToken()).toBeNull();
  });

  it("reads the token per request, so an account switch uses the new account's token", async () => {
    let token = "token-for-account-a";
    setAccessTokenProvider(async () => token);

    const { calls, fetch } = stubTransport();
    const client = createConsoleApi({ baseUrl: "http://api.test", fetch });

    await unwrap(client.GET("/api/v1/me"));
    token = "token-for-account-b";
    await unwrap(client.GET("/api/v1/me"));

    // The second request carries the second account's token: nothing was captured at
    // construction, so a stale credential cannot be reused for a new account.
    expect(calls[0]!.headers.get("authorization")).toBe("Bearer token-for-account-a");
    expect(calls[1]!.headers.get("authorization")).toBe("Bearer token-for-account-b");
    expect(calls[0]!.headers.get("authorization")).not.toBe(calls[1]!.headers.get("authorization"));
  });

  it("impersonates restoration on reload: a restored session's token is what is sent", async () => {
    // The real path: `restoreSession` reads the cookie-backed session, `accessTokenFromSession`
    // decides whether it is still usable, and that value is what the client attaches.
    const { client: auth } = stubAuth({
      session: { access_token: "restored-access-token", expires_at: 9_999_999_999, user: { id: "u1" } },
    });
    setAccessTokenProvider(async () => accessTokenFromSession(await restoreSession(auth)));

    const { calls, fetch } = stubTransport();
    await unwrap(createConsoleApi({ baseUrl: "http://api.test", fetch }).GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBe("Bearer restored-access-token");
  });

  it("sends nothing when a restored session is expired", async () => {
    const { client: auth } = stubAuth({
      session: { access_token: "stale-access-token", expires_at: 1, user: { id: "u1" } },
    });
    setAccessTokenProvider(async () => accessTokenFromSession(await restoreSession(auth)));

    const { calls, fetch } = stubTransport();
    await unwrap(createConsoleApi({ baseUrl: "http://api.test", fetch }).GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBeNull();
  });

  it("surfaces a sign-out immediately: a provider that starts returning null stops the header", async () => {
    let signedIn = true;
    setAccessTokenProvider(async () => (signedIn ? "session-token" : null));

    const { calls, fetch } = stubTransport();
    const client = createConsoleApi({ baseUrl: "http://api.test", fetch });

    await unwrap(client.GET("/api/v1/me"));
    signedIn = false;
    await unwrap(client.GET("/api/v1/me"));

    expect(calls[0]!.headers.get("authorization")).toBe("Bearer session-token");
    expect(calls[1]!.headers.get("authorization")).toBeNull();
  });
});

describe("consoleAuthHeaders (raw authorized requests)", () => {
  it("carries the bearer token, so a direct fetch is not a second identity path", async () => {
    setAccessTokenProvider(async () => "raw-request-token");
    const headers = await consoleAuthHeaders();
    expect(headers.get("authorization")).toBe("Bearer raw-request-token");
  });

  it("sends no credential when there is no token and demo mode is inactive", async () => {
    // In this test environment no Supabase project is configured and demo mode is off, so
    // there is no identity path at all.
    const headers = await consoleAuthHeaders();
    expect(headers.get("authorization")).toBeNull();
    expect(headers.get("x-demo-actor-id")).toBeNull();
  });
});
