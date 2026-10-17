import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PortalShell } from "@/components/PortalShell";

import "./globals.css";

export const metadata: Metadata = {
  title: "Proofline · My expenses",
  description:
    "Submit receipts, check what was read from them and follow the status of your expense claims.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <PortalShell>{children}</PortalShell>
      </body>
    </html>
  );
}
