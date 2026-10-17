import { Card, PageHeader, PlaceholderNotice, SeverityBadge } from "@/components/ui";

export default function ReviewQueuePage() {
  return (
    <>
      <PageHeader
        title="Expense review"
        description="The review workbench: receipt evidence, extracted and corrected fields, and findings with their policy clause."
      />

      <PlaceholderNotice
        title="The review queue has no data source"
        whatIsMissing={
          "The queue reads GET /api/v1/expenses, and the claim workflow is not implemented. " +
          "No expense can be created, uploaded, submitted or evaluated yet, so there is " +
          "nothing to queue."
        }
        blockedOn="The claim, receipt upload and rule-evaluation routes."
      />

      <Card
        title="Intended layout"
        description="Three panes, so a reviewer never has to hold evidence in their head."
      >
        <ol className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">1. Original receipt</span> — the
            authorized content endpoint, with the region for the field in focus.
          </li>
          <li>
            <span className="text-[var(--color-text)]">2. Fields with provenance</span> —
            each value labelled with whether it came from the receipt, the employee or a
            reviewer correction, and whether a human has reviewed it.
          </li>
          <li>
            <span className="text-[var(--color-text)]">3. Findings</span> — rule clause,
            expected and observed values, the calculation, contributing receipts, the
            governing policy version and the recommended action.
          </li>
        </ol>
      </Card>

      <Card
        title="Severity vocabulary"
        description="Severity describes impact and routing. It never asserts misconduct."
      >
        <div className="flex flex-wrap gap-4">
          <SeverityBadge severity="info" />
          <SeverityBadge severity="warning" />
          <SeverityBadge severity="blocking" />
        </div>
      </Card>
    </>
  );
}
