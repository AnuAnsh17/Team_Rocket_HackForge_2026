import { readFileSync } from "node:fs";
import { URL, fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Wording is a product requirement for an expense tool, not polish.
 *
 * Reads the component source, which is the cheapest reliable way to keep the rule true as
 * the copy grows.
 */
const uiSource = readFileSync(
  fileURLToPath(new URL("../src/components/ui.tsx", import.meta.url)),
  "utf-8",
);

describe("mobile employee-facing wording", () => {
  it("never uses accusatory language", () => {
    const forbidden = [
      "fraud",
      "fraudulent",
      "violation",
      "suspicious",
      "guilty",
      "misconduct",
      "abuse",
      "dishonest",
      "cheat",
    ];
    const lowered = uiSource.toLowerCase();
    for (const word of forbidden) {
      expect(lowered, `"${word}" must not appear in employee-facing copy`).not.toContain(word);
    }
  });

  it("presents a possible duplicate as a possibility, not a finding", () => {
    expect(uiSource).toContain("might have been submitted twice");
    expect(uiSource).toContain("nothing is assumed");
  });

  it("says a policy problem is about the claim, not the person", () => {
    expect(uiSource).toContain("This claim does not meet the policy");
  });
});
