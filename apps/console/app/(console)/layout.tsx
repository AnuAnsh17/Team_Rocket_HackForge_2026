import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/AuthProvider";
import { AppShell } from "@/components/AppShell";
import { IdentityGate } from "@/components/IdentityGate";
import { IdentityProvider } from "@/components/IdentityProvider";
import { getServerUser } from "@/lib/supabase/server";
import { CONSOLE_AUTH } from "@/lib/supabase/config";

/**
 * The signed-in console: shell, session, and the backend-resolved identity.
 *
 * Two guards run before any console page renders, and they are deliberately independent:
 *
 *  1. The proxy (`proxy.ts`) refreshes the session and redirects an unauthenticated visitor
 *     to `/login`. It runs before rendering, so no protected markup is ever produced for a
 *     request without a session.
 *  2. This layout repeats the check server-side. That is defence in depth: if the proxy's
 *     matcher is ever narrowed, the layout still refuses to render the console for an
 *     unauthenticated request.
 *
 * Neither guard establishes authority. `IdentityProvider` asks the backend who the caller
 * is and what it may do; that answer is what the shell displays and what decides whether a
 * page is shown at all.
 */
export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  if (CONSOLE_AUTH.supabaseConfigured) {
    const user = await getServerUser();
    if (!user) redirect("/login");
  }

  return (
    <AuthProvider>
      <IdentityProvider>
        <AppShell>
          <IdentityGate>{children}</IdentityGate>
        </AppShell>
      </IdentityProvider>
    </AuthProvider>
  );
}
