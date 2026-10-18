import Link from "next/link";

import AnalyticsDashboard from "@/components/AnalyticsDashboard";
import { Card, PlaceholderNotice, ResultBadge } from "@/components/ui";

/**
 * Overview: Finance/Admin spend analytics.
 *
 * The metrics on this page come from real backend requests to
 * `GET /api/v1/analytics/overview` and `GET /api/v1/analytics/spend` for the selected
 * period, filters and grouping dimension. Nothing here is hard-coded, and no section
 * renders substituted figures when a request fails.
 *
 * Everything the analytics API does not expose stays marked as unimplemented rather than
 * approximated: there is no review queue, findings list, duplicate-candidate list or
 * activity feed, because those routes do not exist yet.
 */
export default function OverviewPage() {
  return (
    <>
      <AnalyticsDashboard />

      <PlaceholderNotice
        title="This page shows analytics only"
        whatIsMissing={
          "The review queue, open findings, duplicate candidates and recent-activity feed are " +
          "not implemented: GET /api/v1/findings, GET /api/v1/duplicates and GET /api/v1/audit " +
          "do not exist yet. No figure on this page stands in for them, and the totals above are " +
          "not a work queue."
        }
        blockedOn="Rule evaluation, candidate persistence and organization-scoped audit reads."
      />

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
          required evidence or policy context is missing, and it is never presented as a pass. The
          analytics figures above are workflow and completeness measures: an approval is not a
          policy result, because the backend&apos;s policy registry still holds zero rules.
        </p>
      </Card>

      <Card
        title="Where the rest of the work is"
        description="Surfaces that are still scaffolds."
      >
        <ul className="space-y-2 text-sm">
          <li>
            <Link className="underline" href="/review">
              Expense review workbench
            </Link>
            <span className="text-[var(--color-text-muted)]">
              {" "}
              — receipt evidence, corrected fields and findings with their clause. Not built yet.
            </span>
          </li>
          <li>
            <Link className="underline" href="/duplicates">
              Duplicate candidates
            </Link>
            <span className="text-[var(--color-text-muted)]">
              {" "}
              — matched signals shown side by side, confirmed or dismissed by a person. Not built
              yet; the analytics API deliberately does not join candidate rows.
            </span>
          </li>
        </ul>
      </Card>
    </>
  );
}
