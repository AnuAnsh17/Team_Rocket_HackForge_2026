import { Card, EmptyState, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function ExceptionsPage() {
  return (
    <>
      <PageHeader
        title="Exceptions"
        description="Missing or uncertain evidence, arithmetic mismatches, individual rule findings and aggregate breaches."
      />

      <PlaceholderNotice
        title="Exception filters are not wired to a data source"
        whatIsMissing={
          "This view reads GET /api/v1/findings. No rule can execute, because the policy " +
          "registry holds zero rules and no approved policy document has been supplied, so " +
          "no finding exists to filter."
        }
        blockedOn="An approved policy document, and the findings routes."
      />

      <Card title="Intended filters" description="The dimensions a reviewer actually narrows by.">
        <ul className="grid grid-cols-2 gap-2 text-sm text-[var(--color-text-muted)]">
          <li>Result: PASS / FAIL / UNKNOWN</li>
          <li>Severity: informational / needs attention / blocks approval</li>
          <li>Status: open / acknowledged / resolved / dismissed</li>
          <li>Finding type, employee and date range</li>
        </ul>
      </Card>

      <EmptyState
        title="No exceptions"
        description="Nothing is listed because no evaluation has run, not because every claim is compliant."
      />
    </>
  );
}
