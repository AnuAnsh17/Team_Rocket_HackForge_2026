/**
 * Next 16 proxy (the renamed middleware convention).
 *
 * Every console request is gated here: an unauthenticated visitor is sent to `/login`, and
 * an authenticated visitor is moved off it. When no Supabase project is configured the
 * proxy passes the request through, so local demo development is unaffected.
 *
 * `proxy.ts` is used rather than the deprecated `middleware.ts`; Next 16.4 warns that the
 * old name is deprecated.
 */

import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/refresh";

export function proxy(request: NextRequest) {
  return updateSession(request);
}

/**
 * Run on page requests only.
 *
 * Static assets and image optimisation are excluded so the proxy is not invoked for a
 * stylesheet, and the auth-refresh path is never on the critical path of loading one.
 */
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|map|txt)$).*)",
  ],
};
