import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

/**
 * Expense detail. A dynamic route so the shape of the page is settled before the data is.
 *
 * In Next 16 `params` is a promise, so it is awaited rather than read synchronously.
 */
export default async function ExpenseDetailPage({
  params,
}: {
  params: Promise<{ expenseId: string }>;
}) {
  const { expenseId } = await params;

  return (
    <>
      <PageHeader
        title="Expense detail"
        description="Receipt evidence, field provenance, findings and the audit trail for one claim."
      />

      <Card title="Requested claim">
        <p className="font-mono text-xs text-[var(--color-text-muted)]">{expenseId}</p>
      </Card>

      <PlaceholderNotice
        title="No claim data can be loaded"
        whatIsMissing={
          "This page reads GET /api/v1/expenses/{expense_id}, which is not implemented. " +
          "The identifier above is echoed from the URL only. When the endpoint exists, an " +
          "identifier the caller is not authorized to read must return the same response " +
          "as one that does not exist, so claim existence is never disclosed."
        }
        blockedOn="The claim detail route."
      />
    </>
  );
}
