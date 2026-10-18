/**
 * Request-parameter and period tests for the analytics console.
 *
 * These assert the console asks the backend for exactly what the contract accepts: the
 * documented filters, the documented grouping dimensions, an inclusive period, and a page
 * size within the documented ceiling. A parameter the API does not implement is a request
 * that silently returns the wrong numbers, so it is checked explicitly.
 */

import { describe, expect, it } from "vitest";

import {
  ANALYTICS_GROUPS,
  EMPTY_FILTERS,
  EXPENSE_STATUSES,
  SPEND_PAGE_LIMIT,
  buildFilterOptionsQuery,
  buildOverviewQuery,
  buildSpendQuery,
  describeSelection,
  initialDateRange,
  isUuid,
  requiresOrganizationAnalytics,
  sameSelection,
  validateFilters,
  validateRange,
  type AnalyticsFilters,
} from "../src/lib/analytics";

/** Every query parameter the two endpoints document. */
const OVERVIEW_PARAMETERS = new Set([
  "from",
  "to",
  "department_id",
  "office_location_id",
  "employee_membership_id",
  "category",
  "currency",
  "status",
]);
const SPEND_PARAMETERS = new Set([...OVERVIEW_PARAMETERS, "group_by", "limit", "cursor"]);

const RANGE = { from: "2026-07-01", to: "2026-09-30" };

const FULL_FILTERS: AnalyticsFilters = {
  departmentId: "11111111-1111-4111-8111-111111111111",
  officeLocationId: "33333333-3333-4333-8333-333333333333",
  employeeMembershipId: "44444444-4444-4444-8444-444444444444",
  category: "travel",
  currency: "INR",
  status: "approved",
};

describe("analytics request parameters", () => {
  it("sends the inclusive period as the two documented date parameters", () => {
    const query = buildOverviewQuery(RANGE, EMPTY_FILTERS);
    expect(query.from).toBe("2026-07-01");
    expect(query.to).toBe("2026-09-30");
    expect(Object.keys(query).sort()).toEqual(["from", "to"]);
  });

  it("maps every supported filter to its documented parameter name", () => {
    expect(buildOverviewQuery(RANGE, FULL_FILTERS)).toEqual({
      from: "2026-07-01",
      to: "2026-09-30",
      department_id: FULL_FILTERS.departmentId,
      office_location_id: FULL_FILTERS.officeLocationId,
      employee_membership_id: FULL_FILTERS.employeeMembershipId,
      category: "travel",
      currency: "INR",
      status: "approved",
    });
  });

  it("omits a filter entirely instead of sending an empty value", () => {
    // A blank UUID is a 422 on the backend, so "no filter" has to mean "absent".
    const query = buildOverviewQuery(RANGE, { ...EMPTY_FILTERS, category: "" });
    expect("department_id" in query).toBe(false);
    expect("currency" in query).toBe(false);
    expect("status" in query).toBe(false);
    expect("category" in query).toBe(false);
  });

  it("only ever emits parameters the contract documents", () => {
    for (const key of Object.keys(buildOverviewQuery(RANGE, FULL_FILTERS))) {
      expect(OVERVIEW_PARAMETERS.has(key), `overview parameter ${key} is not in the contract`).toBe(
        true,
      );
    }
    for (const key of Object.keys(buildSpendQuery(RANGE, FULL_FILTERS, "employee"))) {
      expect(SPEND_PARAMETERS.has(key), `spend parameter ${key} is not in the contract`).toBe(true);
    }
  });

  it("sends the six implemented grouping dimensions and no others", () => {
    expect(ANALYTICS_GROUPS).toEqual([
      "month",
      "department",
      "location",
      "category",
      "employee",
      "status",
    ]);
    for (const groupBy of ANALYTICS_GROUPS) {
      expect(buildSpendQuery(RANGE, EMPTY_FILTERS, groupBy).group_by).toBe(groupBy);
    }
  });

  it("uses a page size within the contract's ceiling and requests no cursor for page one", () => {
    const first = buildSpendQuery(RANGE, EMPTY_FILTERS, "month");
    expect(first.limit).toBe(SPEND_PAGE_LIMIT);
    expect(SPEND_PAGE_LIMIT).toBeLessThanOrEqual(200);
    expect("cursor" in first).toBe(false);

    const next = buildSpendQuery(RANGE, EMPTY_FILTERS, "month", "opaque-cursor");
    expect(next.cursor).toBe("opaque-cursor");
  });

  it("asks for the whole period - without the current filters - when loading option lists", () => {
    // Option catalogues must not be narrowed by the filter the user is choosing from.
    expect(buildFilterOptionsQuery(RANGE)).toEqual({ from: "2026-07-01", to: "2026-09-30" });
  });

  it("knows which dimensions the backend gates behind analytics:read_org", () => {
    expect(requiresOrganizationAnalytics("employee")).toBe(true);
    for (const groupBy of ANALYTICS_GROUPS.filter((group) => group !== "employee")) {
      expect(requiresOrganizationAnalytics(groupBy)).toBe(false);
    }
  });
});

describe("period selection", () => {
  it("starts with a three-month period ending today, not a fixed demo window", () => {
    const range = initialDateRange(new Date(2026, 9, 18));
    expect(range).toEqual({ from: "2026-08-01", to: "2026-10-18" });
  });

  it("builds dates from local calendar parts so the boundary day cannot shift", () => {
    // 00:30 local on the first of a month belongs to that month, whatever UTC says.
    const range = initialDateRange(new Date(2026, 0, 1, 0, 30));
    expect(range.from).toBe("2025-11-01");
    expect(range.to).toBe("2026-01-01");
  });

  it("rejects an inverted or incomplete period before any request is sent", () => {
    expect(validateRange({ from: "2026-09-30", to: "2026-07-01" })).toMatch(/on or before/);
    expect(validateRange({ from: "", to: "2026-07-01" })).toMatch(/both an inclusive/);
    expect(validateRange({ from: "2026-02-30", to: "2026-07-01" })).toMatch(/complete/);
    expect(validateRange(RANGE)).toBeNull();
  });

  it("treats both boundary dates as inside the period", () => {
    // The period is inclusive, so a claim on either boundary is requested.
    const query = buildOverviewQuery({ from: "2026-07-01", to: "2026-07-01" }, EMPTY_FILTERS);
    expect(query.from).toBe(query.to);
    expect(validateRange({ from: "2026-07-01", to: "2026-07-01" })).toBeNull();
  });
});

describe("filter validation", () => {
  it("accepts an empty filter set and a complete membership id", () => {
    expect(validateFilters(EMPTY_FILTERS)).toBeNull();
    expect(validateFilters(FULL_FILTERS)).toBeNull();
    expect(isUuid(FULL_FILTERS.employeeMembershipId)).toBe(true);
  });

  it("refuses a partial membership id rather than sending it", () => {
    const message = validateFilters({ ...EMPTY_FILTERS, employeeMembershipId: "4444" });
    expect(message).toMatch(/complete membership UUID/);
  });

  it("refuses a department or location value the API did not return", () => {
    expect(validateFilters({ ...EMPTY_FILTERS, departmentId: "not-a-uuid" })).toMatch(
      /Department must be selected/,
    );
    expect(validateFilters({ ...EMPTY_FILTERS, officeLocationId: "sales" })).toMatch(
      /Office location must be selected/,
    );
  });

  it("uses the canonical workflow statuses only", () => {
    expect(EXPENSE_STATUSES).toEqual([
      "draft",
      "submitted",
      "needs_info",
      "in_review",
      "approved",
      "rejected",
      "withdrawn",
    ]);
    expect(buildOverviewQuery(RANGE, { ...EMPTY_FILTERS, status: "approved" }).status).toBe(
      "approved",
    );
  });
});

describe("naming the selection a stale result belongs to", () => {
  it("describes the period, the grouping and the filters that were actually requested", () => {
    expect(describeSelection(buildOverviewQuery(RANGE, EMPTY_FILTERS))).toBe(
      "period 2026-07-01 to 2026-09-30 · no filters",
    );
    expect(describeSelection(buildSpendQuery(RANGE, EMPTY_FILTERS, "department"), "department")).toBe(
      "period 2026-07-01 to 2026-09-30 · grouped by department · no filters",
    );
    const filtered = describeSelection(
      buildOverviewQuery(RANGE, { ...EMPTY_FILTERS, category: "travel", status: "approved" }),
    );
    expect(filtered).toContain("filtered by category travel, status approved");
  });

  it("recognizes an identical selection and rejects a changed one", () => {
    const first = buildSpendQuery(RANGE, EMPTY_FILTERS, "month");
    expect(sameSelection(first, buildSpendQuery(RANGE, EMPTY_FILTERS, "month"))).toBe(true);
    expect(sameSelection(first, buildSpendQuery(RANGE, EMPTY_FILTERS, "employee"))).toBe(false);
    expect(sameSelection(first, buildSpendQuery({ ...RANGE, to: "2026-09-29" }, EMPTY_FILTERS, "month"))).toBe(
      false,
    );
    expect(sameSelection(null, first)).toBe(false);
    expect(sameSelection(first, undefined)).toBe(false);
  });
});
