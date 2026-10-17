import { describe, expect, it } from "vitest";

import { PORTAL_NAV, portalHrefs } from "../src/lib/navigation";

describe("employee portal navigation", () => {
  it("defines a route for every employee task", () => {
    expect(portalHrefs()).toEqual([
      "/",
      "/upload",
      "/review",
      "/expenses",
      "/corrections",
      "/allowance",
    ]);
  });

  it("reports every scaffolded route as not implemented", () => {
    // Flip a flag only in the change that implements the route. This test exists so
    // that cannot be forgotten, because a placeholder that reads as a working screen
    // is worse than an absent one.
    expect(PORTAL_NAV.filter((item) => item.implemented).map((item) => item.href)).toEqual([]);
  });

  it("has unique hrefs", () => {
    const hrefs = portalHrefs();
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});
