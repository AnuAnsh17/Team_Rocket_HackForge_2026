/**
 * Console navigation.
 *
 * ---------------------------------------------------------------------------
 * THIS FILE DOES NOT ENFORCE ANYTHING.
 *
 * `requiredRoles` decides which links are *shown*. It is a user-experience aid, not an
 * access control. Every page it points at calls a backend endpoint that independently
 * resolves the caller's identity, permissions and resource scope from its own database,
 * and refuses the request if the caller is not authorized.
 *
 * Conversely, hiding a link is not a permission check either: a user can type a URL. The
 * honesty rule is simply that the UI must not display a privileged action to someone the
 * server will refuse, because that produces a broken product rather than a secure one.
 *
 * The authoritative permission model is app/core/permissions.py in the backend and
 * docs/authorization-matrix.md.
 * ---------------------------------------------------------------------------
 */

/** Mirrors the backend RoleCode enum. Kept as a string union until the generated client exposes it. */
export type ConsoleRole =
  | "employee"
  | "manager"
  | "hr_reviewer"
  | "finance_reviewer"
  | "finance_admin"
  | "org_admin"
  | "policy_admin"
  | "auditor";

export interface NavSection {
  id: string;
  label: string;
  /** Shown only when the viewer holds at least one of these roles. */
  requiredRoles: ConsoleRole[];
  items: NavItem[];
}

export interface NavItem {
  href: string;
  label: string;
  description: string;
  /**
   * Whether the underlying workflow is actually implemented.
   *
   * `false` renders an explicit "not implemented yet" marker. Only the overview is `true`:
   * it reads the live analytics API. Every other item is still `false`, because no claim,
   * finding, duplicate or decision route exists. That flag is what stops a placeholder
   * screen from reading as a working feature.
   */
  implemented: boolean;
}

export const NAV_SECTIONS: NavSection[] = [
  {
    id: "overview",
    label: "Overview",
    requiredRoles: ["finance_reviewer", "finance_admin", "org_admin", "policy_admin", "auditor"],
    items: [
      {
        href: "/",
        label: "Overview",
        description:
          "Live analytics for a selected period: workflow status, currency-separated amounts, field completeness and grouped spend.",
        implemented: true,
      },
    ],
  },
  {
    id: "review",
    label: "Review",
    requiredRoles: ["manager", "hr_reviewer", "finance_reviewer", "finance_admin"],
    items: [
      {
        href: "/review",
        label: "Expense review",
        description: "Three-pane workbench: receipt evidence, corrected fields, findings.",
        implemented: false,
      },
      {
        href: "/exceptions",
        label: "Exceptions",
        description: "Missing context, uncertain fields, arithmetic and rule findings.",
        implemented: false,
      },
      {
        href: "/duplicates",
        label: "Duplicate candidates",
        description: "Side-by-side comparison of matched signals. Confirm or dismiss.",
        implemented: false,
      },
      {
        href: "/approvals",
        label: "My approval tasks",
        description: "Approvals required by hierarchy, grade, amount or policy.",
        implemented: false,
      },
    ],
  },
  {
    id: "hr",
    label: "People",
    requiredRoles: ["hr_reviewer", "org_admin"],
    items: [
      {
        href: "/hr",
        label: "HR review",
        description: "Employment status and profile context for a claim; missing HR information.",
        implemented: false,
      },
    ],
  },
  {
    id: "administration",
    label: "Administration",
    requiredRoles: ["finance_admin", "org_admin", "policy_admin", "auditor"],
    items: [
      {
        href: "/policy",
        label: "Policy registry",
        description: "Approved policy versions, rule clauses and effective assignments.",
        implemented: false,
      },
      {
        href: "/audit",
        label: "Audit history",
        description: "Append-only record of who did what, with before/after values.",
        implemented: false,
      },
      {
        href: "/admin/organization",
        label: "Organization",
        description: "Memberships, roles, departments, cost centres, locations and grades.",
        implemented: false,
      },
      {
        href: "/admin/policy",
        label: "Policy assignment",
        description: "Scoped policy and allowance assignments, with effective dates.",
        implemented: false,
      },
    ],
  },
];

/** Sections visible to a viewer holding the given roles. Display only - see the header. */
export function sectionsForRoles(roles: readonly ConsoleRole[]): NavSection[] {
  const held = new Set(roles);
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter(() =>
      section.requiredRoles.some((role) => held.has(role)),
    ),
  })).filter((section) => section.items.length > 0);
}

/** Every route the console defines, for the smoke test and for the sitemap in the README. */
export function allHrefs(): string[] {
  return NAV_SECTIONS.flatMap((section) => section.items.map((item) => item.href));
}
