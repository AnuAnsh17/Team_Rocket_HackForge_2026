/**
 * Shared UI foundations.
 *
 * Deliberately small and unopinionated. The rule that matters most here is in
 * `PlaceholderNotice`: an unfinished feature says so on the screen. A finance reviewer
 * who mistakes a placeholder for a working queue will draw the wrong conclusion about
 * their own data, which is worse than a missing screen.
 */

import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header>
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-prose text-sm text-[var(--color-text-muted)]">{description}</p>
    </header>
  );
}

export function Card({
  title,
  description,
  actions,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && (
              <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text)]">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
                {description}
              </p>
            )}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Metric({
  label,
  value,
  basis,
}: {
  label: string;
  /** `null` renders as a dash. A KPI with no data must never render as a zero. */
  value: number | string | null;
  /** What the number is counted over. Required, because a count without a basis is a claim. */
  basis: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-[var(--color-text)]">
        {value === null ? "—" : value}
      </p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{basis}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status indicators
// ---------------------------------------------------------------------------

/**
 * Workflow status pill.
 *
 * The label is derived from the canonical `ExpenseStatus` values in
 * docs/api-contract.md. No value here implies wrongdoing; `rejected` means the claim was
 * not reimbursed, not that the employee did anything dishonest.
 */
const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-[var(--color-status-draft)]" },
  submitted: { label: "Submitted", className: "bg-[var(--color-status-submitted)]" },
  needs_info: { label: "Needs information", className: "bg-[var(--color-status-needs-info)]" },
  in_review: { label: "Under review", className: "bg-[var(--color-status-in-review)]" },
  approved: { label: "Approved", className: "bg-[var(--color-status-approved)]" },
  rejected: { label: "Not reimbursed", className: "bg-[var(--color-status-rejected)]" },
  withdrawn: { label: "Withdrawn", className: "bg-[var(--color-status-withdrawn)]" },
};

export function StatusPill({ status }: { status: string }) {
  const entry = STATUS_LABELS[status] ?? {
    label: "Unknown status",
    className: "bg-[var(--color-surface-muted)]",
  };
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-2.5 py-0.5 text-xs text-[var(--color-text)]">
      <span className={`h-2 w-2 rounded-full ${entry.className}`} aria-hidden="true" />
      {entry.label}
    </span>
  );
}

/**
 * Finding severity badge.
 *
 * Severity describes impact and routing. It is never a statement about conduct, and the
 * wording avoids words like "violation" or "suspicious".
 */
const SEVERITY_LABELS: Record<string, { label: string; className: string }> = {
  info: { label: "Informational", className: "bg-[var(--color-severity-info)]" },
  warning: { label: "Needs attention", className: "bg-[var(--color-severity-warning)]" },
  blocking: { label: "Blocks approval", className: "bg-[var(--color-severity-blocking)]" },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const entry = SEVERITY_LABELS[severity] ?? {
    label: "Unclassified",
    className: "bg-[var(--color-surface-muted)]",
  };
  return (
    <span className="inline-flex items-center gap-2 text-xs text-[var(--color-text)]">
      <span className={`h-2 w-2 rounded-sm ${entry.className}`} aria-hidden="true" />
      {entry.label}
    </span>
  );
}

/**
 * Tri-state rule result.
 *
 * `UNKNOWN` gets a real, visible treatment rather than a muted one. It is the correct
 * answer whenever evidence or policy context is missing, and the whole design depends on
 * it never being read as a pass.
 */
const RESULT_LABELS: Record<string, { label: string; className: string }> = {
  PASS: { label: "PASS — meets the policy", className: "bg-[var(--color-result-pass)]" },
  FAIL: { label: "FAIL — does not meet the policy", className: "bg-[var(--color-result-fail)]" },
  UNKNOWN: { label: "UNKNOWN — cannot be determined", className: "bg-[var(--color-result-unknown)]" },
};

export function ResultBadge({ result }: { result: string }) {
  const entry = RESULT_LABELS[result] ?? {
    label: "No result",
    className: "bg-[var(--color-surface-muted)]",
  };
  return (
    <span className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-2 py-0.5 text-xs font-medium text-[var(--color-text)]">
      <span className={`h-2 w-2 rounded-full ${entry.className}`} aria-hidden="true" />
      {entry.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

/**
 * The visible marker for an unfinished feature.
 *
 * Every scaffolded screen renders this, and it names what is missing rather than saying
 * "coming soon": the reader needs to know whether the data is absent because nothing is
 * built or because they have no data.
 */
export function PlaceholderNotice({
  title,
  whatIsMissing,
  blockedOn,
}: {
  title: string;
  whatIsMissing: string;
  blockedOn?: string;
}) {
  return (
    <div
      role="note"
      className="rounded-lg border border-dashed border-[var(--color-severity-warning)] bg-[var(--color-surface-muted)] p-4"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-severity-warning)]">
        Not implemented yet
      </p>
      <p className="mt-1 text-sm font-medium text-[var(--color-text)]">{title}</p>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">{whatIsMissing}</p>
      {blockedOn && (
        <p className="mt-2 text-xs text-[var(--color-text-muted)]">
          <span className="font-medium">Blocked on:</span> {blockedOn}
        </p>
      )}
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2 py-6">
      <span className="sr-only">{label}</span>
      <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-[var(--color-surface-muted)]" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--color-surface-muted)]" />
    </div>
  );
}

/**
 * Empty state.
 *
 * Distinguishes "there is nothing here" from "this is not built". The two look identical
 * to a user otherwise, and confusing them is how a broken feature appears healthy.
 */
export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] p-6 text-center">
      <p className="text-sm font-medium text-[var(--color-text)]">{title}</p>
      <p className="mx-auto mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
        {description}
      </p>
    </div>
  );
}

export function ErrorState({ title, message }: { title: string; message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-[var(--color-severity-blocking)] bg-[var(--color-surface-raised)] p-6"
    >
      <p className="text-sm font-medium text-[var(--color-text)]">{title}</p>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">{message}</p>
    </div>
  );
}

/**
 * Backend-unavailable state.
 *
 * Rendered with the request id when one is available, because that is the single piece of
 * information that makes a support conversation possible.
 */
export function UnavailableState({
  reason,
  requestId,
}: {
  reason: string;
  requestId?: string | null;
}) {
  return (
    <div role="alert" className="rounded-lg border border-[var(--color-border-strong)] p-6">
      <p className="text-sm font-medium text-[var(--color-text)]">
        This data is not available
      </p>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">{reason}</p>
      {requestId && (
        <p className="mt-2 font-mono text-xs text-[var(--color-text-muted)]">
          request id: {requestId}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

export interface Column<Row> {
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  /** Align numeric columns right so figures are comparable down the column. */
  numeric?: boolean;
}

export function DataTable<Row>({
  columns,
  rows,
  getRowKey,
  caption,
}: {
  columns: Array<Column<Row>>;
  rows: Row[];
  getRowKey: (row: Row, index: number) => string;
  caption?: string;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-[var(--color-border-strong)] text-left">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] ${
                  column.numeric ? "text-right" : ""
                }`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={getRowKey(row, index)}
              className="border-b border-[var(--color-border)] last:border-0"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2 text-[var(--color-text)] ${
                    column.numeric ? "text-right tabular-nums" : ""
                  }`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
