import Link from "next/link";

import {
  Card,
  EmptyState,
  Metric,
  PageHeader,
  PlaceholderNotice,
  ResultBadge,
} from "@/components/ui";

/**
 * Overview.
 *
 * Deliberately renders NO numbers. The analytics API is implemented, but this overview
 * page does not consume it yet. Showing a plausible figure would be misleading.
 */
export default function OverviewPage() {
  return (
    <>
      <PageHeader
        title="Overview"
        description="Review queue, open findings, duplicate candidates and recent activity."
      />

      <PlaceholderNotice
        title="No metrics are shown on this page"
        whatIsMissing={
          "GET /api/v1/analytics/overview now returns persisted organization metrics, but this " +
          "page is not connected to it yet. A hard-coded or example number would be " +
          "indistinguishable from real data, so this page shows none."
        }
        blockedOn="The dashboard UI integration."
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric label="Awaiting review" value={null} basis="not yet available" />
        <Metric label="Open findings" value={null} basis="not yet available" />
        <Metric label="Duplicate candidates" value={null} basis="not yet available" />
        <Metric label="Needs information" value={null} basis="not yet available" />
      </div>

      <Card
        title="The tri-state contract"
        description="How every policy result will be presented once rules exist."
      >
        <div className="flex flex-wrap gap-3">
          <ResultBadge result="PASS" />
          <ResultBadge result="FAIL" />
          <ResultBadge result="UNKNOWN" />
        </div>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          UNKNOWN is a first-class outcome, not an error. It is the correct answer whenever
          required evidence or policy context is missing, and it is never presented as a
          pass. Today the backend&apos;s policy registry holds zero rules, so every claim
          would evaluate to UNKNOWN.
        </p>
      </Card>

      <Card title="Where the real work is" description="The two surfaces that prove the product.">
        <ul className="space-y-2 text-sm">
          <li>
            <Link className="underline" href="/review">
              Expense review workbench
            </Link>
            <span className="text-[var(--color-text-muted)]">
              {" "}
              — receipt evidence, corrected fields and findings with their clause.
            </span>
          </li>
          <li>
            <Link className="underline" href="/duplicates">
              Duplicate candidates
            </Link>
            <span className="text-[var(--color-text-muted)]">
              {" "}
              — matched signals shown side by side, confirmed or dismissed by a person.
            </span>
          </li>
        </ul>
      </Card>

      <EmptyState
        title="No claims in the queue"
        description="This placeholder does not load the claim queue or analytics yet; an empty display does not mean the organization has no expenses."
      />
    </>
  );
}
