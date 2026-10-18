"use client";

/**
 * Email/password sign-in.
 *
 * The form talks to Supabase Auth directly through the browser client. It never touches the
 * Proofline backend with a password: the password goes to the identity provider, and what
 * the console then sends to the backend is the resulting access token, which the backend
 * verifies itself.
 *
 * Nothing here decides authorization. A successful sign-in only means the console may ask
 * the backend who the caller is; the backend may still answer 403, and that is rendered as
 * its own state rather than as a failed sign-in.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { DEMO_MODE_ACTIVE, SUPABASE_CONFIGURED } from "@/lib/api";
import { signInWithPassword } from "@/lib/auth/actions";
import { safeNextPath } from "@/lib/auth/session";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const sessionExpired = searchParams.get("reason") === "expired";
  const next = safeNextPath(searchParams.get("next"));

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);

    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setError("The sign-in service is not configured for this build.");
      setBusy(false);
      return;
    }

    const result = await signInWithPassword(supabase, email.trim(), password);
    // Drop the password as soon as it is used, whether or not it worked.
    setPassword("");
    setBusy(false);

    if (!result.ok) {
      setError(result.message);
      return;
    }
    // Land on the console. `refresh()` makes the server components re-read the new session
    // cookie, so the console renders as the account that just signed in.
    router.replace(next);
    router.refresh();
  }

  if (!SUPABASE_CONFIGURED) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6">
        <h1 className="text-base font-semibold text-[var(--color-text)]">Sign-in is not configured</h1>
        <p className="mt-2 max-w-prose text-sm text-[var(--color-text-muted)]">
          This build has no Supabase project configured, so there is no identity provider to sign
          in against.
          {DEMO_MODE_ACTIVE
            ? " Demo mode is active: the console identifies an actor by id through the console header instead."
            : " Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, or enable NEXT_PUBLIC_DEMO_MODE for local development."}
        </p>
        <p className="mt-4">
          <a
            href="/"
            className="inline-block rounded border border-[var(--color-border-strong)] px-3 py-1.5 text-sm font-medium text-[var(--color-text)]"
          >
            Go to the console
          </a>
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6"
      aria-label="Sign in to the Proofline console"
    >
      <h1 className="text-base font-semibold text-[var(--color-text)]">Sign in</h1>
      <p className="mt-1 max-w-prose text-sm text-[var(--color-text-muted)]">
        Use your Proofline account. Signing in proves who you are; what you may see is decided by
        the backend from your membership.
      </p>

      {sessionExpired && (
        <p role="status" className="mt-4 rounded border border-[var(--color-border-strong)] p-3 text-sm">
          Your session expired, so you were signed out.
        </p>
      )}

      <div className="mt-4 space-y-3">
        <label className="block text-sm" htmlFor="email">
          <span className="text-[var(--color-text)]">Work email</span>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
          />
        </label>

        <label className="block text-sm" htmlFor="password">
          <span className="text-[var(--color-text)]">Password</span>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
          />
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded border border-[var(--color-severity-blocking)] p-3 text-sm">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="mt-5 rounded border border-[var(--color-border-strong)] px-4 py-2 text-sm font-medium disabled:opacity-60"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>

      <p className="mt-4 max-w-prose text-xs text-[var(--color-text-muted)]">
        Permissions come from your organization membership, not from this form. If the backend
        refuses a request after you sign in, the console will say so rather than pretending the
        data is empty.
      </p>
    </form>
  );
}
