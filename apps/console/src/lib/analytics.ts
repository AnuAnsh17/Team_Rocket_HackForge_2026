/**
 * Finance/Admin analytics access layer.
 *
 * This module is the console's single source of truth for reading
 * `GET /api/v1/analytics/overview` and `GET /api/v1/analytics/spend`. Every type here
 * comes from the generated `@proofline/api-client` schema, so a backend contract change
 * breaks compilation instead of silently producing a dashboard that disagrees with the
 * API.
 *
 * Three rules govern this file:
 *
 * 1. NO BUSINESS LOGIC. The backend decides what a status means, which claims are inside
 *    the period, and what a currency's total is. This module builds request parameters
 *    and formats returned values. It never re-derives a metric.
 * 2. NO FLOAT MONEY. Amounts arrive as decimal strings and stay decimal strings. The few
 *    places the console genuinely has to combine server-returned sums (for example
 *    "awaiting review" = submitted + in_review) do it with exact BigInt arithmetic over
 *    the digits, never with `Number`.
 * 3. NO INVENTED FIELDS. If the contract does not return a value, the value does not
 *    exist here. `loadSpendPage` returns exactly one page plus the API's own pagination
 *    envelope, so no caller can mistake a first page for the whole dataset.
 */

import {
  ApiError,
  unwrap,
  type components,
  type paths,
  type ProoflineClient,
} from "@proofline/api-client";

// ---------------------------------------------------------------------------
// Generated contract types (never hand-written DTOs)
// ---------------------------------------------------------------------------

export type AnalyticsOverview = components["schemas"]["AnalyticsOverviewResponse"];
export type AnalyticsSpendResponse = components["schemas"]["AnalyticsSpendResponse"];
export type AnalyticsSpendRow = components["schemas"]["AnalyticsSpendRow"];
export type AnalyticsGroupBy = components["schemas"]["AnalyticsGroupBy"];
export type ExpenseStatus = components["schemas"]["ExpenseStatus"];
export type PageInfo = components["schemas"]["PageInfo"];

export type OverviewQuery = paths["/api/v1/analytics/overview"]["get"]["parameters"]["query"];
export type SpendQuery = paths["/api/v1/analytics/spend"]["get"]["parameters"]["query"];

/** The six grouping dimensions the endpoint implements, in the contract's order. */
export const ANALYTICS_GROUPS: readonly AnalyticsGroupBy[] = [
  "month",
  "department",
  "location",
  "category",
  "employee",
  "status",
];

/** Every canonical workflow status. `status_counts` always returns all of them. */
export const EXPENSE_STATUSES: readonly ExpenseStatus[] = [
  "draft",
  "submitted",
  "needs_info",
  "in_review",
  "approved",
  "rejected",
  "withdrawn",
];

/**
 * Page size for the spend explorer.
 *
 * 200 is the backend's documented ceiling (`app/core/pagination.py: MAX_LIMIT`), so each
 * page is as complete as the contract allows and the fewest requests are needed to show a
 * realistic number of groups.
 */
export const SPEND_PAGE_LIMIT = 200;

/**
 * Grouping dimensions the backend gates behind `analytics:read_org`.
 *
 * Mirrors `analytics_service.require_analytics_access(employee_level=...)`. It shapes a
 * hint in the UI only; the backend still refuses the request.
 */
export function requiresOrganizationAnalytics(groupBy: AnalyticsGroupBy): boolean {
  return groupBy === "employee";
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

export interface DateRange {
  from: string;
  to: string;
}

export interface AnalyticsFilters {
  departmentId: string;
  officeLocationId: string;
  employeeMembershipId: string;
  category: string;
  currency: string;
  status: ExpenseStatus | "";
}

export const EMPTY_FILTERS: AnalyticsFilters = {
  departmentId: "",
  officeLocationId: "",
  employeeMembershipId: "",
  category: "",
  currency: "",
  status: "",
};

/**
 * The initial period: the current month plus the two preceding months, ending today.
 *
 * Deliberately relative to "now" rather than a fixed demo window. Dates are built from
 * local calendar parts, so a reviewer in UTC+05:30 sees the range they expect instead of
 * one shifted by timezone serialization.
 */
export function initialDateRange(now: Date = new Date()): DateRange {
  const start = new Date(now.getFullYear(), now.getMonth() - 2, 1);
  return { from: toIsoDate(start), to: toIsoDate(now) };
}

export function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isIsoDate(value: string): boolean {
  if (!ISO_DATE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function isUuid(value: string): boolean {
  return UUID.test(value);
}

/**
 * Client-side mirror of the backend's own validation.
 *
 * The API rejects an inverted range (`422`) and rejects a department, location or
 * membership id that is not part of the actor's organization. Checking the obvious cases
 * here avoids a wasted round trip and an error screen; the server stays the authority and
 * its refusal is still rendered when it disagrees.
 */
export function validateRange(range: DateRange): string | null {
  if (!range.from || !range.to) return "Choose both an inclusive start date and an end date.";
  if (!isIsoDate(range.from) || !isIsoDate(range.to)) return "Dates must be complete (YYYY-MM-DD).";
  if (range.from > range.to) return "The start date must be on or before the end date.";
  return null;
}

export function validateFilters(filters: AnalyticsFilters): string | null {
  if (filters.employeeMembershipId && !isUuid(filters.employeeMembershipId)) {
    return "Employee membership must be a complete membership UUID.";
  }
  if (filters.departmentId && !isUuid(filters.departmentId)) {
    return "Department must be selected from the list the API returned.";
  }
  if (filters.officeLocationId && !isUuid(filters.officeLocationId)) {
    return "Office location must be selected from the list the API returned.";
  }
  return null;
}

/**
 * Convert UI filter state into the exact query the contract accepts.
 *
 * An empty string means "no filter", so the parameter is omitted entirely rather than sent
 * as `department_id=`. The API validates a present-but-empty UUID as invalid, so a blank
 * parameter would turn an unfiltered view into a 422.
 */
export function buildOverviewQuery(range: DateRange, filters: AnalyticsFilters): OverviewQuery {
  const query: OverviewQuery = { from: range.from, to: range.to };
  if (filters.departmentId) query.department_id = filters.departmentId;
  if (filters.officeLocationId) query.office_location_id = filters.officeLocationId;
  if (filters.employeeMembershipId) query.employee_membership_id = filters.employeeMembershipId;
  if (filters.category) query.category = filters.category;
  if (filters.currency) query.currency = filters.currency;
  if (filters.status) query.status = filters.status;
  return query;
}

export function buildSpendQuery(
  range: DateRange,
  filters: AnalyticsFilters,
  groupBy: AnalyticsGroupBy,
  cursor: string | null = null,
): SpendQuery {
  const query: SpendQuery = {
    ...buildOverviewQuery(range, filters),
    group_by: groupBy,
    limit: SPEND_PAGE_LIMIT,
  };
  if (cursor) query.cursor = cursor;
  return query;
}

/**
 * The query behind the filter option lists.
 *
 * Option catalogues come from the same endpoint with the user's filters left off. A list
 * narrowed by the very filter it is choosing could never widen again. `from`/`to` are
 * still sent because the contract requires them.
 */
export function buildFilterOptionsQuery(range: DateRange): OverviewQuery {
  return { from: range.from, to: range.to };
}

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

export async function loadOverview(
  api: ProoflineClient,
  query: OverviewQuery,
  signal?: AbortSignal,
): Promise<AnalyticsOverview> {
  return unwrap(api.GET("/api/v1/analytics/overview", { params: { query }, signal }));
}

export async function loadFilterOptions(
  api: ProoflineClient,
  range: DateRange,
  signal?: AbortSignal,
): Promise<AnalyticsOverview> {
  return loadOverview(api, buildFilterOptionsQuery(range), signal);
}

export interface SpendPage {
  rows: AnalyticsSpendRow[];
  /** The API's own pagination envelope, passed through unmodified. */
  page: PageInfo;
  /** Claims matching the filters but lacking a transaction date; excluded from groups. */
  unknownDateCount: number;
  groupBy: AnalyticsGroupBy;
  fromDate: string;
  toDate: string;
}

/**
 * Fetch exactly one page of spend groups.
 *
 * Deliberately NOT a fetch-everything helper. Following the cursor in a loop would hide
 * the dataset's real size, turn one filter change into an unbounded number of requests,
 * and leave the UI unable to state how much it had actually shown.
 */
export async function loadSpendPage(
  api: ProoflineClient,
  query: SpendQuery,
  signal?: AbortSignal,
): Promise<SpendPage> {
  const response: AnalyticsSpendResponse = await unwrap(
    api.GET("/api/v1/analytics/spend", { params: { query }, signal }),
  );
  return {
    rows: response.results.items,
    page: response.results.page,
    unknownDateCount: response.claims_with_unknown_transaction_date,
    groupBy: response.group_by,
    fromDate: response.from_date,
    toDate: response.to_date,
  };
}

/**
 * A stable description of what a request asked for, for labelling stale results.
 *
 * When a newer request fails, the console keeps the last successful response on screen
 * rather than blanking the page. That is only honest if the screen says which selection
 * those figures belong to, because the controls have already moved on.
 */
export function describeSelection(
  query: { from: string; to: string } & Partial<Omit<OverviewQuery, "from" | "to">>,
  groupBy?: AnalyticsGroupBy,
): string {
  const filters: string[] = [];
  if (query.department_id) filters.push("department");
  if (query.office_location_id) filters.push("office location");
  if (query.employee_membership_id) filters.push("employee");
  if (query.category) filters.push(`category ${query.category}`);
  if (query.currency) filters.push(`currency ${query.currency}`);
  if (query.status) filters.push(`status ${query.status}`);

  const parts = [`period ${query.from} to ${query.to}`];
  if (groupBy) parts.push(`grouped by ${groupBy}`);
  parts.push(filters.length > 0 ? `filtered by ${filters.join(", ")}` : "no filters");
  return parts.join(" · ");
}

/** Whether two requests asked for exactly the same thing. */
export function sameSelection(
  left: OverviewQuery | SpendQuery | null | undefined,
  right: OverviewQuery | SpendQuery | null | undefined,
): boolean {
  if (!left || !right) return false;
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const key of keys) {
    const a = (left as Record<string, unknown>)[key];
    const b = (right as Record<string, unknown>)[key];
    if ((a ?? null) !== (b ?? null)) return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Stale-response prevention
// ---------------------------------------------------------------------------

/**
 * A monotonically increasing request token.
 *
 * Every request captures a token when it starts and checks it before writing state, so a
 * slower earlier request cannot overwrite the result of a newer one - the failure that
 * makes a dashboard show figures for filters the user has already changed. AbortController
 * cancels the in-flight request; this guard covers the response that is already in the
 * microtask queue and can no longer be cancelled.
 */
export function createRequestGate(): {
  begin: () => number;
  isCurrent: (token: number) => boolean;
} {
  let latest = 0;
  return {
    begin: () => {
      latest += 1;
      return latest;
    },
    isCurrent: (token: number) => token === latest,
  };
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export type AnalyticsErrorKind =
  | "unauthenticated"
  | "forbidden"
  | "not-found"
  | "validation"
  | "not-implemented"
  | "server"
  | "network"
  | "unknown";

export interface AnalyticsError {
  kind: AnalyticsErrorKind;
  title: string;
  message: string;
  /** Backend request id when the failure carried one: the only support handle we get. */
  requestId: string | null;
}

/**
 * Turn a thrown value into something a reviewer can act on.
 *
 * A failed request must never become a chart of zeros, so every failure ends up as a
 * stated cause. 401 and 403 stay distinct because the API distinguishes them: 401 means
 * there is no identity at all, 403 means the identity is valid but not permitted. Telling
 * a forbidden caller to sign in again would be wrong advice that hides the refusal.
 */
export function describeError(error: unknown): AnalyticsError {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return {
        kind: "unauthenticated",
        title: "No authenticated identity",
        message:
          "The backend did not receive an authenticated caller. Start a supported sign-in session, or in local demo mode set an authorized demo actor id in the console header.",
        requestId: error.requestId,
      };
    }
    if (error.status === 403 || error.isForbidden) {
      return {
        kind: "forbidden",
        title: "Analytics access denied",
        message:
          "The backend refused this request for the current actor. Analytics needs organization-scoped expense read access plus an analytics permission; employee-level grouping or filtering additionally needs analytics:read_org. The role preview in the header grants nothing.",
        requestId: error.requestId,
      };
    }
    if (error.status === 404) {
      return {
        kind: "not-found",
        title: "Analytics route is not served here",
        message:
          "The configured API did not find this route. Check that the console points at a backend running the analytics API branch.",
        requestId: error.requestId,
      };
    }
    if (error.status === 422) {
      return {
        kind: "validation",
        title: "The API rejected these filter values",
        message: `${error.message} Filters must belong to the actor's own organization.`,
        requestId: error.requestId,
      };
    }
    if (error.status === 501) {
      return {
        kind: "not-implemented",
        title: "Not implemented by this backend",
        message: error.message,
        requestId: error.requestId,
      };
    }
    if (error.status >= 500) {
      return {
        kind: "server",
        title: "The analytics service failed",
        message: `${error.message} This section shows nothing rather than a partial or zeroed figure.`,
        requestId: error.requestId,
      };
    }
    return {
      kind: "unknown",
      title: "Analytics could not be loaded",
      message: error.message,
      requestId: error.requestId,
    };
  }

  return {
    kind: "network",
    title: "Backend unreachable",
    message:
      "The analytics service did not respond. Check the configured API address and whether the backend is running, then retry.",
    requestId: null,
  };
}

// ---------------------------------------------------------------------------
// Exact decimal arithmetic (strings only - never Number, never float)
// ---------------------------------------------------------------------------

interface Decimal {
  negative: boolean;
  integer: string;
  fraction: string;
}

/** Parse a `^-?\d+(\.\d+)?$` decimal string, or return null when it is not one. */
export function parseDecimal(value: string): Decimal | null {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) return null;
  return {
    negative: match[1] === "-",
    integer: match[2] ?? "0",
    fraction: match[3] ?? "",
  };
}

function scaledDigits(value: Decimal, scale: number): bigint {
  return BigInt(value.integer + value.fraction.padEnd(scale, "0"));
}

function signedDigits(value: Decimal, scale: number): bigint {
  const digits = scaledDigits(value, scale);
  return value.negative ? -digits : digits;
}

function renderScaled(total: bigint, scale: number): string {
  const negative = total < 0n;
  const digits = (negative ? -total : total).toString().padStart(scale + 1, "0");
  const integer = scale > 0 ? digits.slice(0, -scale) : digits;
  const fraction = scale > 0 ? digits.slice(-scale) : "";
  return `${negative ? "-" : ""}${integer}${scale > 0 ? `.${fraction}` : ""}`;
}

/**
 * Add decimal strings exactly.
 *
 * Returns `null` when there is nothing to add, and `null` when any input is not a decimal
 * string: an unparseable amount must surface as "unknown" rather than being silently
 * dropped from a total.
 */
export function addDecimalStrings(values: Array<string | null | undefined>): string | null {
  const present = values.filter((value): value is string => value !== null && value !== undefined);
  if (present.length === 0) return null;

  const parsed = present.map(parseDecimal);
  if (parsed.some((value) => value === null)) return null;
  const decimals = parsed as Decimal[];

  const scale = Math.max(...decimals.map((value) => value.fraction.length));
  const total = decimals.reduce((sum, value) => sum + signedDigits(value, scale), 0n);
  return renderScaled(total, scale);
}

/** Compare two decimal strings: -1, 0 or 1. Unparseable input compares equal. */
export function compareDecimals(left: string, right: string): number {
  const a = parseDecimal(left);
  const b = parseDecimal(right);
  if (!a || !b) return 0;
  const scale = Math.max(a.fraction.length, b.fraction.length);
  const leftValue = signedDigits(a, scale);
  const rightValue = signedDigits(b, scale);
  if (leftValue < rightValue) return -1;
  return leftValue > rightValue ? 1 : 0;
}

/**
 * Bar width as a percentage of the largest value in the same currency.
 *
 * A chart presents exact values, so the width comes from the digits and is clamped to
 * 0-100. Values are only ever compared within one currency, because comparing across
 * currencies is meaningless and summing them is worse.
 */
export function decimalBarPercent(
  value: string | null | undefined,
  maximum: string | null | undefined,
): number {
  if (value == null || maximum == null) return 0;
  const amount = parseDecimal(value);
  const ceiling = parseDecimal(maximum);
  if (!amount || !ceiling || ceiling.negative || amount.negative) return 0;

  const scale = Math.max(amount.fraction.length, ceiling.fraction.length);
  const numerator = scaledDigits(amount, scale);
  const denominator = scaledDigits(ceiling, scale);
  if (denominator === 0n) return 0;

  const percentage = (numerator * 100n) / denominator;
  return Number(percentage > 100n ? 100n : percentage);
}

/**
 * Format a decimal string as currency without ever converting it to a float.
 *
 * `Intl.NumberFormat` decides grouping, symbol placement and the currency's own default
 * precision; the digit string decides the value. Precision beyond the currency's default
 * is preserved rather than rounded away, and trailing zeros below it are dropped so that
 * `100.500` INR renders as ₹100.50.
 */
export function formatDecimalCurrency(
  value: string | null | undefined,
  currency: string | null | undefined,
  locale = "en-IN",
): string {
  if (value === null || value === undefined) return "—";
  const parsed = parseDecimal(value);
  if (!parsed) return currency ? `${value} ${currency}` : value;
  if (!currency) return value;

  try {
    const currencyDigits =
      new Intl.NumberFormat(locale, { style: "currency", currency }).resolvedOptions()
        .maximumFractionDigits ?? 2;
    // Trailing zeros below the currency's own precision are presentation noise, not value:
    // `100.500` USD is `$100.50`. Precision above it is kept, so nothing is rounded away.
    const significantFraction = parsed.fraction.replace(/0+$/, "");
    const scale = Math.max(currencyDigits, significantFraction.length);

    const parts = new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: scale,
      maximumFractionDigits: scale,
    }).formatToParts(parsed.negative ? -1 : 1);

    const groupedInteger = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(
      BigInt(parsed.integer),
    );
    const fraction = parsed.fraction.slice(0, scale).padEnd(scale, "0");

    return parts
      .map((part) => {
        if (part.type === "integer") return groupedInteger;
        if (part.type === "fraction") return fraction;
        return part.value;
      })
      .join("");
  } catch {
    // An unrecognized ISO code must still render, just without a symbol.
    return `${value} ${currency}`;
  }
}

/** Group a count. Counts are not money and are never rendered as currency. */
export function formatCount(value: number, locale = "en-IN"): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}

// ---------------------------------------------------------------------------
// Presentation helpers over returned rows (no re-derivation of backend metrics)
// ---------------------------------------------------------------------------

/**
 * Split returned rows by currency.
 *
 * The API returns one row per (grouping key, currency). Rendering a chart therefore means
 * rendering one series per currency, never one combined series.
 */
export function groupRowsByCurrency<T extends { currency?: string | null }>(
  rows: readonly T[],
): Array<{ currency: string | null; rows: T[] }> {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    const key = row.currency ?? "";
    const bucket = groups.get(key);
    if (bucket) bucket.push(row);
    else groups.set(key, [row]);
  }
  return [...groups.entries()].map(([key, groupRows]) => ({
    currency: key || null,
    rows: groupRows,
  }));
}

/** Largest amount among the returned values; used only to scale the bars. */
export function largestAmount(
  amounts: Iterable<string | null | undefined>,
): string | null {
  let largest: string | null = null;
  for (const amount of amounts) {
    if (amount == null) continue;
    if (largest === null || compareDecimals(amount, largest) > 0) {
      largest = amount;
    }
  }
  return largest;
}

/**
 * The grouping key of a spend row, combined with its currency.
 *
 * The API returns one row per (grouping key, currency), so this pair identifies a row
 * uniquely and lets pages be merged without double-counting a group.
 */
export function spendRowKey(row: AnalyticsSpendRow, groupBy: AnalyticsGroupBy): string {
  const key =
    groupBy === "month"
      ? row.bucket_start
      : groupBy === "department"
        ? row.department_id
        : groupBy === "location"
          ? row.office_location_id
          : groupBy === "category"
            ? row.category
            : groupBy === "employee"
              ? row.employee_membership_id
              : row.status;
  return `${groupBy}|${key ?? ""}|${row.currency ?? ""}`;
}

/**
 * Append a later page to the rows already shown, without duplicating a group.
 *
 * The cursor is currently an opaque offset, so a claim created between two requests can
 * shift a group onto the next page and repeat a row that was already merged. Keeping the
 * later copy of a duplicated key preserves the grouping's structure while showing the
 * fresher aggregate.
 */
export function mergeSpendRows(
  existing: readonly AnalyticsSpendRow[],
  incoming: readonly AnalyticsSpendRow[],
  groupBy: AnalyticsGroupBy,
): AnalyticsSpendRow[] {
  const merged = new Map<string, AnalyticsSpendRow>();
  for (const row of existing) merged.set(spendRowKey(row, groupBy), row);
  for (const row of incoming) merged.set(spendRowKey(row, groupBy), row);
  return [...merged.values()];
}

export interface CurrencySummary {
  currency: string | null;
  /** Exact sum of the returned group totals, or null when none of them had an amount. */
  total: string | null;
  claimCount: number;
  amountClaimCount: number;
}

/**
 * Combine the server's per-status sums for the requested statuses, per currency.
 *
 * This is the only arithmetic the dashboard performs, and it is a faithful transformation
 * of returned group sums: `status_amounts` partitions the period's claims by status, so
 * summing a subset yields exactly that subset's total. It is exact decimal addition of
 * server-returned values, never a re-derivation of a backend metric, and currencies are
 * never combined with one another.
 */
export function summariseStatusAmounts(
  rows: AnalyticsOverview["status_amounts"],
  statuses: readonly ExpenseStatus[],
): CurrencySummary[] {
  const wanted = new Set<string>(statuses);
  const byCurrency = new Map<string, AnalyticsOverview["status_amounts"]>();
  for (const row of rows) {
    if (!wanted.has(row.status)) continue;
    const key = row.currency ?? "";
    const bucket = byCurrency.get(key);
    if (bucket) bucket.push(row);
    else byCurrency.set(key, [row]);
  }

  return [...byCurrency.entries()].map(([key, entries]) => ({
    currency: key || null,
    total: addDecimalStrings(entries.map((entry) => entry.amount_total)),
    claimCount: entries.reduce((count, entry) => count + entry.claim_count, 0),
    amountClaimCount: entries.reduce((count, entry) => count + entry.amount_claim_count, 0),
  }));
}

// ---------------------------------------------------------------------------
// Department breakdown
// ---------------------------------------------------------------------------

export type AnalyticsDepartmentSummary =
  components["schemas"]["AnalyticsDepartmentSummaryResponse"];
export type AnalyticsDepartmentRow = components["schemas"]["AnalyticsDepartmentRow"];
export type AnalyticsDepartmentTotals = components["schemas"]["AnalyticsDepartmentTotals"];

export type DepartmentQuery =
  paths["/api/v1/analytics/departments"]["get"]["parameters"]["query"];

/**
 * The same filter set as the other analytics queries, built the same way.
 *
 * An empty string means "no filter", so the parameter is omitted rather than sent blank:
 * the API validates a present-but-empty UUID as invalid, which would turn an unfiltered
 * view into a 422.
 */
export function buildDepartmentQuery(
  range: DateRange,
  filters: AnalyticsFilters,
): DepartmentQuery {
  const query: DepartmentQuery = { from: range.from, to: range.to };
  if (filters.departmentId) query.department_id = filters.departmentId;
  if (filters.officeLocationId) query.office_location_id = filters.officeLocationId;
  if (filters.employeeMembershipId) query.employee_membership_id = filters.employeeMembershipId;
  if (filters.category) query.category = filters.category;
  if (filters.currency) query.currency = filters.currency;
  if (filters.status) query.status = filters.status;
  return query;
}

export async function loadDepartments(
  api: ProoflineClient,
  query: DepartmentQuery,
  signal?: AbortSignal,
): Promise<AnalyticsDepartmentSummary> {
  return unwrap(api.GET("/api/v1/analytics/departments", { params: { query }, signal }));
}

/**
 * A department row's share of its currency total, as a percentage string.
 *
 * The API returns an exact fraction string; this only formats it, using the same BigInt
 * digit arithmetic as the rest of the file. It never recomputes the share from money
 * values, so the displayed percentage cannot disagree with the backend.
 */
export function formatSharePercent(share: string | null | undefined): string | null {
  const fraction = parseDecimal(share ?? "");
  if (fraction === null) return null;
  const scale = fraction.fraction.length;
  const digits = signedDigits(fraction, scale);
  // Multiply by 1000 so one decimal place can be truncated rather than rounded away.
  const perThousand = (digits * 1000n) / 10n ** BigInt(scale);
  const whole = perThousand / 10n;
  const tenth = perThousand % 10n < 0n ? -(perThousand % 10n) : perThousand % 10n;
  return `${whole}.${tenth}%`;
}

/**
 * A bar width as a percentage of the widest value in the same currency.
 *
 * Money stays in exact digits for the comparison; only the final CSS width becomes a
 * number, and it is a rendering decision rather than a figure anyone reads as money.
 */
export function barWidthPercent(
  value: string | null | undefined,
  widest: string | null | undefined,
): number {
  const amount = parseDecimal(value ?? "");
  const max = parseDecimal(widest ?? "");
  if (amount === null || max === null) return 0;
  const scale = Math.max(amount.fraction.length, max.fraction.length);
  const digits = signedDigits(amount, scale);
  const ceiling = signedDigits(max, scale);
  if (ceiling <= 0n || digits <= 0n) return 0;
  if (digits >= ceiling) return 100;
  // Two decimal places of precision, computed on integers.
  const perTenThousand = (digits * 10000n) / ceiling;
  return Math.max(1, Math.min(100, Number(perTenThousand) / 100));
}

/** The largest requested total among rows sharing a currency. */
export function widestRequested(rows: AnalyticsDepartmentRow[]): string | null {
  let widest: string | null = null;
  for (const row of rows) {
    if (row.amount_total === null || row.amount_total === undefined) continue;
    if (widest === null || compareDecimals(row.amount_total, widest) > 0) {
      widest = row.amount_total;
    }
  }
  return widest;
}
