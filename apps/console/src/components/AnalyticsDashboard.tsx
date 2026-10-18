"use client";

/**
 * Finance/Admin spend analytics.
 *
 * The operating path is real: this component issues
 * `GET /api/v1/analytics/overview` and `GET /api/v1/analytics/spend` on every period,
 * filter and grouping change, and renders what those endpoints return. No figure on this
 * screen is computed by the frontend beyond exact decimal addition of values the server
 * already summed, and no figure is substituted when a request fails.
 *
 * What the display deliberately does NOT claim:
 *
 * - Workflow `approved` is not a policy PASS and not a payment. Statuses are labelled as
 *   workflow states.
 * - A missing or uncertain critical field is a completeness fact, not misconduct. Claims
 *   are never asserted to be fraudulent, and potential duplicates are not shown as
 *   findings: the analytics service does not join candidate rows at all.
 * - Department and office attribution uses each membership's *current* department and
 *   location, because expenses do not store a historical snapshot. The note under the
 *   charts says so rather than implying the split is as-of the transaction date.
 * - Claims without a transaction date cannot be placed in a period. They are counted and
 *   named separately, never bucketed at zero.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  Card,
  EmptyState,
  ErrorState,
  Metric,
  StatusPill,
} from "@/components/ui";
import {
  ANALYTICS_GROUPS,
  EMPTY_FILTERS,
  EXPENSE_STATUSES,
  SPEND_PAGE_LIMIT,
  buildOverviewQuery,
  buildSpendQuery,
  createRequestGate,
  decimalBarPercent,
  describeError,
  describeSelection,
  formatCount,
  formatDecimalCurrency,
  initialDateRange,
  isUuid,
  largestAmount,
  loadFilterOptions,
  loadOverview,
  loadSpendPage,
  mergeSpendRows,
  requiresOrganizationAnalytics,
  sameSelection,
  summariseStatusAmounts,
  validateFilters,
  validateRange,
  type AnalyticsError,
  type AnalyticsFilters,
  type AnalyticsGroupBy,
  type AnalyticsOverview,
  type AnalyticsSpendRow,
  type DateRange,
  type ExpenseStatus,
  type OverviewQuery,
  type PageInfo,
  type SpendQuery,
} from "@/lib/analytics";
import { createConsoleApi } from "@/lib/api";

/**
 * One client for the whole screen.
 *
 * `createConsoleApi` supplies the demo actor header and the (currently empty) token
 * provider from `src/lib/api.ts`. Nothing here selects a role or an organization: the
 * backend resolves both from the actor it sees.
 */
const consoleApi = createConsoleApi();

/** The debounce applied to the free-text membership filter, in milliseconds. */
const FILTER_DEBOUNCE_MS = 400;

// ---------------------------------------------------------------------------
// State shapes
// ---------------------------------------------------------------------------

/** A resource that is loaded, loading for the first time, or refreshing over known data. */
export interface ResourceState<T> {
  data: T | null;
  error: AnalyticsError | null;
  /** First load: nothing has ever rendered, so a skeleton is shown. */
  loading: boolean;
  /** A newer request is in flight while previous data is on screen. */
  refreshing: boolean;
  /**
   * The request `data` came from.
   *
   * Retained so a failure can say which selection the figures on screen actually belong
   * to. Without it, a failed request after a filter change would leave the previous
   * selection's numbers sitting under the new controls, which reads as the new answer.
   */
  loadedQuery?: OverviewQuery | null;
}

export interface SpendState {
  rows: AnalyticsSpendRow[];
  page: PageInfo | null;
  unknownDateCount: number;
  error: AnalyticsError | null;
  loading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  loadMoreError: AnalyticsError | null;
  /** How many spend pages have been requested and merged so far. */
  pagesLoaded: number;
  /** The request `rows` came from. See {@link ResourceState.loadedQuery}. */
  loadedQuery?: SpendQuery | null;
}

const INITIAL_OVERVIEW_STATE: ResourceState<AnalyticsOverview> = {
  data: null,
  error: null,
  loading: true,
  refreshing: false,
};

const INITIAL_SPEND_STATE: SpendState = {
  rows: [],
  page: null,
  unknownDateCount: 0,
  error: null,
  loading: true,
  refreshing: false,
  loadingMore: false,
  loadMoreError: null,
  pagesLoaded: 0,
};

// ---------------------------------------------------------------------------
// Container
// ---------------------------------------------------------------------------

export default function AnalyticsDashboard() {
  const [range, setRange] = useState<DateRange>(() => initialDateRange());
  const [filters, setFilters] = useState<AnalyticsFilters>(EMPTY_FILTERS);
  const [employeeDraft, setEmployeeDraft] = useState("");
  const [groupBy, setGroupBy] = useState<AnalyticsGroupBy>("month");
  const [reloadToken, setReloadToken] = useState(0);

  const [overview, setOverview] = useState<ResourceState<AnalyticsOverview>>(
    INITIAL_OVERVIEW_STATE,
  );
  const [catalogue, setCatalogue] = useState<AnalyticsOverview | null>(null);
  const [catalogueError, setCatalogueError] = useState<AnalyticsError | null>(null);
  const [spend, setSpend] = useState<SpendState>(INITIAL_SPEND_STATE);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Gates make "latest request wins" explicit. Aborting covers the in-flight case; the
  // gate covers a response that has already arrived and is waiting on the microtask queue.
  const overviewGate = useRef(createRequestGate());
  const spendGate = useRef(createRequestGate());
  const loadMoreGate = useRef(createRequestGate());

  const validationError = useMemo(
    () => validateRange(range) ?? validateFilters(filters),
    [range, filters],
  );

  /**
   * Debounce the membership field.
   *
   * It is the only control a user types a partial value into, so committing on every
   * keystroke would fire a request per character - each one a 422 until the id is
   * complete. Selects and dates commit immediately: a chosen value is a finished value.
   */
  useEffect(() => {
    const handle = window.setTimeout(() => {
      setFilters((current) =>
        current.employeeMembershipId === employeeDraft
          ? current
          : { ...current, employeeMembershipId: employeeDraft },
      );
    }, FILTER_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [employeeDraft]);

  // Overview (filtered) plus the unfiltered catalogue that populates the option lists.
  useEffect(() => {
    if (validationError) {
      setOverview((current) => ({
        ...current,
        loading: false,
        refreshing: false,
        error: null,
      }));
      return;
    }

    const token = overviewGate.current.begin();
    const controller = new AbortController();
    const query = buildOverviewQuery(range, filters);
    setOverview((current) => ({
      data: current.data,
      error: null,
      loading: current.data === null,
      refreshing: current.data !== null,
      loadedQuery: current.loadedQuery,
    }));
    setCatalogueError(null);

    loadOverview(consoleApi, query, controller.signal)
      .then((data) => {
        if (controller.signal.aborted || !overviewGate.current.isCurrent(token)) return;
        setOverview({ data, error: null, loading: false, refreshing: false, loadedQuery: query });
        setLastUpdated(new Date());
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || !overviewGate.current.isCurrent(token)) return;
        setOverview((current) => ({
          ...current,
          loading: false,
          refreshing: false,
          error: describeError(error),
        }));
      });

    loadFilterOptions(consoleApi, range, controller.signal)
      .then((data) => {
        if (controller.signal.aborted || !overviewGate.current.isCurrent(token)) return;
        setCatalogue(data);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || !overviewGate.current.isCurrent(token)) return;
        setCatalogueError(describeError(error));
      });

    return () => controller.abort();
  }, [range, filters, reloadToken, validationError]);

  // Spend page 1. Re-runs when the grouping changes, and only then - changing the
  // dimension must not re-request the overview as well.
  useEffect(() => {
    if (validationError) {
      setSpend((current) => ({
        ...current,
        loading: false,
        refreshing: false,
        loadingMore: false,
      }));
      return;
    }

    // Any in-flight "load more" belongs to the previous selection and must not append.
    loadMoreGate.current.begin();
    const token = spendGate.current.begin();
    const controller = new AbortController();
    const query = buildSpendQuery(range, filters, groupBy, null);
    setSpend((current) => {
      if (!sameSelection(current.loadedQuery, query)) {
        // A different selection invalidates the rows *and* the pagination cursor. The
        // cursor addresses the next page of the previous selection's result set, so
        // keeping it would offer "load more" while the rows for the new selection are
        // still unresolved and would send the new filters with the old cursor, silently
        // skipping groups. The retained figures are dropped rather than relabelled, and a
        // genuine loading state takes their place.
        return {
          rows: [],
          page: null,
          unknownDateCount: 0,
          error: null,
          loading: true,
          refreshing: false,
          loadingMore: false,
          loadMoreError: null,
          pagesLoaded: 0,
          loadedQuery: current.loadedQuery,
        };
      }
      // Same selection (an explicit refresh): the rows on screen are still the answer to
      // the request being repeated, so they stay until the new response arrives.
      return {
        ...current,
        error: null,
        loadMoreError: null,
        loading: current.rows.length === 0,
        refreshing: current.rows.length > 0,
      };
    });

    loadSpendPage(consoleApi, query, controller.signal)
      .then((page) => {
        if (controller.signal.aborted || !spendGate.current.isCurrent(token)) return;
        setSpend({
          rows: page.rows,
          page: page.page,
          unknownDateCount: page.unknownDateCount,
          error: null,
          loading: false,
          refreshing: false,
          loadingMore: false,
          loadMoreError: null,
          pagesLoaded: 1,
          loadedQuery: query,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || !spendGate.current.isCurrent(token)) return;
        setSpend((current) => ({
          ...current,
          loading: false,
          refreshing: false,
          loadingMore: false,
          error: describeError(error),
        }));
      });

    return () => controller.abort();
  }, [range, filters, groupBy, reloadToken, validationError]);

  const loadMore = useCallback(() => {
    const cursor = spend.page?.next_cursor;
    if (!cursor) return;
    // The cursor addresses the page after the result set the rows on screen came from. It
    // may only be followed while that result set is still the one the controls describe,
    // and while no request for it is outstanding: appending a page fetched with the new
    // filters to rows fetched with the old ones mixes two selections into one list.
    const loadedQuery = buildSpendQuery(range, filters, groupBy, null);
    if (!sameSelection(spend.loadedQuery, loadedQuery)) return;
    if (spend.loading || spend.refreshing || spend.loadingMore) return;
    const token = loadMoreGate.current.begin();
    setSpend((current) => ({ ...current, loadingMore: true, loadMoreError: null }));
    loadSpendPage(consoleApi, buildSpendQuery(range, filters, groupBy, cursor))
      .then((page) => {
        if (!loadMoreGate.current.isCurrent(token)) return;
        setSpend((current) => ({
          ...current,
          rows: mergeSpendRows(current.rows, page.rows, groupBy),
          page: page.page,
          unknownDateCount: page.unknownDateCount,
          loadingMore: false,
          loadMoreError: null,
          pagesLoaded: current.pagesLoaded + 1,
        }));
      })
      .catch((error: unknown) => {
        if (!loadMoreGate.current.isCurrent(token)) return;
        setSpend((current) => ({
          ...current,
          loadingMore: false,
          loadMoreError: describeError(error),
        }));
      });
  }, [
    filters,
    groupBy,
    range,
    spend.page,
    spend.loadedQuery,
    spend.loading,
    spend.refreshing,
    spend.loadingMore,
  ]);

  const updateFilter = useCallback(
    <K extends keyof AnalyticsFilters>(key: K, value: AnalyticsFilters[K]) => {
      setFilters((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const reset = useCallback(() => {
    // The period is part of the same panel as the filters, and it is the one control that
    // can be left in a state the API refuses (start after end). A reset that cleared the
    // filters but kept an impossible period would leave the reader stuck with a banner and
    // no way back, so the period returns to its derived default too.
    setRange(initialDateRange());
    setFilters(EMPTY_FILTERS);
    setEmployeeDraft("");
    setGroupBy("month");
  }, []);

  return (
    <AnalyticsView
      range={range}
      filters={filters}
      employeeDraft={employeeDraft}
      groupBy={groupBy}
      validationError={validationError}
      overview={overview}
      catalogue={catalogue}
      catalogueError={catalogueError}
      spend={spend}
      lastUpdated={lastUpdated}
      onRangeChange={setRange}
      onFilterChange={updateFilter}
      onEmployeeDraftChange={setEmployeeDraft}
      onGroupByChange={setGroupBy}
      onReset={reset}
      onRefresh={() => setReloadToken((token) => token + 1)}
      onLoadMore={loadMore}
    />
  );
}

// ---------------------------------------------------------------------------
// Presentational view (props in, markup out - directly renderable in tests)
// ---------------------------------------------------------------------------

export function AnalyticsView({
  range,
  filters,
  employeeDraft,
  groupBy,
  validationError,
  overview,
  catalogue,
  catalogueError,
  spend,
  lastUpdated,
  onRangeChange,
  onFilterChange,
  onEmployeeDraftChange,
  onGroupByChange,
  onReset,
  onRefresh,
  onLoadMore,
}: {
  range: DateRange;
  filters: AnalyticsFilters;
  employeeDraft: string;
  groupBy: AnalyticsGroupBy;
  validationError: string | null;
  overview: ResourceState<AnalyticsOverview>;
  catalogue: AnalyticsOverview | null;
  catalogueError: AnalyticsError | null;
  spend: SpendState;
  lastUpdated: Date | null;
  onRangeChange: (range: DateRange) => void;
  onFilterChange: <K extends keyof AnalyticsFilters>(key: K, value: AnalyticsFilters[K]) => void;
  onEmployeeDraftChange: (value: string) => void;
  onGroupByChange: (groupBy: AnalyticsGroupBy) => void;
  onReset: () => void;
  onRefresh: () => void;
  onLoadMore: () => void;
}) {
  const busy = overview.loading || overview.refreshing || spend.loading || spend.refreshing;

  // Built once per render and passed down, so every section compares the response it holds
  // against the same description of what the controls now request.
  const overviewQuery = buildOverviewQuery(range, filters);
  const spendQuery = buildSpendQuery(range, filters, groupBy);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">
            Finance intelligence
          </p>
          <h1 className="mt-1 text-lg font-semibold tracking-tight">Spend analytics</h1>
          <p className="mt-1 max-w-prose text-sm text-[var(--color-text-muted)]">
            Persisted claims for the selected period, aggregated by the analytics API. Amounts
            stay separated by currency; workflow status is not a policy result and not a payment
            record.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm font-medium hover:bg-[var(--color-surface-muted)] disabled:cursor-wait disabled:opacity-60"
          >
            {busy ? "Refreshing…" : "Refresh data"}
          </button>
          <p className="text-xs text-[var(--color-text-muted)]">
            {lastUpdated
              ? `Last successful response ${lastUpdated.toLocaleTimeString()}`
              : "No successful response yet"}
          </p>
        </div>
      </header>

      <PeriodSummary overview={overview} range={range} currentQuery={overviewQuery} />

      <FilterPanel
        range={range}
        filters={filters}
        employeeDraft={employeeDraft}
        catalogue={catalogue}
        catalogueState={
          catalogue ? "ready" : catalogueError ? "failed" : "loading"
        }
        onRangeChange={onRangeChange}
        onFilterChange={onFilterChange}
        onEmployeeDraftChange={onEmployeeDraftChange}
        onReset={onReset}
      />

      {validationError && (
        <div
          role="alert"
          className="rounded-lg border border-[var(--color-severity-warning)] bg-[var(--color-surface-muted)] p-4"
        >
          <p className="text-sm font-medium text-[var(--color-text)]">
            This selection cannot be requested
          </p>
          <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
            {validationError} No request was sent, so the figures below remain those of the last
            valid selection, and each section states which selection that is. Correct the period
            or the filters, or reset both.
          </p>
        </div>
      )}

      {catalogueError && !overview.error && (
        <p
          role="status"
          className="rounded border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]"
        >
          Filter option lists could not be refreshed ({catalogueError.title}). Selections already
          made remain valid.
        </p>
      )}

      <OverviewSection
        overview={overview}
        range={range}
        currentQuery={overviewQuery}
        selectionError={validationError}
      />

      <SpendSection
        spend={spend}
        groupBy={groupBy}
        range={range}
        currentQuery={spendQuery}
        selectionError={validationError}
        onGroupByChange={onGroupByChange}
        onLoadMore={onLoadMore}
      />

      <DisclosureNotes />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Period summary
// ---------------------------------------------------------------------------

/** Inclusive period label. Date-only strings are formatted in UTC so they cannot shift. */
export function formatPeriodLabel(range: DateRange): string {
  const start = formatIsoDate(range.from);
  const end = formatIsoDate(range.to);
  if (!start || !end) return `${range.from || "?"} – ${range.to || "?"}`;
  return `${start} – ${end}`;
}

function formatIsoDate(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

/** First calendar date of the month, e.g. `2026-07-01` -> `Jul 2026`. */
export function formatMonthLabel(value: string | null | undefined): string {
  if (!value) return "Month not recorded";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(
    parsed,
  );
}

/**
 * The period the response on screen actually belongs to.
 *
 * The controls and the request that produced the visible figures are not the same thing
 * while a refresh is in flight, so every period caption is derived from the response's own
 * `loadedQuery` and falls back to the control `range` only when nothing is displayed.
 */
function displayedRange(
  loadedQuery: { from: string; to: string } | null | undefined,
  range: DateRange,
  hasData: boolean,
): DateRange {
  if (hasData && loadedQuery) return { from: loadedQuery.from, to: loadedQuery.to };
  return range;
}

function PeriodSummary({
  overview,
  range,
  currentQuery,
}: {
  overview: ResourceState<AnalyticsOverview>;
  range: DateRange;
  currentQuery: OverviewQuery;
}) {
  const data = overview.data;
  const loadedQuery = overview.loadedQuery ?? null;
  const periodRange = displayedRange(loadedQuery, range, data !== null);
  // Only a response that was actually asked for by the current controls is "the current
  // selection"; a retained one that answers something else has to say so, because the
  // paragraph below quotes the API's own confirmation of *its* period.
  const isCurrentSelection =
    loadedQuery === null ? true : sameSelection(loadedQuery, currentQuery);

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-[var(--color-text)]">
          Period: <span className="tabular-nums">{formatPeriodLabel(periodRange)}</span>
        </p>
        <p className="text-xs text-[var(--color-text-muted)]">
          Inclusive of both dates, by transaction date only
        </p>
      </div>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
        The two boundary dates are included. Only the claim&apos;s transaction date is used: a claim
        created or decided inside the period but transacted outside it is not counted here.
        {data
          ? ` The API confirmed this period as ${data.from_date} to ${data.to_date}.`
          : ""}
      </p>
      {data && loadedQuery && !isCurrentSelection && (
        <p
          role="status"
          className="mt-2 max-w-prose text-xs text-[var(--color-severity-warning)]"
        >
          That confirmation is for {describeSelection(loadedQuery)}, which is the response on
          screen. The controls now request a different selection, and these figures stay until
          that response arrives.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function FilterPanel({
  range,
  filters,
  employeeDraft,
  catalogue,
  catalogueState,
  onRangeChange,
  onFilterChange,
  onEmployeeDraftChange,
  onReset,
}: {
  range: DateRange;
  filters: AnalyticsFilters;
  employeeDraft: string;
  catalogue: AnalyticsOverview | null;
  /** Distinguishes "still loading" from "the option list could not be loaded". */
  catalogueState: "loading" | "ready" | "failed";
  onRangeChange: (range: DateRange) => void;
  onFilterChange: <K extends keyof AnalyticsFilters>(key: K, value: AnalyticsFilters[K]) => void;
  onEmployeeDraftChange: (value: string) => void;
  onReset: () => void;
}) {
  const departments = uniqueOptions(
    (catalogue?.by_department ?? []).map((entry) => ({
      value: entry.department_id ?? "",
      label: entry.department_name ?? "No department on the membership",
    })),
  ).filter((option) => option.value !== "");

  const locations = uniqueOptions(
    (catalogue?.by_office_location ?? []).map((entry) => ({
      value: entry.office_location_id ?? "",
      label: entry.office_location_name ?? "No office location on the membership",
    })),
  ).filter((option) => option.value !== "");

  // Categories are free-form persisted strings; a null category is its own bucket and is
  // not offered as a filter value, because the API cannot filter for "is null".
  const categories = [...new Set((catalogue?.by_category ?? []).map((entry) => entry.category ?? ""))]
    .filter((value) => value !== "")
    .sort();

  // Currencies come from returned amount rows: the contract has no separate currency list.
  const currencies = [
    ...new Set(
      [
        ...(catalogue?.status_amounts ?? []).map((entry) => entry.currency ?? ""),
        ...(catalogue?.monthly_totals ?? []).map((entry) => entry.currency ?? ""),
      ].filter((value) => value !== ""),
    ),
  ].sort();

  const membershipHint =
    employeeDraft && !isUuid(employeeDraft)
      ? "Enter the complete membership UUID; partial values are not requested."
      : "Requires the analytics:read_org permission on the backend.";

  return (
    <Card
      title="Period and filters"
      description="Every control below changes the request that is sent. Dates are inclusive; other filters are applied by the API."
      actions={
        <button
          type="button"
          onClick={onReset}
          className="rounded border border-[var(--color-border-strong)] px-2 py-1 text-xs hover:bg-[var(--color-surface-muted)]"
        >
          Reset period and filters
        </button>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <FilterField label="Start date (inclusive)">
          <input
            aria-label="Start date (inclusive)"
            type="date"
            value={range.from}
            onChange={(event) => onRangeChange({ ...range, from: event.target.value })}
            className="w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-2 text-sm text-[var(--color-text)]"
          />
        </FilterField>
        <FilterField label="End date (inclusive)">
          <input
            aria-label="End date (inclusive)"
            type="date"
            value={range.to}
            onChange={(event) => onRangeChange({ ...range, to: event.target.value })}
            className="w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-2 text-sm text-[var(--color-text)]"
          />
        </FilterField>
        <FilterSelect
          label="Department"
          value={filters.departmentId}
          options={departments}
          onChange={(value) => onFilterChange("departmentId", value)}
          emptyLabel={catalogueEmptyLabel(catalogueState, "departments")}
        />
        <FilterSelect
          label="Office location"
          value={filters.officeLocationId}
          options={locations}
          onChange={(value) => onFilterChange("officeLocationId", value)}
          emptyLabel={catalogueEmptyLabel(catalogueState, "locations")}
        />
        <FilterSelect
          label="Category"
          value={filters.category}
          options={categories.map((value) => ({ value, label: value }))}
          onChange={(value) => onFilterChange("category", value)}
          emptyLabel={catalogueEmptyLabel(catalogueState, "categories")}
        />
        <FilterSelect
          label="Currency"
          value={filters.currency}
          options={currencies.map((value) => ({ value, label: value }))}
          onChange={(value) => onFilterChange("currency", value)}
          emptyLabel={catalogueEmptyLabel(catalogueState, "currencies")}
        />
        <FilterSelect
          label="Workflow status"
          value={filters.status}
          options={EXPENSE_STATUSES.map((value) => ({ value, label: statusLabel(value) }))}
          onChange={(value) => onFilterChange("status", value as ExpenseStatus | "")}
          emptyLabel="All workflow statuses"
        />
        <FilterField label="Employee membership" hint={membershipHint}>
          <input
            aria-label="Employee membership id"
            type="text"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            value={employeeDraft}
            onChange={(event) => onEmployeeDraftChange(event.target.value.trim())}
            placeholder="Membership UUID"
            className="w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-2 font-mono text-xs text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
          />
        </FilterField>
      </div>
    </Card>
  );
}

function FilterField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1 text-xs text-[var(--color-text-muted)]">
      <span>{label}</span>
      {children}
      {hint && <span className="block text-[11px] leading-snug">{hint}</span>}
    </label>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  emptyLabel,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  emptyLabel: string;
}) {
  // A selected value that is missing from a refreshed catalogue would silently change the
  // filter on the next render, so it is kept as an explicit option.
  const optionsWithSelection =
    value && !options.some((option) => option.value === value)
      ? [{ value, label: `${value} (no longer in the current period)` }, ...options]
      : options;

  return (
    <FilterField label={label}>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-2 text-sm text-[var(--color-text)]"
      >
        <option value="">{emptyLabel}</option>
        {optionsWithSelection.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FilterField>
  );
}

function uniqueOptions(options: Array<{ value: string; label: string }>) {
  return [...new Map(options.map((option) => [option.value || option.label, option])).values()];
}

/**
 * Wording for a filter whose option list is not available.
 *
 * A failed option list must not keep saying "Loading", because it is not loading: it is
 * absent, and a reviewer needs to know why the control looks empty.
 */
function catalogueEmptyLabel(
  state: "loading" | "ready" | "failed",
  plural: string,
): string {
  if (state === "ready") return `All ${plural}`;
  if (state === "failed") return `${plural[0]?.toUpperCase() ?? ""}${plural.slice(1)} unavailable`;
  return `Loading ${plural}…`;
}

// ---------------------------------------------------------------------------
// Overview section
// ---------------------------------------------------------------------------

function OverviewSection({
  overview,
  range,
  currentQuery,
  selectionError,
}: {
  overview: ResourceState<AnalyticsOverview>;
  range: DateRange;
  currentQuery: OverviewQuery;
  /** Set when the controls describe a request the API would refuse, so none was sent. */
  selectionError: string | null;
}) {
  if (overview.loading && !overview.data) {
    return <OverviewSkeleton />;
  }

  if (overview.error && !overview.data) {
    return <ErrorState title={overview.error.title} message={overview.error.message} />;
  }

  const data = overview.data;
  if (!data) {
    if (selectionError) {
      return (
        <p
          role="status"
          className="rounded border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]"
        >
          {selectionError} No request was sent, and no earlier response is available to show, so
          there are no figures for this screen yet.
        </p>
      );
    }
    return <OverviewSkeleton />;
  }

  const loadedQuery = overview.loadedQuery ?? null;
  // Every caption below describes the response on screen. Taking the period from the live
  // controls instead would caption one period's figures with another period's dates the
  // moment a refresh starts, and would caption an unrequestable selection's figures as if
  // the API had answered it.
  const periodRange = displayedRange(loadedQuery, range, true);
  const isCurrentSelection =
    loadedQuery === null ? true : sameSelection(loadedQuery, currentQuery);
  const loadedSelection = loadedQuery ? describeSelection(loadedQuery) : null;

  // A failure after the controls changed must not leave the previous selection's figures
  // under the new controls: they would read as the answer to a question that was never
  // answered. The error is shown instead, naming what the retained figures were for.
  if (overview.error && !isCurrentSelection) {
    return (
      <div className="space-y-3">
        <ErrorState title={overview.error.title} message={overview.error.message} />
        <p className="max-w-prose text-xs text-[var(--color-text-muted)]">
          An earlier selection did load successfully
          {loadedSelection ? ` (${loadedSelection})` : ""}
          , but it is not what the controls now request, so it is not shown here. Set the filters
          back or retry to see figures for the current selection.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6" aria-live="polite">
      {overview.error && (
        <StaleNotice
          message={`The latest overview request failed (${overview.error.title}): ${overview.error.message}`}
          loadedSelection={loadedSelection}
          isCurrentSelection={isCurrentSelection}
          requestId={overview.error.requestId}
        />
      )}
      {overview.refreshing && !overview.error && (
        <p role="status" className="text-xs text-[var(--color-text-muted)]">
          Updating for the current selection. The figures below are from the last completed
          response until the new one arrives.
        </p>
      )}
      {loadedSelection && !isCurrentSelection && !overview.error && (
        <p
          role="status"
          className="rounded border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]"
        >
          These figures are the last completed response, for {loadedSelection}.
          {selectionError
            ? " No request was sent for the selection now in the controls, so nothing has replaced them."
            : " The controls now request a different selection; these figures stay until that response arrives."}
        </p>
      )}

      <MetricGrid overview={data} />

      {data.claim_count === 0 ? (
        <EmptyState
          title="No dated claims in this period"
          description={`Nothing was transacted between ${periodRange.from} and ${periodRange.to} for this selection, so there are no charts to draw. ${formatCount(
            data.claims_with_unknown_transaction_date,
          )} claims match the filters but have no transaction date and cannot be placed in any period.`}
        />
      ) : (
        <>
          <MoneySummary overview={data} />
          <StatusBreakdown overview={data} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ChartCard
              title="Monthly spending"
              dimension="Transaction month"
              period={formatPeriodLabel(periodRange)}
              footnote="Calendar months with no dated claims are omitted by the API; an absent month is zero dated claims, not missing data."
            >
              <AmountBars
                rows={data.monthly_totals.map((row) => ({
                  currency: row.currency,
                  claimCount: row.claim_count,
                  amountClaimCount: row.amount_claim_count,
                  amountTotal: row.amount_total,
                  label: formatMonthLabel(row.month),
                }))}
                emptyMessage="No dated claims in the selected period."
              />
            </ChartCard>
            <ChartCard
              title="Department spending"
              dimension="Department"
              period={formatPeriodLabel(periodRange)}
              footnote="Each membership's current persisted department. Expenses do not store a historical snapshot, so a transfer can change this attribution."
            >
              <AmountBars
                rows={data.by_department.map((row) => ({
                  currency: row.currency,
                  claimCount: row.claim_count,
                  amountClaimCount: row.amount_claim_count,
                  amountTotal: row.amount_total,
                  label: row.department_name ?? "No department on the membership",
                }))}
                emptyMessage="No dated claims for any department in the selected period."
              />
            </ChartCard>
            <ChartCard
              title="Office location spending"
              dimension="Office location"
              period={formatPeriodLabel(periodRange)}
              footnote="Each membership's current persisted office location, with the same historical caveat as departments."
            >
              <AmountBars
                rows={data.by_office_location.map((row) => ({
                  currency: row.currency,
                  claimCount: row.claim_count,
                  amountClaimCount: row.amount_claim_count,
                  amountTotal: row.amount_total,
                  label: row.office_location_name ?? "No office location on the membership",
                }))}
                emptyMessage="No dated claims for any office location in the selected period."
              />
            </ChartCard>
            <ChartCard
              title="Expense categories"
              dimension="Category"
              period={formatPeriodLabel(periodRange)}
              footnote="Categories are the persisted strings employees and reviewers recorded. No policy classification is inferred."
            >
              <AmountBars
                rows={data.by_category.map((row) => ({
                  currency: row.currency,
                  claimCount: row.claim_count,
                  amountClaimCount: row.amount_claim_count,
                  amountTotal: row.amount_total,
                  label: row.category ?? "No category recorded",
                }))}
                emptyMessage="No dated claims for any category in the selected period."
              />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}

function MetricGrid({ overview }: { overview: AnalyticsOverview }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      <Metric
        label="Claims in period"
        value={formatCount(overview.claim_count)}
        basis="Dated claims whose transaction date is inside the range"
      />
      <Metric
        label="Awaiting review"
        value={formatCount(overview.claims_requiring_review)}
        basis="Workflow status submitted plus in_review"
      />
      <Metric
        label="Needs information"
        value={formatCount(overview.claims_needing_information)}
        basis="Workflow status needs_info"
      />
      <Metric
        label="Missing critical fields"
        value={formatCount(overview.claims_missing_critical_fields)}
        basis="Dated in-range claims with no merchant, amount or currency"
      />
      <Metric
        label="Uncertain critical fields"
        value={formatCount(overview.claims_with_uncertain_critical_fields)}
        basis="Dated in-range claims whose current field evidence carries an uncertainty reason"
      />
      <Metric
        label="No transaction date"
        value={formatCount(overview.claims_with_unknown_transaction_date)}
        basis="Organization claims with no expense date; outside every period and never counted at zero"
      />
    </div>
  );
}

function MoneySummary({ overview }: { overview: AnalyticsOverview }) {
  const approved = summariseStatusAmounts(overview.status_amounts, ["approved"]);
  const awaiting = summariseStatusAmounts(overview.status_amounts, ["submitted", "in_review"]);
  const rejected = summariseStatusAmounts(overview.status_amounts, ["rejected"]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <CurrencySummaryCard
        title="Approved amounts"
        description="Workflow approval by a human reviewer. This is not a policy PASS and not evidence of payment."
        summaries={approved}
      />
      <CurrencySummaryCard
        title="Awaiting review amounts"
        description="Exact sum of the API's submitted and in_review group totals, kept separate per currency."
        summaries={awaiting}
      />
      <CurrencySummaryCard
        title="Not reimbursed amounts"
        description="Claims a reviewer did not approve. A workflow outcome, with no judgement about the employee."
        summaries={rejected}
      />
    </div>
  );
}

function CurrencySummaryCard({
  title,
  description,
  summaries,
}: {
  title: string;
  description: string;
  summaries: ReturnType<typeof summariseStatusAmounts>;
}) {
  return (
    <Card title={title} description={description}>
      {summaries.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">
          No claims in these workflow statuses for this period.
        </p>
      ) : (
        <ul className="space-y-3">
          {summaries.map((summary) => (
            <li key={summary.currency ?? "currency-not-recorded"}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                  {summary.currency ?? "Currency not recorded"}
                </span>
                <span className="text-lg font-semibold tabular-nums">
                  {summary.total === null
                    ? "No amount recorded"
                    : formatDecimalCurrency(summary.total, summary.currency)}
                </span>
              </div>
              <p className="text-xs text-[var(--color-text-muted)]">
                Amount known for {formatCount(summary.amountClaimCount)} of{" "}
                {formatCount(summary.claimCount)} claims
                {summary.total === null
                  ? " · no group in this selection carried an amount"
                  : " · added from the API's per-status totals, never converted across currencies"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function StatusBreakdown({ overview }: { overview: AnalyticsOverview }) {
  const amountsByStatus = new Map<string, AnalyticsOverview["status_amounts"]>();
  for (const row of overview.status_amounts) {
    const bucket = amountsByStatus.get(row.status);
    if (bucket) bucket.push(row);
    else amountsByStatus.set(row.status, [row]);
  }

  const totalPerCurrency = summariseStatusAmounts(overview.status_amounts, EXPENSE_STATUSES);

  return (
    <Card
      title="Workflow status"
      description="Every canonical status the API returns, including statuses with no claims in the period."
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {overview.status_counts.map((entry) => {
          const currencyRows = amountsByStatus.get(entry.status) ?? [];
          return (
            <div
              key={entry.status}
              className="rounded-md border border-[var(--color-border)] p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <StatusPill status={entry.status} />
                <span className="text-lg font-semibold tabular-nums">
                  {formatCount(entry.claim_count)}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">claims in period</p>
              {currencyRows.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-[var(--color-border)] pt-2">
                  {currencyRows.map((amount) => (
                    <li
                      key={amount.currency ?? "currency-not-recorded"}
                      className="flex justify-between gap-2 text-xs"
                    >
                      <span className="text-[var(--color-text-muted)]">
                        {amount.currency ?? "No currency"}
                      </span>
                      <span className="tabular-nums">
                        {amount.amount_total == null
                          ? "No amount"
                          : formatDecimalCurrency(amount.amount_total, amount.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-[var(--color-text-muted)]">
        Recorded amounts across all workflow statuses, per currency:{" "}
        {totalPerCurrency.length === 0
          ? "no claim in this selection has a persisted amount."
          : totalPerCurrency
              .map((summary) =>
                summary.total === null
                  ? `${summary.currency ?? "no currency"}: no amount recorded`
                  : `${summary.currency ?? "no currency"} ${formatDecimalCurrency(summary.total, summary.currency)}`,
              )
              .join(" · ")}
      </p>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Spend explorer
// ---------------------------------------------------------------------------

function SpendSection({
  spend,
  groupBy,
  range,
  currentQuery,
  selectionError,
  onGroupByChange,
  onLoadMore,
}: {
  spend: SpendState;
  groupBy: AnalyticsGroupBy;
  range: DateRange;
  currentQuery: SpendQuery;
  /** Set when the controls describe a request the API would refuse, so none was sent. */
  selectionError: string | null;
  onGroupByChange: (groupBy: AnalyticsGroupBy) => void;
  onLoadMore: () => void;
}) {
  const total = spend.page?.total ?? null;
  const loaded = spend.rows.length;
  const employeeScope = requiresOrganizationAnalytics(groupBy);
  const refusedForScope = spend.error?.kind === "forbidden" && employeeScope;
  // A row's label is derived from the grouping dimension, so rows may only be shown while
  // the whole selection they were requested under - period, filters, dimension and page
  // size - is still the selection the controls describe. A no-error in-flight refresh is
  // still a different selection, and rendering the previous grouping's rows under the new
  // grouping is how a month bucket ends up captioned "Employee name not recorded".
  const rowsAreCurrent = sameSelection(spend.loadedQuery, currentQuery);
  const showRows = loaded > 0 && rowsAreCurrent && !spend.loading;
  // The cursor addresses the page after the result set those rows came from, so it is only
  // offered while that result set is still the current one.
  const hasMore = rowsAreCurrent && Boolean(spend.page?.next_cursor);
  const rowsBelongToOtherSelection = loaded > 0 && !rowsAreCurrent;
  const loadedSelection = spend.loadedQuery
    ? describeSelection(spend.loadedQuery, spend.loadedQuery.group_by)
    : "an earlier selection";

  return (
    <Card
      title="Filtered spend groups"
      description={`GET /api/v1/analytics/spend, grouped by one dimension and currency. Page size ${SPEND_PAGE_LIMIT}.`}
      actions={
        <label className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-[var(--color-text-muted)]">
          Group by
          <select
            aria-label="Spend grouping dimension"
            value={groupBy}
            onChange={(event) => onGroupByChange(event.target.value as AnalyticsGroupBy)}
            className="min-w-0 max-w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text)]"
          >
            {ANALYTICS_GROUPS.map((group) => (
              <option key={group} value={group}>
                {groupLabel(group)}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {employeeScope && (
        <p className="mb-3 rounded border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
          Employee grouping returns one row per membership and requires the
          analytics:read_org permission. The backend refuses the request without it.
        </p>
      )}

      {spend.loading && loaded === 0 && (
        <div role="status" aria-live="polite" className="space-y-2 py-4">
          <span className="sr-only">Loading spend groups</span>
          <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--color-surface-muted)]" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
          <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
        </div>
      )}

      {spend.error && !showRows && (
        <div className="space-y-3">
          <ErrorState
            title={refusedForScope ? "Employee-level grouping is not permitted" : spend.error.title}
            message={
              refusedForScope
                ? "This actor may read organization aggregates but not employee-level groupings. Choose a different dimension, or ask an administrator for the analytics:read_org permission on the server."
                : spend.error.message
            }
          />
          {loaded > 0 && (
            <p className="max-w-prose text-xs text-[var(--color-text-muted)]">
              The previous selection did return groups
              {spend.loadedQuery
                ? ` (${describeSelection(spend.loadedQuery, spend.loadedQuery.group_by)})`
                : ""}
              , but they are not what the controls now request, so they are not relabelled as the
              current grouping. Choose the previous grouping again or retry.
            </p>
          )}
        </div>
      )}

      {!spend.error && rowsBelongToOtherSelection && (
        <p
          role="status"
          className="rounded border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]"
        >
          {selectionError
            ? `No request was sent for the selection now in the controls, so the groups already loaded are not replaced. They are for ${loadedSelection}, and they are not shown under the current controls.`
            : `The groups already loaded are for ${loadedSelection}. The controls now request a different selection, so those groups are not relabelled as the current grouping.`}
        </p>
      )}

      {showRows && (
        <div className="space-y-4" aria-live="polite">
          {spend.error && (
            <StaleNotice
              message={`The latest spend request failed (${spend.error.title}): ${spend.error.message}`}
              loadedSelection={
                spend.loadedQuery
                  ? describeSelection(spend.loadedQuery, spend.loadedQuery.group_by)
                  : null
              }
              isCurrentSelection={sameSelection(spend.loadedQuery, currentQuery)}
              requestId={spend.error.requestId}
            />
          )}
          {spend.refreshing && !spend.error && (
            <p role="status" className="text-xs text-[var(--color-text-muted)]">
              Updating these groups for the current selection.
            </p>
          )}

          <p className="text-xs text-[var(--color-text-muted)]">
            Grouped by <strong>{groupLabel(groupBy).toLowerCase()}</strong> and currency ·{" "}
            {total === null
              ? `${formatCount(loaded)} groups returned on the first page; the API did not report a total`
              : `showing ${formatCount(loaded)} of ${formatCount(total)} matching groups`}
            {spend.pagesLoaded > 1 ? ` across ${formatCount(spend.pagesLoaded)} pages` : ""} ·{" "}
            {formatPeriodLabel(displayedRange(spend.loadedQuery, range, true))}
          </p>

          <AmountBars
            rows={spend.rows.map((row) => ({
              currency: row.currency,
              claimCount: row.claim_count,
              amountClaimCount: row.amount_claim_count,
              amountTotal: row.amount_total,
              label: spendRowLabel(row, groupBy),
              statusValue: row.status,
            }))}
            emptyMessage="No groups match the current filters."
          />

          {hasMore && (
            <div className="flex flex-wrap items-center gap-3 border-t border-[var(--color-border)] pt-3">
              <button
                type="button"
                onClick={onLoadMore}
                disabled={spend.loadingMore || spend.refreshing || spend.loading}
                className="rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm font-medium hover:bg-[var(--color-surface-muted)] disabled:cursor-wait disabled:opacity-60"
              >
                {spend.loadingMore ? "Loading more groups…" : "Load more groups"}
              </button>
              <p className="text-xs text-[var(--color-text-muted)]">
                The API returned a next-page cursor, so this list is not the whole dataset yet.
              </p>
            </div>
          )}
          {!hasMore && total !== null && loaded < total && (
            <p role="status" className="text-xs text-[var(--color-text-muted)]">
              The API reported {formatCount(total)} matching groups but returned no further cursor.
              Showing the {formatCount(loaded)} it returned.
            </p>
          )}
          {spend.loadMoreError && (
            <p role="alert" className="text-xs text-[var(--color-severity-blocking)]">
              {spend.loadMoreError.title}: {spend.loadMoreError.message}
            </p>
          )}

          {spend.unknownDateCount > 0 && (
            <p className="text-xs text-[var(--color-text-muted)]">
              {formatCount(spend.unknownDateCount)} claims match these filters but have no
              transaction date, so the API excludes them from these groups. They are not dropped
              data: they are reported here instead of being placed in a month.
            </p>
          )}
        </div>
      )}

      {!spend.loading && !spend.error && loaded === 0 && (
        selectionError ? (
          <EmptyState
            title="This selection cannot be requested"
            description={`${selectionError} No request was sent, so there are no groups to show. Correct the period or filters, or reset them.`}
          />
        ) : (
          <EmptyState
            title="No groups match this selection"
            description={
              spend.unknownDateCount > 0
                ? `${formatCount(spend.unknownDateCount)} claims match the filters but have no transaction date, so no group can be formed for them.`
                : "The API returned no groups for this period, filters and dimension."
            }
          />
        )
      )}
    </Card>
  );
}

function spendRowLabel(row: AnalyticsSpendRow, groupBy: AnalyticsGroupBy): string {
  switch (groupBy) {
    case "month":
      return formatMonthLabel(row.bucket_start);
    case "department":
      return row.department_name ?? "No department on the membership";
    case "location":
      return row.office_location_name ?? "No office location on the membership";
    case "category":
      return row.category ?? "No category recorded";
    case "employee":
      return row.employee_display_name ?? "Employee name not recorded";
    case "status":
      return row.status ? statusLabel(row.status) : "Status not recorded";
  }
}

// ---------------------------------------------------------------------------
// Charts (presentational only, drawn from returned values)
// ---------------------------------------------------------------------------

interface BarRow {
  currency?: string | null;
  claimCount: number;
  amountClaimCount: number;
  amountTotal?: string | null;
  label: string;
  /** Set when the row's grouping key is a workflow status, so a status pill can be used. */
  statusValue?: ExpenseStatus | null;
}

export function ChartCard({
  title,
  dimension,
  period,
  footnote,
  children,
}: {
  title: string;
  dimension: string;
  period: string;
  footnote: string;
  children: ReactNode;
}) {
  return (
    <figure className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
      <figcaption>
        <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text)]">{title}</h2>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          Dimension: {dimension} · Period: {period} · amounts are never combined across currencies
        </p>
      </figcaption>
      <div className="mt-4">{children}</div>
      <p className="mt-4 border-t border-[var(--color-border)] pt-3 text-[11px] leading-snug text-[var(--color-text-muted)]">
        {footnote}
      </p>
    </figure>
  );
}

/**
 * Horizontal bars, one series per currency.
 *
 * Chosen over a charting dependency for three reasons: the values stay exact strings, the
 * bar widths are computed from those digits rather than a float, and every bar is real
 * text in the accessibility tree, so a screen reader gets the same numbers a sighted
 * reviewer sees.
 */
export function AmountBars({
  rows,
  emptyMessage,
}: {
  rows: BarRow[];
  emptyMessage: string;
}) {
  if (rows.length === 0) {
    return <p className="text-sm text-[var(--color-text-muted)]">{emptyMessage}</p>;
  }

  const byCurrency = new Map<string, BarRow[]>();
  for (const row of rows) {
    const key = row.currency ?? "";
    const bucket = byCurrency.get(key);
    if (bucket) bucket.push(row);
    else byCurrency.set(key, [row]);
  }

  return (
    <div className="space-y-5">
      {[...byCurrency.entries()].map(([currencyKey, currencyRows]) => {
        const maximum = largestAmount(currencyRows.map((row) => row.amountTotal));
        return (
          <section key={currencyKey || "currency-not-recorded"}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
              {currencyKey || "Currency not recorded"}
            </h3>
            <ul className="space-y-3">
              {currencyRows.map((row, index) => (
                <li key={`${row.label}-${index}`}>
                  <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-xs">
                    <span className="min-w-0 truncate">
                      {row.statusValue ? (
                        <StatusPill status={row.statusValue} />
                      ) : (
                        row.label
                      )}
                    </span>
                    <span className="shrink-0 text-[var(--color-text-muted)]">
                      {formatCount(row.claimCount)} claims
                    </span>
                  </div>
                  {row.amountTotal != null ? (
                    <>
                      <div
                        className="h-2 overflow-hidden rounded-full bg-[var(--color-surface-muted)]"
                        role="img"
                        aria-label={`${row.label}: ${
                          currencyKey || "currency not recorded"
                        } ${row.amountTotal}, ${row.claimCount} claims`}
                      >
                        <span
                          className="block h-full rounded-full bg-[var(--color-accent)]"
                          style={{ width: `${decimalBarPercent(row.amountTotal, maximum)}%` }}
                        />
                      </div>
                      <p className="mt-1 text-right text-xs font-medium tabular-nums">
                        {formatDecimalCurrency(row.amountTotal, row.currency)}
                        {row.amountClaimCount < row.claimCount && (
                          <span className="ml-2 font-normal text-[var(--color-text-muted)]">
                            known for {formatCount(row.amountClaimCount)} of{" "}
                            {formatCount(row.claimCount)} claims
                          </span>
                        )}
                      </p>
                    </>
                  ) : (
                    <p className="text-xs text-[var(--color-text-muted)]">
                      No amount recorded · {formatCount(row.claimCount)} claims
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function StaleNotice({
  message,
  loadedSelection,
  isCurrentSelection,
  requestId,
}: {
  message: string;
  /** What the figures on screen actually asked for, when it is known. */
  loadedSelection: string | null;
  isCurrentSelection: boolean;
  requestId: string | null;
}) {
  return (
    <div
      role="alert"
      className="rounded-md border border-[var(--color-severity-warning)] bg-[var(--color-surface-muted)] px-4 py-3"
    >
      <p className="text-sm text-[var(--color-text)]">
        Showing the last result that loaded.{" "}
        {loadedSelection === null
          ? "It may not match the current controls."
          : isCurrentSelection
            ? `It is still the current selection: ${loadedSelection}.`
            : `It is NOT the current selection. Those figures are for ${loadedSelection}, and the controls have changed since.`}{" "}
        {message}
      </p>
      {requestId && (
        <p className="mt-1 font-mono text-[11px] text-[var(--color-text-muted)]">
          request id: {requestId}
        </p>
      )}
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">Loading live analytics from the backend</span>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        {[0, 1, 2, 3, 4, 5].map((key) => (
          <div
            key={key}
            className="space-y-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4"
          >
            <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
            <div className="h-6 w-1/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
            <div className="h-3 w-full animate-pulse rounded bg-[var(--color-surface-muted)]" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {[0, 1].map((key) => (
          <div
            key={key}
            className="h-40 animate-pulse rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)]"
          />
        ))}
      </div>
    </div>
  );
}

function DisclosureNotes() {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
        What these figures do not say
      </p>
      <ul className="mt-2 max-w-prose space-y-1 text-xs text-[var(--color-text-muted)]">
        <li>
          An <strong>approved</strong> workflow status means a person approved the claim. It is not
          a policy PASS, a reimbursement, or a payment, and no policy engine has evaluated these
          claims.
        </li>
        <li>
          <strong>Missing</strong> and <strong>uncertain</strong> critical fields are completeness
          facts from persisted values and current field evidence. They are not findings about an
          employee&apos;s conduct.
        </li>
        <li>
          The analytics service does not join duplicate-candidate rows, so nothing here is a
          duplicate count and nothing here asserts fraud.
        </li>
        <li>
          Amounts come back as exact decimal strings per currency. They are never converted or
          combined, so there is no single &ldquo;total spend&rdquo; figure.
        </li>
        <li>
          Claims with no transaction date cannot be assigned to a period. They are counted on this
          page and excluded from every chart rather than being shown as a zero.
        </li>
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

/**
 * Workflow status wording.
 *
 * Kept in one place and used for selects and chart legends alike. The status pills in
 * `@/components/ui` remain the single source of the coloured indicator.
 */
export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "Draft",
    submitted: "Submitted",
    needs_info: "Needs information",
    in_review: "Under review",
    approved: "Approved",
    rejected: "Not reimbursed",
    withdrawn: "Withdrawn",
  };
  return labels[status] ?? status;
}

export function groupLabel(group: AnalyticsGroupBy): string {
  const labels: Record<AnalyticsGroupBy, string> = {
    month: "Month",
    department: "Department",
    location: "Office location",
    category: "Category",
    employee: "Employee",
    status: "Workflow status",
  };
  return labels[group];
}
