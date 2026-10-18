"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { useConsoleAuth } from "@/components/AuthProvider";
import { useBackendIdentity } from "@/components/IdentityProvider";
import { DEMO_MODE_ACTIVE, readDemoActorId, writeDemoActorId } from "@/lib/api";
import { sectionsForRoles, type ConsoleRole } from "@/lib/navigation";

/**
 * Console application shell.
 *
 * The role list below is a UI aid for demonstrating role-specific navigation. It is
 * NOT how access is decided: every page calls a backend endpoint that resolves the
 * caller's roles and scope from its own database and refuses unauthorized requests.
 * See the header comment in src/lib/navigation.ts.
 *
 * The header shows the identity the BACKEND resolved (`GET /api/v1/me`), not anything the
 * client believes about itself, and a demo session is labelled as one so it can never be
 * mistaken for a real sign-in.
 */
const DEMO_ROLE_PRESETS: Array<{ label: string; roles: ConsoleRole[] }> = [
  { label: "Finance reviewer", roles: ["finance_reviewer"] },
  { label: "Finance administrator", roles: ["finance_admin"] },
  { label: "Manager", roles: ["manager"] },
  { label: "HR reviewer", roles: ["hr_reviewer"] },
  { label: "Organization administrator", roles: ["org_admin"] },
  { label: "Policy administrator", roles: ["policy_admin"] },
  { label: "Auditor (read-only)", roles: ["auditor"] },
];

function IdentityBar() {
  const auth = useConsoleAuth();
  const [signingOut, setSigningOut] = useState(false);

  if (auth.mode === "demo") {
    return (
      <span
        data-session-kind="demo"
        className="rounded border border-[var(--color-severity-warning)] px-2 py-0.5 text-xs text-[var(--color-severity-warning)]"
      >
        Demo session — not a real sign-in
      </span>
    );
  }

  if (auth.mode === "unconfigured") {
    return (
      <span
        data-session-kind="unconfigured"
        className="rounded border border-[var(--color-severity-warning)] px-2 py-0.5 text-xs text-[var(--color-severity-warning)]"
      >
        No identity provider configured
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span data-session-kind="supabase" className="text-xs text-[var(--color-text-muted)]">
        {auth.email ?? "Signed in"}
      </span>
      <button
        type="button"
        disabled={signingOut}
        onClick={() => {
          setSigningOut(true);
          void auth.signOut();
        }}
        className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs disabled:opacity-60"
      >
        {signingOut ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const identity = useBackendIdentity();
  const [preset, setPreset] = useState(DEMO_ROLE_PRESETS[0]?.label ?? "");
  const activePreset = DEMO_ROLE_PRESETS.find((entry) => entry.label === preset);
  const roles = activePreset?.roles ?? [];
  const sections = sectionsForRoles(roles);
  const demoActorId = DEMO_MODE_ACTIVE ? readDemoActorId() : null;

  const membership = identity.membership;

  return (
    <div className="min-h-screen bg-[var(--color-surface)] text-[var(--color-text)]">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface-raised)]">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-4 px-6 py-3">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            Proofline <span className="text-[var(--color-text-muted)]">· Internal console</span>
          </Link>

          <span className="rounded border border-[var(--color-severity-warning)] px-2 py-0.5 text-xs text-[var(--color-severity-warning)]">
            Scaffold · no audit workflow implemented
          </span>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <label className="text-xs text-[var(--color-text-muted)]" htmlFor="demo-role">
              Demo role preview
            </label>
            <select
              id="demo-role"
              value={preset}
              onChange={(event) => setPreset(event.target.value)}
              className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs"
            >
              {DEMO_ROLE_PRESETS.map((entry) => (
                <option key={entry.label} value={entry.label}>
                  {entry.label}
                </option>
              ))}
            </select>

            {DEMO_MODE_ACTIVE && (
              <input
                aria-label="Demo actor id"
                placeholder="X-Demo-Actor-Id"
                defaultValue={demoActorId ?? ""}
                onBlur={(event) => {
                  const next = event.target.value.trim();
                  if (next !== (demoActorId ?? "")) writeDemoActorId(next || null);
                }}
                className="w-full min-w-0 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 font-mono text-xs sm:w-64"
              />
            )}

            <IdentityBar />
          </div>
        </div>

        <p className="mx-auto max-w-[1600px] px-6 pb-2 text-xs text-[var(--color-text-muted)]">
          {membership ? (
            <>
              Signed in as{" "}
              <span className="font-medium text-[var(--color-text)]">
                {membership.user.display_name}
              </span>
              {membership.employee_code ? ` (${membership.employee_code})` : ""}, membership{" "}
              <span className="font-mono">{membership.id}</span>, status {membership.status}. This
              is the identity the backend resolved.
            </>
          ) : (
            <>
              Navigation and the role selector are a preview of the intended information
              architecture. They are <strong>not</strong> access control: the backend resolves
              roles, permissions and scope for the authenticated actor on every request, and
              refuses anything unauthorized.
            </>
          )}
        </p>
      </header>

      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-6 py-6 lg:flex-row">
        <nav aria-label="Sections" className="w-full shrink-0 space-y-6 lg:w-64">
          {sections.length === 0 && (
            <p className="text-xs text-[var(--color-text-muted)]">
              No sections are shown for this role preview.
            </p>
          )}
          {sections.map((section) => (
            <div key={section.id}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                {section.label}
              </p>
              <ul className="space-y-1">
                {section.items.map((item) => {
                  const active =
                    pathname === item.href ||
                    (item.href !== "/" && pathname.startsWith(item.href));
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`block rounded px-3 py-2 text-sm ${
                          active
                            ? "bg-[var(--color-surface-muted)] font-medium"
                            : "hover:bg-[var(--color-surface-muted)]"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          {item.label}
                          {!item.implemented && (
                            <span
                              title="Not implemented yet"
                              className="rounded border border-[var(--color-severity-warning)] px-1 text-[10px] uppercase tracking-wide text-[var(--color-severity-warning)]"
                            >
                              stub
                            </span>
                          )}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/*
          Keyed on the backend-resolved identity. When the account changes, React unmounts
          this subtree, so every page's loaded state - the analytics figures, the chosen
          period, any fetched row - is discarded and re-fetched for the new identity. That is
          what makes "switch account, see the previous account's numbers" impossible rather
          than merely unlikely.
        */}
        <main key={identity.identityKey} className="min-w-0 flex-1 space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}
