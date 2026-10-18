import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

/**
 * Root layout.
 *
 * Deeper structure is a route group. The signed-in console lives under `app/(console)`,
 * which adds the application shell and the authentication guard; `app/login` deliberately
 * sits outside it, so an unauthenticated visitor never renders console chrome.
 *
 * `robots: noindex` is not a security control - every request is authorized by the backend -
 * it only keeps an internal surface out of search engines.
 */
export const metadata: Metadata = {
  title: "Proofline · Internal console",
  description:
    "Internal HR, manager, finance and administration console for Proofline. Scaffold: the audit workflow is not implemented.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
