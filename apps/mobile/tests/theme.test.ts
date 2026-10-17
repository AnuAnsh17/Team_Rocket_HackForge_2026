import { describe, expect, it } from "vitest";

import { RESULT_LABELS, STATUS_LABELS, resultColor, statusColor } from "../src/theme";

describe("mobile theme vocabulary", () => {
  it("describes a rejected claim as not reimbursed", () => {
    // A rejected claim means the expense was not reimbursed, not that the employee did
    // anything wrong. The wording is a product requirement.
    expect(STATUS_LABELS.rejected).toBe("Not reimbursed");
  });

  it("treats UNKNOWN as a first-class result with its own meaning", () => {
    expect(RESULT_LABELS.UNKNOWN).toBe("We could not confirm this yet");
    // It must be visually distinguishable, not rendered as a muted or disabled state.
    expect(resultColor("UNKNOWN")).not.toBe(resultColor("PASS"));
    expect(resultColor("UNKNOWN")).not.toBe(resultColor("FAIL"));
  });

  it("gives every known status a distinct colour", () => {
    const known = ["draft", "submitted", "needs_info", "in_review", "approved", "rejected"];
    const colours = known.map((status) => statusColor(status));
    // draft and withdrawn may share a neutral colour; the workflow states must not.
    expect(new Set(colours).size).toBe(known.length);
  });

  it("falls back to a neutral colour for an unrecognised status", () => {
    expect(statusColor("something_new")).toBe(statusColor("unknown-status"));
  });
});
