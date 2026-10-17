/**
 * Shared employee-facing UI.
 *
 * The wording rules in this file are product requirements, not polish. An employee must
 * be able to tell the difference between "we need something from you", "there is a policy
 * issue", "this might be a duplicate" and "this is under review", and none of them may
 * read as an accusation.
 */

import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header>
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-prose text-sm text-[var(--color-text-muted)]">{description}</p>
    </header>
  );
}

export function Card({
  title,
  description,
  children,
  actions,
}: {
  title?: string;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-sm font-semibold">{title}</h2>}
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

/**
 * The four states an employee needs to distinguish.
 *
 * The wording is the point. "Needs information" asks for something. "Policy issue" states
 * a fact about the claim. "Possible duplicate" is explicitly a possibility. "Under
 * review" says a person is looking. None of them accuses.
 */
export type EmployeeState = "needs_info" | "policy_issue" | "possible_duplicate" | "in_review";

const STATE_COPY: Record<EmployeeState, { label: string; explanation: string; className: string }> = {
  needs_info: {
    label: "We need something from you",
    explanation:
      "Finance has asked for information that is missing from this claim. Add it and we will re-check the claim.",
    className: "border-[var(--color-status-needs-info)]",
  },
  policy_issue: {
    label: "This claim does not meet the policy",
    explanation:
      "A policy rule that applies to this claim is not satisfied. The finding shows the clause and the calculation, and you can comment or correct the claim.",
    className: "border-[var(--color-status-rejected)]",
  },
  possible_duplicate: {
    label: "This might have been submitted twice",
    explanation:
      "We found another claim that looks similar. A person will check it; nothing is assumed, and you do not need to do anything yet.",
    className: "border-[var(--color-severity-warning)]",
  },
  in_review: {
    label: "A person is reviewing this",
    explanation: "The claim is with finance. You will see a status change when there is a decision.",
    className: "border-[var(--color-status-in-review)]",
  },
};

export function EmployeeStatusBanner({ state }: { state: EmployeeState }) {
  const copy = STATE_COPY[state];
  return (
    <div className={`rounded-xl border-l-4 bg-[var(--color-surface-raised)] p-4 ${copy.className}`}>
      <p className="text-sm font-medium">{copy.label}</p>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">{copy.explanation}</p>
    </div>
  );
}

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
      className="rounded-xl border border-dashed border-[var(--color-severity-warning)] bg-[var(--color-surface-muted)] p-4"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-severity-warning)]">
        Not available yet
      </p>
      <p className="mt-1 text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">{whatIsMissing}</p>
      {blockedOn && (
        <p className="mt-2 text-xs text-[var(--color-text-muted)]">
          <span className="font-medium">Waiting on:</span> {blockedOn}
        </p>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] p-8 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-prose text-xs text-[var(--color-text-muted)]">
        {description}
      </p>
    </div>
  );
}
