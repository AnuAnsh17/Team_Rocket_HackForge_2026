/**
 * Session refresh and route gating for the proxy (Next 16's middleware).
 *
 * This is the cookie-based App Router pattern from `@supabase/ssr`: a server client that
 * can both read the request's cookies and write refreshed ones onto the response. It runs
 * before rendering, so an expired access token is refreshed once, in one place, instead of
 * separately in every component.
 *
 * The gate itself is the pure `decideNavigation` function; this module only performs the
 * I/O around it.
 */

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { decideNavigation } from "@/lib/auth/session";
import { CONSOLE_AUTH, SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/config";

/**
 * Refresh the session and apply the navigation gate for one request.
 *
 * When no project is configured the request is passed through untouched: local demo
 * development must not be gated behind a sign-in that cannot be completed.
 */
export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({ request });

  if (!CONSOLE_AUTH.supabaseConfigured) {
    return response;
  }

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // Mirror onto the request so a later read in this same pass sees the new value...
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        // ...and rebuild the response so the refreshed cookies are actually sent.
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // `getUser()` verifies the token with the auth server and triggers a refresh when it has
  // expired; the refresh writes the new cookies through `setAll` above. Reading the result
  // now means the response is committed only after the session state is settled.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const decision = decideNavigation({
    configured: true,
    hasUser: Boolean(user),
    pathname: request.nextUrl.pathname,
  });

  if (decision.action === "redirect") {
    const url = request.nextUrl.clone();
    url.pathname = decision.to;
    url.search = decision.next ? `?next=${encodeURIComponent(decision.next)}` : "";
    const redirect = NextResponse.redirect(url);
    // A refresh may have happened during `getUser()`: carry those cookies onto the
    // redirect so the session is not silently dropped on the way to the sign-in screen.
    for (const cookie of response.cookies.getAll()) {
      redirect.cookies.set(cookie);
    }
    return redirect;
  }

  return response;
}
