"use client";

/**
 * Department-wise expenditure and review workload.
 *
 * Every figure comes from `GET /api/v1/analytics/departments`, which aggregates in
 * PostgreSQL. Nothing here adds money values up: the organization total arrives with the
 * breakdown, so the section renders what the database computed rather than what the
 * browser could work out. Amounts are never combined across currencies, and a department
 * with no recorded membership is shown as "Unassigned" rather than dropped or guessed.
 *
 * The visual language follows the console's existing design system and reuses its CSS
 * tokens, so this reads as part of the same product rather than a second dashboard.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { createConsoleApi } from "@/lib/api";
import {
  barWidthPercent,
  buildDepartmentQuery,
  describeError,
  formatCount,
  formatDecimalCurrency,
  formatSharePercent,
  loadDepartments,
  widestRequested,
  type AnalyticsDepartmentSummary,
  type AnalyticsError,
  type AnalyticsFilters,
  type DateRange,
} from "@/lib/analytics";

const consoleApi = createConsoleApi();

interface SectionState {
  data: AnalyticsDepartmentSummary | null;
  error: AnalyticsError | null;
  loading: boolean;
  /** The request the held data belongs to, so a stale response can be labelled. */
  loadedQuery: string | null;
}

const INITIAL_STATE: SectionState = { data: null, error: null, loading: true, loadedQuery: null };

function amountLabel(value: string | null | undefined, currency: string | null | undefined) {
  if (value === null || value === undefined) return "—";
  return formatDecimalCurrency(value, currency ?? undefined);
}

export default function DepartmentSection({
  range,
  filters,
  reloadToken = 0,
}: {
  range: DateRange;
  filters: AnalyticsFilters;
  reloadToken?: number;
}) {
  const [state, setState] = useState<SectionState>(INITIAL_STATE);
  const generation = useRef(0);

  const query = buildDepartmentQuery(range, filters);
  const queryKey = JSON.stringify(query);

  const load = useCallback(
    (key: string, signal: AbortSignal, generationAtCall: number) => {
      setState((previous) => ({ ...previous, loading: true, error: null }));
      loadDepartments(consoleApi, JSON.parse(key), signal)
        .then((data) => {
          // A later request has already started: this response is stale, so it must not
          // overwrite the newer one.
          if (generation.current !== generationAtCall) return;
          setState({ data, error: null, loading: false, loadedQuery: key });
        })
        .catch((error: unknown) => {
          if (signal.aborted || generation.current !== generationAtCall) return;
          // Keep the previous figures but say so: never silently show stale data as
          // current, and never substitute zeros for a failed request.
          setState((previous) => ({
            data: previous.data,
            error: describeError(error),
            loading: false,
            loadedQuery: previous.loadedQuery,
          }));
        });
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    const generationAtCall = ++generation.current;
    load(queryKey, controller.signal, generationAtCall);
    return () => controller.abort();
  }, [queryKey, reloadToken, load]);

  const { data, error, loading } = state;
  const stale = error !== null && data !== null;

  if (data === null && loading) {
    return (
      <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6">
        <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text)]">
          Department expenditure
        </h2>
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">
          Loading department breakdown…
        </p>
      </section>
    );
  }

  if (data === null && error !== null) {
    return (
      <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6">
        <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text)]">
          Department expenditure
        </h2>
        <p className="mt-3 text-sm text-[var(--color-status-rejected)]">{error.title}</p>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">{error.message}</p>
        {error.requestId ? (
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Request id: <span className="font-mono">{error.requestId}</span>
          </p>
        ) : null}
        <button
          type="button"
          onClick={() => {
            const controller = new AbortController();
            load(queryKey, controller.signal, ++generation.current);
          }}
          className="mt-4 rounded-md border border-[var(--color-border-strong)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text)] hover:border-[var(--color-accent)]"
        >
          Retry
        </button>
      </section>
    );
  }

  const currencies = (data?.totals ?? []).map((total) => total.currency ?? "unassigned");

  return (
    <section aria-labelledby="department-heading" className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2
            id="department-heading"
            className="text-sm font-semibold tracking-wide text-[var(--color-text)]"
          >
            Department expenditure and review workload
          </h2>
          <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
            Requested is every persisted claim amount in the period. Approved is the subset in an
            approved workflow state — a review decision, not a payment — so it is never larger
            than requested. Department comes from each member&apos;s recorded membership.
          </p>
        </div>
        {loading ? (
          <span className="text-xs text-[var(--color-text-muted)]">Refreshing…</span>
        ) : null}
      </header>

      {stale ? (
        <p className="rounded-md border border-[var(--color-status-needs-info)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
          The figures below are the last result that loaded and may be out of date:{" "}
          {error?.message}
        </p>
      ) : null}

      {data!.departments.length === 0 ? (
        <p className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 text-sm text-[var(--color-text-muted)]">
          No department activity in the selected period. This is an empty result, not spend of
          zero: no dated claim matched these filters.
        </p>
      ) : null}

      {currencies.map((currency) => (
        <CurrencySection
          key={currency}
          currency={currency === "unassigned" ? null : currency}
          summary={data!}
        />
      ))}

      {data!.claims_with_unknown_transaction_date > 0 ? (
        <p className="text-xs text-[var(--color-text-muted)]">
          {formatCount(data!.claims_with_unknown_transaction_date)} claim(s) match these filters
          but have no transaction date. They are excluded from every department above and counted
          here instead, because an undated claim cannot be attributed to a period or a month.
        </p>
      ) : null}
    </section>
  );
}

function CurrencySection({
  currency,
  summary,
}: {
  currency: string | null;
  summary: AnalyticsDepartmentSummary;
}) {
  const rows = summary.departments.filter((row) => (row.currency ?? null) === currency);
  const totals = summary.totals.find((total) => (total.currency ?? null) === currency);
  if (rows.length === 0) return null;

  const widest = widestRequested(rows);
  const labelled = rows.map((row) => ({
    row,
    name: row.department_name ?? "Unassigned",
  }));

  return (
    <div className="space-y-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          {currency ?? "No currency recorded"}
        </h3>
        <span className="text-xs text-[var(--color-text-muted)]">
          {formatCount(totals?.claim_count ?? 0)} claims · {rows.length} department row(s)
        </span>
      </div>

      <KpiStrip totals={totals} currency={currency} />

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-accent)]">
          Requested versus approved
        </h4>
        <ul className="mt-3 space-y-2">
          {labelled.map(({ row, name }) => (
            <li key={`${row.department_id ?? "none"}`} className="grid grid-cols-[minmax(8rem,12rem)_1fr] items-center gap-3">
              <span className="truncate text-xs text-[var(--color-text)]" title={name}>
                {name}
              </span>
              <span className="relative block h-6">
                <span
                  className="absolute inset-y-0 left-0 rounded-sm bg-[var(--color-accent)] opacity-90"
                  style={{ width: `${barWidthPercent(row.amount_total, widest)}%` }}
                  aria-hidden="true"
                />
                <span
                  className="absolute left-0 rounded-sm bg-[var(--color-status-approved)]"
                  style={{
                    width: `${barWidthPercent(row.approved_amount_total, widest)}%`,
                    bottom: 0,
                    height: "0.3rem",
                  }}
                  aria-hidden="true"
                />
                <span className="relative z-10 pl-2 text-[11px] leading-6 text-[var(--color-text)]">
                  {amountLabel(row.amount_total, row.currency)} requested
                  {row.approved_amount_total
                    ? ` · ${amountLabel(row.approved_amount_total, row.currency)} approved`
                    : ""}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[52rem] border-collapse text-sm">
          <caption className="sr-only">
            Department-wise claims, requested and approved expenditure, review workload and share
            of requested expenditure for {currency ?? "claims with no currency"}.
          </caption>
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
              <th scope="col" className="py-2 pr-4 font-medium">Department</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Claims</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Requested</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Approved</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Awaiting review</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Rejected</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Average</th>
              <th scope="col" className="py-2 text-right font-medium">Share</th>
            </tr>
          </thead>
          <tbody>
            {labelled.map(({ row, name }) => (
              <tr
                key={`row-${row.department_id ?? "none"}`}
                className="border-b border-[var(--color-border)] last:border-0"
              >
                <th scope="row" className="py-2 pr-4 text-left font-normal text-[var(--color-text)]">
                  {name}
                </th>
                <td className="py-2 pr-4 text-right tabular-nums">{formatCount(row.claim_count)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {amountLabel(row.amount_total, row.currency)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {amountLabel(row.approved_amount_total, row.currency)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {formatCount(row.pending_review_count)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {formatCount(row.rejected_count)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {amountLabel(row.average_amount_total, row.currency)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {formatSharePercent(row.requested_share) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KpiStrip({
  totals,
  currency,
}: {
  totals: AnalyticsDepartmentSummary["totals"][number] | undefined;
  currency: string | null;
}) {
  const metrics: Array<{ label: string; value: string; tone?: string }> = [
    {
      label: "Requested",
      value: amountLabel(totals?.amount_total, currency),
      tone: "var(--color-accent)",
    },
    { label: "Approved", value: amountLabel(totals?.approved_amount_total, currency) },
    {
      label: "Awaiting review",
      value: formatCount(totals?.pending_review_count ?? 0),
      tone: "var(--color-status-needs-info)",
    },
    {
      label: "Rejected",
      value: formatCount(totals?.rejected_count ?? 0),
      tone: "var(--color-status-rejected)",
    },
    { label: "Needs information", value: formatCount(totals?.needs_info_count ?? 0) },
    { label: "Unassigned claims", value: formatCount(totals?.unassigned_claim_count ?? 0) },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
        >
          <dt className="text-[11px] uppercase tracking-wide text-[var(--color-text-muted)]">
            {metric.label}
          </dt>
          <dd
            className="mt-1 text-sm font-semibold tabular-nums text-[var(--color-text)]"
            style={metric.tone ? { color: metric.tone } : undefined}
          >
            {metric.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
