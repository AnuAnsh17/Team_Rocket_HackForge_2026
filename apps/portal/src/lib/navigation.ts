/**
 * Employee portal navigation.
 *
 * Flat and short on purpose. An employee has one job to do here - get a receipt in and
 * find out where it stands - and a deep navigation tree works against that.
 */

export interface PortalNavItem {
  href: string;
  label: string;
  description: string;
  /**
   * Whether the underlying workflow is implemented.
   *
   * `false` renders an explicit "not implemented yet" marker on the page. All are `false`
   * today. A test fails if one is flipped without the work.
   */
  implemented: boolean;
}

export const PORTAL_NAV: PortalNavItem[] = [
  {
    href: "/",
    label: "Home",
    description: "Submitted this month, pending items, anything needing your input.",
    implemented: false,
  },
  {
    href: "/upload",
    label: "Add a receipt",
    description: "Photograph or choose a receipt, then check what was read from it.",
    implemented: false,
  },
  {
    href: "/review",
    label: "Check the details",
    description: "Confirm or correct the merchant, date, total and business context.",
    implemented: false,
  },
  {
    href: "/expenses",
    label: "My expenses",
    description: "Everything you have submitted, with its current status.",
    implemented: false,
  },
  {
    href: "/corrections",
    label: "Needs your input",
    description: "Claims where finance has asked you for something.",
    implemented: false,
  },
  {
    href: "/allowance",
    label: "My allowance",
    description: "The limits that apply to you, from your assigned policy.",
    implemented: false,
  },
];

export function portalHrefs(): string[] {
  return PORTAL_NAV.map((item) => item.href);
}
