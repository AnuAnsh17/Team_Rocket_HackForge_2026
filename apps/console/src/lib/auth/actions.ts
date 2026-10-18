/**
 * The three things the console does to a session: sign in, restore it, sign it out.
 *
 * They are functions over a minimal client interface rather than hooks, so they can be
 * driven in a test with a stub and so the components stay thin. Every one of them avoids
 * logging: the only thing that may ever be written is a status/code pair from
 * {@link describeSignInFailure}, never a credential.
 */

import type { SupabaseClient } from "@supabase/supabase-js";

import { mapSignInError } from "@/lib/auth/messages";
import type { SessionLike } from "@/lib/auth/session";

/** Just the part of a Supabase client these functions use. */
export type AuthClient = Pick<SupabaseClient, "auth">;

export interface SignInResult {
  ok: boolean;
  /** A message safe to show a person, or null on success. */
  message: string | null;
}

/**
 * Attempt an email/password sign-in.
 *
 * The password is passed straight to the auth client and never stored, echoed or logged;
 * on failure only a mapped, credential-free sentence is returned.
 */
export async function signInWithPassword(
  client: AuthClient,
  email: string,
  password: string,
): Promise<SignInResult> {
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) return { ok: false, message: mapSignInError(error) };
  return { ok: true, message: null };
}

/**
 * Restore the current session, or null.
 *
 * `getSession()` refreshes an expired session first, so a null result means there is
 * genuinely no session rather than merely an old one.
 */
export async function restoreSession(client: AuthClient): Promise<SessionLike | null> {
  const { data } = await client.auth.getSession();
  return data.session ?? null;
}

/**
 * Sign out.
 *
 * Clears the local session even when the network sign-out fails: a user who pressed sign
 * out must end up signed out, and leaving a usable session on the device because the auth
 * server was unreachable is the worse failure.
 */
export async function signOutSession(client: AuthClient): Promise<void> {
  try {
    await client.auth.signOut();
  } catch {
    // The local session below is cleared regardless.
  }
}
