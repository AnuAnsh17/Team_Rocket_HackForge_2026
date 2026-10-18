import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "@/components/LoginForm";

/**
 * Sign-in route.
 *
 * It sits outside the `(console)` route group on purpose: it must render without the
 * console shell, and without requiring an identity - it is where an identity is obtained.
 */
export const metadata: Metadata = {
  title: "Sign in · Proofline console",
  robots: { index: false, follow: false },
};

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-surface)] p-6 text-[var(--color-text)]">
      <div className="w-full max-w-md">
        <p className="mb-4 text-sm font-semibold tracking-tight">
          Proofline <span className="text-[var(--color-text-muted)]">· Internal console</span>
        </p>
        {/* `useSearchParams` needs a Suspense boundary when a route can be prerendered. */}
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
