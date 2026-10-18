/**
 * Currency, precision and grouping tests.
 *
 * The API returns amounts as decimal strings precisely so that no float arithmetic happens
 * on the way to the screen. These tests hold that line: they fail if the console ever
 * parses an amount into a `number`, loses precision, or mixes two currencies in one total.
 */

import { describe, expect, it } from "vitest";

import {
  addDecimalStrings,
  compareDecimals,
  decimalBarPercent,
  formatCount,
  formatDecimalCurrency,
  groupRowsByCurrency,
  largestAmount,
  mergeSpendRows,
  summariseStatusAmounts,
  type AnalyticsOverview,
  type ExpenseStatus,
} from "../src/lib/analytics";
import { OVERVIEW_FIXTURE, spendRow } from "./analytics-fixtures";

type StatusAmount = AnalyticsOverview["status_amounts"][number];

function statusAmount(overrides: Partial<StatusAmount> & { status: ExpenseStatus }): StatusAmount {
  return {
    currency: "INR",
    claim_count: 1,
    amount_claim_count: 1,
    amount_total: "0.00",
    ...overrides,
  };
}

describe("decimal arithmetic", () => {
  it("adds decimal strings exactly where floating point would not", () => {
    // The motivating case, stated inline so the reason for this module is in the test.
    expect(0.1 + 0.2).not.toBe(0.3);
    expect(addDecimalStrings(["0.1", "0.2"])).toBe("0.3");
  });

  it("keeps precise lakh-and-paise sums exact", () => {
    expect(addDecimalStrings(["1000000.10", "0.20"])).toBe("1000000.30");
    expect(addDecimalStrings(["0.01", "0.02", "0.03"])).toBe("0.06");
  });

  it("aligns differing scales without truncating", () => {
    expect(addDecimalStrings(["1", "0.005"])).toBe("1.005");
    expect(addDecimalStrings(["10.5", "0.25"])).toBe("10.75");
  });

  it("handles negatives, which a refund would produce", () => {
    expect(addDecimalStrings(["100.00", "-30.50"])).toBe("69.50");
    expect(addDecimalStrings(["-5.00", "-0.25"])).toBe("-5.25");
  });

  it("reports no total as null rather than zero", () => {
    // Nothing to add and an unparseable amount must never be coerced into 0.
    expect(addDecimalStrings([])).toBeNull();
    expect(addDecimalStrings([null, undefined])).toBeNull();
    expect(addDecimalStrings(["12.00", null])).toBe("12.00");
    expect(addDecimalStrings(["12.00", "not-a-number"])).toBeNull();
  });

  it("compares amounts by value, not by string length", () => {
    expect(compareDecimals("9.00", "10.00")).toBe(-1);
    expect(compareDecimals("10.00", "10.00")).toBe(0);
    expect(compareDecimals("100.01", "100.00")).toBe(1);
    expect(compareDecimals("-1.00", "0.00")).toBe(-1);
  });

  it("scales a bar from the digits and clamps it to the axis", () => {
    expect(decimalBarPercent("50.00", "200.00")).toBe(25);
    expect(decimalBarPercent("200.00", "200.00")).toBe(100);
    expect(decimalBarPercent("500.00", "200.00")).toBe(100);
    expect(decimalBarPercent("0.00", "200.00")).toBe(0);
    expect(decimalBarPercent("5.00", "0.00")).toBe(0);
    expect(decimalBarPercent(null, "200.00")).toBe(0);
  });

  it("selects the largest amount within a currency, ignoring missing values", () => {
    expect(largestAmount(["1.00", null, "999.99", undefined, "12.00"])).toBe("999.99");
    expect(largestAmount([null, undefined])).toBeNull();
  });
});

describe("currency formatting", () => {
  it("formats INR with the Indian grouping a console user expects", () => {
    const formatted = formatDecimalCurrency("1234567.89", "INR", "en-IN");
    expect(formatted).toContain("12,34,567.89");
    // No ungrouped digits and no float rounding on the way out.
    expect(formatted).not.toContain("1234567");
  });

  it("formats each currency with its own symbol and default precision", () => {
    expect(formatDecimalCurrency("4200.5", "USD", "en-US")).toBe("$4,200.50");
    expect(formatDecimalCurrency("99", "EUR", "en-US")).toBe("€99.00");
  });

  it("preserves precision beyond the currency default", () => {
    expect(formatDecimalCurrency("1234.5678", "USD", "en-US")).toBe("$1,234.5678");
  });

  it("drops trailing zeros below the currency precision", () => {
    expect(formatDecimalCurrency("100.500", "USD", "en-US")).toBe("$100.50");
  });

  it("renders a missing amount as a dash, never as zero", () => {
    expect(formatDecimalCurrency(null, "INR")).toBe("—");
    expect(formatDecimalCurrency(undefined, "INR")).toBe("—");
  });

  it("still renders an amount whose currency was not recorded", () => {
    expect(formatDecimalCurrency("1000.00", null)).toBe("1000.00");
    expect(formatDecimalCurrency("1000.00", "")).toBe("1000.00");
  });

  it("formats counts as counts, never as money", () => {
    expect(formatCount(1234)).toBe("1,234");
    expect(formatCount(0)).toBe("0");
    expect(formatCount(1234567)).toBe("12,34,567");
  });
});

describe("currency separation", () => {
  it("keeps INR and USD in separate totals", () => {
    const summaries = summariseStatusAmounts(OVERVIEW_FIXTURE.status_amounts, ["approved"]);
    expect(summaries.map((summary) => summary.currency).sort()).toEqual(["INR", "USD"]);
    expect(summaries.find((summary) => summary.currency === "INR")?.total).toBe("1234567.89");
    expect(summaries.find((summary) => summary.currency === "USD")?.total).toBe("4200.50");
  });

  it("sums the selected statuses exactly, per currency", () => {
    const awaiting = summariseStatusAmounts(OVERVIEW_FIXTURE.status_amounts, [
      "submitted",
      "in_review",
    ]);
    expect(awaiting).toHaveLength(1);
    // 1000000.10 + 0.20 is the case floating point gets wrong.
    expect(awaiting[0]?.total).toBe("1000000.30");
    expect(awaiting[0]?.claimCount).toBe(57);
    expect(awaiting[0]?.amountClaimCount).toBe(55);
  });

  it("counts claims that carry no currency separately from real currencies", () => {
    const all = summariseStatusAmounts(OVERVIEW_FIXTURE.status_amounts, [
      "approved",
      "submitted",
      "in_review",
      "rejected",
      "draft",
    ]);
    const unrecorded = all.find((summary) => summary.currency === null);
    expect(unrecorded).toBeDefined();
    expect(unrecorded?.total).toBeNull();
    expect(unrecorded?.claimCount).toBe(11);
  });

  it("never reports a single combined total across currencies", () => {
    const combined = addDecimalStrings(["1234567.89", "4200.50"]);
    const summaries = summariseStatusAmounts(OVERVIEW_FIXTURE.status_amounts, ["approved"]);
    // The arithmetic is available but the console deliberately does not present it as one
    // figure: two currencies have two totals and no conversion rate exists anywhere.
    expect(combined).toBe("1238768.39");
    expect(summaries).toHaveLength(2);
  });

  it("returns nothing, not a zero, when no requested status had an amount", () => {
    const none = summariseStatusAmounts([statusAmount({ status: "draft", amount_total: null })], [
      "draft",
    ]);
    expect(none).toEqual([
      { currency: "INR", total: null, claimCount: 1, amountClaimCount: 1 },
    ]);
    expect(summariseStatusAmounts([], ["approved"])).toEqual([]);
  });

  it("groups returned rows by their currency", () => {
    const grouped = groupRowsByCurrency([
      spendRow({ currency: "INR" }),
      spendRow({ currency: "USD" }),
      spendRow({ currency: "INR" }),
    ]);
    expect(grouped.map((group) => group.currency).sort()).toEqual(["INR", "USD"]);
    expect(grouped.find((group) => group.currency === "INR")?.rows).toHaveLength(2);
  });
});

describe("pagination merging", () => {
  it("appends a later page without duplicating a group", () => {
    const pageOne = [
      spendRow({ bucket_start: "2026-07-01", currency: "INR", amount_total: "10.00" }),
      spendRow({ bucket_start: "2026-08-01", currency: "INR", amount_total: "20.00" }),
    ];
    const pageTwo = [
      // The offset cursor can repeat a shifted row; the later value wins and it appears once.
      spendRow({ bucket_start: "2026-08-01", currency: "INR", amount_total: "25.00" }),
      spendRow({ bucket_start: "2026-09-01", currency: "INR", amount_total: "30.00" }),
    ];

    const merged = mergeSpendRows(pageOne, pageTwo, "month");
    expect(merged).toHaveLength(3);
    expect(merged.filter((row) => row.bucket_start === "2026-08-01")).toHaveLength(1);
    expect(
      merged.find((row) => row.bucket_start === "2026-08-01")?.amount_total,
    ).toBe("25.00");
  });

  it("keeps the same grouping key in different currencies apart", () => {
    const merged = mergeSpendRows(
      [spendRow({ bucket_start: "2026-07-01", currency: "INR", amount_total: "10.00" })],
      [spendRow({ bucket_start: "2026-07-01", currency: "USD", amount_total: "5.00" })],
      "month",
    );
    expect(merged).toHaveLength(2);
  });

  it("keys a row by its grouping dimension, not by its label", () => {
    // Two employees can share a display name; the membership id is what distinguishes them.
    const merged = mergeSpendRows(
      [spendRow({ employee_membership_id: "a", employee_display_name: "Same Name" })],
      [spendRow({ employee_membership_id: "b", employee_display_name: "Same Name" })],
      "employee",
    );
    expect(merged).toHaveLength(2);
  });
});
