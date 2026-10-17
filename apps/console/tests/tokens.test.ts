import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { COLOR_TOKENS, SPACING_TOKENS } from "../src/lib/tokens";

const stylesheet = readFileSync(
  fileURLToPath(new URL("../app/globals.css", import.meta.url)),
  "utf-8",
);

describe("design tokens", () => {
  it("declares every TypeScript colour token in the stylesheet", () => {
    for (const [name, cssVariable] of Object.entries(COLOR_TOKENS)) {
      expect(stylesheet, `${name} (${cssVariable}) is missing from globals.css`).toContain(
        `${cssVariable}:`,
      );
    }
  });

  it("declares every TypeScript spacing token in the stylesheet", () => {
    for (const cssVariable of Object.values(SPACING_TOKENS)) {
      expect(stylesheet).toContain(`${cssVariable}:`);
    }
  });

  it("has a colour for every tri-state rule result, including UNKNOWN", () => {
    // UNKNOWN must be visually distinguishable, not muted: it is the correct answer
    // whenever evidence is missing and must never read as a pass.
    expect(stylesheet).toContain("--color-result-unknown:");
    expect(stylesheet).toContain("--color-result-pass:");
    expect(stylesheet).toContain("--color-result-fail:");
  });

  it("has no colour token implying fraud or risk", () => {
    const forbidden = ["fraud", "risk", "guilt", "suspicious"];
    for (const variable of Object.values(COLOR_TOKENS)) {
      expect(forbidden.some((word) => variable.includes(word))).toBe(false);
    }
  });
});
