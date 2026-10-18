/**
 * Supabase browser client.
 *
 * The session is persisted in cookies by `@supabase/ssr`, not in `localStorage`. That is
 * the documented App Router pattern and it is what lets the proxy and any server component
 * read the same session, so a token refresh performed on one side is not invisible to the
 * other. There is deliberately no hand-rolled token storage here.
 *
 * The client is created lazily and only when a project is configured. Creating it eagerly
 * with an empty URL would throw in every local demo build.
 */

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { setAccessTokenProvider } from "@/lib/api";
import { accessTokenFromSession } from "@/lib/auth/session";
import { CONSOLE_AUTH, SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/config";

let browserClient: SupabaseClient | null = null;

/**
 * The shared browser client, or null when no project is configured.
 *
 * `isSingleton: true` keeps one client per document, so auth state listeners and token
 * refreshes do not multiply as components mount.
 */
export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (!CONSOLE_AUTH.supabaseConfigured) return null;
  if (!browserClient) {
    browserClient = createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      isSingleton: true,
    });
  }
  return browserClient;
}

/**
 * The current access token, or null.
 *
 * Reads the session on every call rather than caching a token, so a refresh or a sign-out
 * is reflected on the very next request and one account's token can never be reused for
 * another. An expired or absent session yields null rather than a stale credential.
 *
 * Nothing here decodes the token or inspects its claims: the backend verifies it.
 */
export async function provideSupabaseAccessToken(): Promise<string | null> {
  const supabase = getSupabaseBrowserClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return accessTokenFromSession(data.session);
}

// Register at import. `src/lib/api.ts` stays free of the SDK; it only ever calls this
// function. When no project is configured the provider returns null, so no bearer header
// is sent and the demo header remains the only identity path.
setAccessTokenProvider(provideSupabaseAccessToken);
