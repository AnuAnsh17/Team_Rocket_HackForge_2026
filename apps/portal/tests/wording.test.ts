import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Wording is a product requirement for an expense tool, not polish.
 *
 * An employee reading a status is in a slightly anxious position. Copy that implies
 * suspicion changes how people respond to a correction request, and the product does not
 * assert wrongdoing - so it must not have the vocabulary for it either.
 *
 * These assertions read the component source, which is the cheapest reliable way to keep
 * the rule true as the copy grows.
 */
const uiSource = readFileSync(
  fileURLToPath(new URL("../src/components/ui.tsx", import.meta.url)),
  "utf-8",
);

const EMPLOYEE_FACING_COPY = uiSource.slice(uiSource.indexOf("STATE_COPY"));

describe("employee-facing wording", () => {
  it("never uses accusatory language", () => {
    const forbidden = [
      "fraud",
      "fraudulent",
      "violation",
      "violated",
      "suspicious",
      "guilty",
      "misconduct",
      "abuse",
      "dishonest",
      "cheat",
      "liar",
    ];
    const lowered = uiSource.toLowerCase();
    for (const word of forbidden) {
      expect(lowered, `"${word}" must not appear in employee-facing copy`).not.toContain(word);
    }
  });

  it("describes the four states with distinct wording", () => {
    const labels = [
      ...EMPLOYEE_FACING_COPY.matchAll(/label: "([^"]+)"/g),
    ].map((match) => match[1]);
    expect(labels.length).toBe(4);
    expect(new Set(labels).size).toBe(4);
  });

  it("presents a possible duplicate as a possibility, not a finding", () => {
    // The exact phrase matters: it tells the employee that a person will check, and that
    // nothing has been concluded. Changing it should be a deliberate decision.
    expect(EMPLOYEE_FACING_COPY).toContain("might have been submitted twice");
    expect(EMPLOYEE_FACING_COPY).toContain("nothing is assumed");
  });

  it("says a policy problem is about the claim, not the person", () => {
    expect(EMPLOYEE_FACING_COPY).toContain("This claim does not meet the policy");
  });
});
