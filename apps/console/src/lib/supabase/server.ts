/**
 * Supabase server client.
 *
 * Used by server components and route handlers. It reads the same cookies the proxy
 * refreshes, so a server-rendered decision and a client-side one never disagree about who
 * the caller is.
 *
 * A new client is created per request: `@supabase/ssr` clients carry cookie state and must
 * never be shared between requests or between users.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { CONSOLE_AUTH, SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/config";

/** Build a server client bound to the current request's cookies. */
export async function createSupabaseServerClient() {
  const cookieStore = await cookies();

  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // Called from a Server Component, where cookies are read-only. This is expected:
          // the proxy refreshes the session and writes the cookies, so a failed write here
          // is not data loss.
        }
      },
    },
  });
}

/**
 * The verified user for the current request, or null.
 *
 * `getUser()` is used rather than `getSession()` because it asks the auth server to verify
 * the token; a server component must not make an authorization decision on an unverified
 * cookie. Returns null immediately when no project is configured, so local demo builds do
 * not attempt a verification they cannot complete.
 */
export async function getServerUser() {
  if (!CONSOLE_AUTH.supabaseConfigured) return null;
  const supabase = await createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}
