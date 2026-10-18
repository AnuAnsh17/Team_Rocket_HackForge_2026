/**
 * Fixtures for the analytics console tests.
 *
 * These objects mirror the JSON the backend returns for
 * `GET /api/v1/analytics/overview` and `GET /api/v1/analytics/spend`. They are typed with
 * the generated client's own response types, so a fixture that drifts from the contract
 * fails compilation instead of quietly testing a shape the API cannot produce.
 *
 * They exist ONLY as test input. Nothing in `src/` imports this module, so mocked figures
 * can never become the dashboard's operating data.
 */

import type { components } from "@proofline/api-client";

// The analytics response shapes are reached through the generated `components` map, exactly
// as `src/lib/analytics.ts` does: the client exports the schema, not hand-written DTOs.
type AnalyticsOverview = components["schemas"]["AnalyticsOverviewResponse"];
type AnalyticsSpendResponse = components["schemas"]["AnalyticsSpendResponse"];
type AnalyticsSpendRow = components["schemas"]["AnalyticsSpendRow"];
type ExpenseStatus = components["schemas"]["ExpenseStatus"];
type PageInfo = components["schemas"]["PageInfo"];

/** A period with activity in two currencies, sparse months and an unrecorded category. */
export const OVERVIEW_FIXTURE: AnalyticsOverview = {
  from_date: "2026-07-01",
  to_date: "2026-09-30",
  claim_count: 1234,
  claims_requiring_review: 57,
  claims_needing_information: 12,
  claims_missing_critical_fields: 8,
  claims_with_uncertain_critical_fields: 5,
  claims_with_unknown_transaction_date: 41,
  status_counts: [
    { status: "draft", claim_count: 11 },
    { status: "submitted", claim_count: 30 },
    { status: "needs_info", claim_count: 12 },
    { status: "in_review", claim_count: 27 },
    { status: "approved", claim_count: 900 },
    { status: "rejected", claim_count: 4 },
    { status: "withdrawn", claim_count: 250 },
  ],
  status_amounts: [
    { status: "approved", currency: "INR", claim_count: 900, amount_claim_count: 900, amount_total: "1234567.89" },
    { status: "approved", currency: "USD", claim_count: 3, amount_claim_count: 3, amount_total: "4200.50" },
    { status: "submitted", currency: "INR", claim_count: 30, amount_claim_count: 28, amount_total: "1000000.10" },
    { status: "in_review", currency: "INR", claim_count: 27, amount_claim_count: 27, amount_total: "0.20" },
    { status: "rejected", currency: "INR", claim_count: 4, amount_claim_count: 2, amount_total: "150.00" },
    { status: "draft", currency: null, claim_count: 11, amount_claim_count: 0, amount_total: null },
  ],
  by_department: [
    {
      department_id: "11111111-1111-4111-8111-111111111111",
      department_name: "Engineering",
      currency: "INR",
      claim_count: 800,
      amount_claim_count: 790,
      amount_total: "900000.10",
    },
    {
      department_id: "22222222-2222-4222-8222-222222222222",
      department_name: "Sales",
      currency: "INR",
      claim_count: 300,
      amount_claim_count: 300,
      amount_total: "1250000.00",
    },
    {
      department_id: null,
      department_name: null,
      currency: "INR",
      claim_count: 20,
      amount_claim_count: 10,
      amount_total: null,
    },
  ],
  by_office_location: [
    {
      office_location_id: "33333333-3333-4333-8333-333333333333",
      office_location_name: "Bengaluru",
      currency: "INR",
      claim_count: 900,
      amount_claim_count: 880,
      amount_total: "1500000.00",
    },
    {
      office_location_id: null,
      office_location_name: null,
      currency: "INR",
      claim_count: 10,
      amount_claim_count: 10,
      amount_total: "2500.00",
    },
  ],
  by_category: [
    { category: "travel", currency: "INR", claim_count: 700, amount_claim_count: 700, amount_total: "1400000.00" },
    { category: "meals", currency: "INR", claim_count: 300, amount_claim_count: 300, amount_total: "0.10" },
    { category: null, currency: "INR", claim_count: 40, amount_claim_count: 0, amount_total: null },
  ],
  monthly_totals: [
    { month: "2026-07-01", currency: "INR", claim_count: 400, amount_claim_count: 400, amount_total: "400000.00" },
    { month: "2026-08-01", currency: "INR", claim_count: 500, amount_claim_count: 500, amount_total: "1200000.00" },
    { month: "2026-09-01", currency: "USD", claim_count: 2, amount_claim_count: 2, amount_total: "2500.00" },
  ],
};

/** A period with no dated claims at all, but with undated claims outside it. */
export const EMPTY_OVERVIEW_FIXTURE: AnalyticsOverview = {
  ...OVERVIEW_FIXTURE,
  claim_count: 0,
  claims_requiring_review: 0,
  claims_needing_information: 0,
  claims_missing_critical_fields: 0,
  claims_with_uncertain_critical_fields: 0,
  claims_with_unknown_transaction_date: 41,
  status_counts: (
    [
      "draft",
      "submitted",
      "needs_info",
      "in_review",
      "approved",
      "rejected",
      "withdrawn",
    ] as ExpenseStatus[]
  ).map((status) => ({ status, claim_count: 0 })),
  status_amounts: [],
  by_department: [],
  by_office_location: [],
  by_category: [],
  monthly_totals: [],
};

export function spendRow(overrides: Partial<AnalyticsSpendRow> = {}): AnalyticsSpendRow {
  return {
    currency: "INR",
    claim_count: 1,
    amount_claim_count: 1,
    amount_total: "1.00",
    bucket_start: null,
    category: null,
    department_id: null,
    department_name: null,
    employee_membership_id: null,
    employee_display_name: null,
    office_location_id: null,
    office_location_name: null,
    status: null,
    ...overrides,
  };
}

export function pageInfo(overrides: Partial<PageInfo> = {}): PageInfo {
  return { limit: 200, next_cursor: null, total: null, ...overrides };
}

export function spendResponse(overrides: Partial<AnalyticsSpendResponse> = {}): AnalyticsSpendResponse {
  return {
    from_date: "2026-07-01",
    to_date: "2026-09-30",
    group_by: "month",
    claims_with_unknown_transaction_date: 3,
    results: {
      items: [
        spendRow({ bucket_start: "2026-07-01", currency: "INR", claim_count: 40, amount_claim_count: 39, amount_total: "40000.00" }),
        spendRow({ bucket_start: "2026-08-01", currency: "INR", claim_count: 50, amount_claim_count: 50, amount_total: "120000.50" }),
      ],
      page: pageInfo({ total: 2 }),
    },
    ...overrides,
  };
}
