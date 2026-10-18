"use client";

/**
 * Console authentication context.
 *
 * Holds the Supabase session, exposes sign-out, and connects the API client's 401 signal to
 * navigation. It deliberately does NOT decide authorization: it knows whether there is a
 * session, not what that session may do. Roles and permissions are the backend's answer,
 * read from `GET /api/v1/me` before anything renders (see `IdentityProvider`).
 *
 * Session restoration on reload is inherited from `@supabase/ssr`: the browser client reads
 * the session from cookies, so a reload lands in the same state without a separate token
 * store here.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { CONSOLE_AUTH, DEMO_MODE_ACTIVE, readDemoActorId, setUnauthorizedHandler } from "@/lib/api";
import { signOutSession } from "@/lib/auth/actions";
import { identityKeyFromSession, type SessionLike } from "@/lib/auth/session";
import type { ConsoleAuthMode } from "@/lib/supabase/config";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export type ConsoleAuthStatus = "loading" | "authenticated" | "demo" | "anonymous";

export interface ConsoleAuthContextValue {
  status: ConsoleAuthStatus;
  /** Which identity path this build is using. */
  mode: ConsoleAuthMode;
  /** The signed-in account's email, when there is one. */
  email: string | null;
  /**
   * A stable key for the current identity.
   *
   * Changes when the account changes, which is what keys the console content so one
   * account cannot inherit another's rendered state.
   */
  identityKey: string;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<ConsoleAuthContextValue | null>(null);

export function useConsoleAuth(): ConsoleAuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useConsoleAuth must be used inside <AuthProvider>.");
  return value;
}

function initialStatus(): ConsoleAuthStatus {
  if (CONSOLE_AUTH.supabaseConfigured) return "loading";
  return DEMO_MODE_ACTIVE ? "demo" : "anonymous";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<SessionLike | null>(null);
  const [status, setStatus] = useState<ConsoleAuthStatus>(initialStatus);

  useEffect(() => {
    if (!CONSOLE_AUTH.supabaseConfigured) return;
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setStatus("anonymous");
      return;
    }

    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session ?? null);
      setStatus(data.session ? "authenticated" : "anonymous");
    });

    // `onAuthStateChange` covers sign-in, sign-out and silent token refresh, so the
    // context never has to poll and the token provider (which reads the session directly)
    // stays the single source of the bearer value.
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession ?? null);
      setStatus(nextSession ? "authenticated" : "anonymous");
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  /**
   * A 401 from any console request: drop to anonymous and return to sign-in.
   *
   * No retry. Re-sending a credential the backend has already rejected cannot succeed, and
   * a retry loop would turn one expired session into a burst of failures on every page.
   */
  useEffect(() => {
    if (!CONSOLE_AUTH.supabaseConfigured) return;
    setUnauthorizedHandler(() => {
      setSession(null);
      setStatus("anonymous");
      router.replace("/login?reason=expired");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  const signOut = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    if (supabase) await signOutSession(supabase);
    // Clear local state before navigating, so nothing keyed on the old identity can render
    // during the transition.
    setSession(null);
    setStatus("anonymous");
    router.replace("/login");
    router.refresh();
  }, [router]);

  const value = useMemo<ConsoleAuthContextValue>(
    () => ({
      status,
      mode: CONSOLE_AUTH.mode,
      email: session?.user?.email ?? null,
      identityKey:
        status === "demo" ? `demo:${readDemoActorId() ?? "unset"}` : identityKeyFromSession(session),
      signOut,
    }),
    [status, session, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
