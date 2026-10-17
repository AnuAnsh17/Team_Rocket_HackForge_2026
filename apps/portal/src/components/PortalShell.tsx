"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { DEMO_MODE_ENABLED, readDemoActorId, writeDemoActorId } from "@/lib/api";
import { PORTAL_NAV } from "@/lib/navigation";

/**
 * Employee portal shell.
 *
 * The demo actor field exists to demonstrate that an employee sees only their own data.
 * It identifies a USER; the backend decides what that user may see. Switching ids here
 * cannot reveal another employee's claim, because the backend enforces ownership.
 */
export function PortalShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [demoActorId, setDemoActorId] = useState(
    typeof window === "undefined" ? null : readDemoActorId(),
  );

  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface-raised)]">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-4 px-5 py-3">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            Proofline
          </Link>
          <span className="rounded border border-[var(--color-severity-warning)] px-2 py-0.5 text-xs text-[var(--color-severity-warning)]">
            Scaffold · submission and checks not implemented
          </span>

          {DEMO_MODE_ENABLED && (
            <div className="ml-auto flex items-center gap-2">
              <label className="text-xs text-[var(--color-text-muted)]" htmlFor="demo-actor">
                Demo employee
              </label>
              <input
                id="demo-actor"
                defaultValue={demoActorId ?? ""}
                placeholder="seeded user id"
                onBlur={(event) => {
                  const next = event.target.value.trim();
                  setDemoActorId(next || null);
                  writeDemoActorId(next || null);
                }}
                className="w-72 rounded-lg border border-[var(--color-border)] px-2 py-1 font-mono text-xs"
              />
            </div>
          )}
        </div>

        <nav aria-label="Sections" className="mx-auto max-w-5xl px-5">
          <ul className="flex flex-wrap gap-1 pb-2">
            {PORTAL_NAV.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                      active
                        ? "bg-[var(--color-surface-muted)] font-medium"
                        : "hover:bg-[var(--color-surface-muted)]"
                    }`}
                  >
                    {item.label}
                    {!item.implemented && (
                      <span
                        title="Not implemented yet"
                        className="rounded border border-[var(--color-severity-warning)] px-1 text-[10px] uppercase text-[var(--color-severity-warning)]"
                      >
                        stub
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-5 py-6">{children}</main>

      <footer className="mx-auto max-w-5xl px-5 pb-8 text-xs text-[var(--color-text-muted)]">
        You only ever see your own claims, receipts and history. That restriction is
        enforced by the server on every request, not by this page.
      </footer>
    </div>
  );
}
