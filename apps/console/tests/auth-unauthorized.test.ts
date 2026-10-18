/**
 * 401 handling at the transport seam.
 *
 * The rule: a 401 means no valid identity, so the console returns to sign-in and does not
 * retry. A 403 must NOT trigger that path - the identity is valid and simply lacks
 * authority, so sending the caller to a sign-in screen would hide an authorization refusal.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { createConsoleApi, setAccessTokenProvider, setUnauthorizedHandler } from "../src/lib/api";
import { unwrap } from "@proofline/api-client";

function envelope(code: string, message: string) {
  return JSON.stringify({ error: { code, message, details: [], request_id: "req-1" } });
}

const originalFetch = globalThis.fetch;

function respondWith(status: number, code: string) {
  globalThis.fetch = (async () =>
    new Response(envelope(code, "refused"), {
      status,
      headers: { "content-type": "application/json" },
    })) as typeof globalThis.fetch;
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  setUnauthorizedHandler(null);
  setAccessTokenProvider(null);
  vi.restoreAllMocks();
});

describe("console 401 handling", () => {
  it("reports a 401 so the session is reset, and does not retry", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respondWith(401, "UNAUTHENTICATED");

    // No fetch override: the console client's own `consoleFetch` is what is under test.
    const client = createConsoleApi({ baseUrl: "http://api.test" });
    const callsBefore = handler.mock.calls.length;

    await expect(unwrap(client.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401 });

    // Reported exactly once: no automatic re-request was made.
    expect(handler).toHaveBeenCalledTimes(callsBefore + 1);
  });

  it("does not treat a 403 as a sign-out", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respondWith(403, "FORBIDDEN");

    const client = createConsoleApi({ baseUrl: "http://api.test" });

    await expect(unwrap(client.GET("/api/v1/me"))).rejects.toMatchObject({
      status: 403,
      code: "FORBIDDEN",
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not treat a server error as a sign-out", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respondWith(500, "INTERNAL_ERROR");

    const client = createConsoleApi({ baseUrl: "http://api.test" });
    await expect(unwrap(client.GET("/api/v1/me"))).rejects.toMatchObject({ status: 500 });
    expect(handler).not.toHaveBeenCalled();
  });

  it("passes the response through untouched", async () => {
    respondWith(403, "FORBIDDEN");
    const client = createConsoleApi({ baseUrl: "http://api.test" });
    let status = 0;
    try {
      await unwrap(client.GET("/api/v1/me"));
    } catch (error) {
      status = (error as { status: number }).status;
    }
    expect(status).toBe(403);
  });
});
