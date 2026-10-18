/**
 * Session actions against a stubbed auth client.
 *
 * The login error paths, session restoration and sign-out clearing are driven here, with no
 * live Supabase project: the functions take a minimal `{ auth }` interface, so a stub that
 * records calls is enough to prove what the console does with a session.
 */

import { describe, expect, it, vi } from "vitest";

import { restoreSession, signInWithPassword, signOutSession, type AuthClient } from "../src/lib/auth/actions";

const FAKE_JWT =
  "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJlLXNlZ21lbnQ";

/** A stub auth client that records calls and answers from a scripted result. */
function stubClient(script: {
  signIn?: { data?: unknown; error?: unknown };
  signOut?: { error?: unknown } | Error;
  session?: { access_token?: string | null; expires_at?: number | null; user?: { id?: string } } | null;
  getSessionThrows?: boolean;
} = {}) {
  const calls = {
    signInWithPassword: [] as Array<{ email: string; password: string }>,
    signOut: 0,
    getSession: 0,
  };

  const client = {
    auth: {
      signInWithPassword: vi.fn(async (credentials: { email: string; password: string }) => {
        calls.signInWithPassword.push(credentials);
        return script.signIn ?? { data: {}, error: null };
      }),
      signOut: vi.fn(async () => {
        calls.signOut += 1;
        if (script.signOut instanceof Error) throw script.signOut;
        return script.signOut ?? { error: null };
      }),
      getSession: vi.fn(async () => {
        calls.getSession += 1;
        if (script.getSessionThrows) throw new Error("no session");
        return { data: { session: script.session ?? null } };
      }),
    },
  } as unknown as AuthClient;

  return { client, calls };
}

describe("signInWithPassword", () => {
  it("passes the credentials straight to the auth client and reports success", async () => {
    const { client, calls } = stubClient({ signIn: { data: { user: {} }, error: null } });

    const result = await signInWithPassword(client, "finance@example.com", "hunter2-hunter2");

    expect(result).toEqual({ ok: true, message: null });
    expect(calls.signInWithPassword).toEqual([
      { email: "finance@example.com", password: "hunter2-hunter2" },
    ]);
  });

  it("maps a refused sign-in to a safe message, never the provider text", async () => {
    const { client } = stubClient({
      signIn: { data: {}, error: { status: 400, message: "Invalid login credentials" } },
    });

    const result = await signInWithPassword(client, "finance@example.com", "wrong");

    expect(result.ok).toBe(false);
    expect(result.message).toMatch(/email address and password/i);
    expect(result.message).not.toContain("wrong");
  });

  it("maps a network failure", async () => {
    const { client } = stubClient({ signIn: { data: {}, error: new TypeError("fetch failed") } });
    const result = await signInWithPassword(client, "a@example.com", "pw");
    expect(result.message).toMatch(/could not be reached/i);
  });

  it("does not leak a credential the provider put in its own error", async () => {
    const { client } = stubClient({
      signIn: { data: {}, error: { status: 401, message: `password hunter2 token ${FAKE_JWT}` } },
    });

    const result = await signInWithPassword(client, "a@example.com", "hunter2");

    expect(result.message).not.toContain("hunter2");
    expect(result.message).not.toContain(FAKE_JWT);
  });
});

describe("restoreSession", () => {
  it("returns the session the cookies carry", async () => {
    const { client } = stubClient({ session: { access_token: "t", expires_at: 9_999_999_999 } });
    const session = await restoreSession(client);
    expect(session?.access_token).toBe("t");
  });

  it("returns null when there is no session", async () => {
    const { client } = stubClient({ session: null });
    expect(await restoreSession(client)).toBeNull();
  });
});

describe("signOutSession", () => {
  it("asks the auth client to sign out", async () => {
    const { client, calls } = stubClient();
    await signOutSession(client);
    expect(calls.signOut).toBe(1);
  });

  it("does not throw when the network sign-out fails", async () => {
    // A user who pressed sign out must end up signed out; a failing auth server must not
    // leave the caller stuck on a console screen.
    const { client, calls } = stubClient({ signOut: new Error("network down") });
    await expect(signOutSession(client)).resolves.toBeUndefined();
    expect(calls.signOut).toBe(1);
  });
});
