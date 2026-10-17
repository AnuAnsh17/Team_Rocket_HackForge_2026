import { describe, expect, it } from "vitest";

import { NAV_SECTIONS, allHrefs, sectionsForRoles } from "../src/lib/navigation";

/**
 * These assertions protect two properties that are easy to lose as the console grows:
 * every route is reachable by at least one role, and no route claims to be implemented
 * while it is not.
 */

describe("console navigation", () => {
  it("exposes every defined route through at least one role", () => {
    const everyRole = [
      "employee",
      "manager",
      "hr_reviewer",
      "finance_reviewer",
      "finance_admin",
      "org_admin",
      "policy_admin",
      "auditor",
    ] as const;

    const reachable = new Set(
      sectionsForRoles(everyRole).flatMap((section) => section.items.map((item) => item.href)),
    );

    for (const href of allHrefs()) {
      expect(reachable.has(href), `${href} is not reachable by any role`).toBe(true);
    }
  });

  it("reports every scaffolded route as not implemented", () => {
    // If a route gains a real implementation, flip its `implemented` flag in the same
    // change as the work. This test exists so that cannot be forgotten.
    const claimedImplemented = NAV_SECTIONS.flatMap((section) =>
      section.items.filter((item) => item.implemented).map((item) => item.href),
    );
    expect(claimedImplemented).toEqual([]);
  });

  it("shows an auditor only read-oriented sections", () => {
    const sections = sectionsForRoles(["auditor"]);
    const ids = sections.map((section) => section.id);
    expect(ids).not.toContain("review");
    expect(ids).not.toContain("hr");
  });

  it("shows a finance reviewer the review section", () => {
    const hrefs = sectionsForRoles(["finance_reviewer"]).flatMap((section) =>
      section.items.map((item) => item.href),
    );
    expect(hrefs).toContain("/review");
    expect(hrefs).toContain("/duplicates");
  });

  it("gives an unknown role nothing", () => {
    expect(sectionsForRoles([])).toEqual([]);
  });
});
