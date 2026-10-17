import { Card, EmployeeStatusBanner, PageHeader, PlaceholderNotice } from "@/components/ui";

export default async function ExpenseDetailPage({
  params,
}: {
  params: Promise<{ expenseId: string }>;
}) {
  const { expenseId } = await params;

  return (
    <>
      <PageHeader
        title="Your claim"
        description="Status, evidence and history for one claim."
      />

      <Card title="Claim">
        <p className="font-mono text-xs text-[var(--color-text-muted)]">{expenseId}</p>
      </Card>

      <PlaceholderNotice
        title="This claim cannot be loaded"
        whatIsMissing={
          "The claim detail route is not implemented. The identifier above is echoed from " +
          "the address only. If this claim belonged to someone else, the server would answer " +
          "exactly as it does for a claim that does not exist, so that nothing is revealed " +
          "about other people's expenses."
        }
        blockedOn="The claim detail route."
      />

      <Card title="How your status will read" description="Example wording, shown only to fix the vocabulary.">
        <div className="grid gap-3 sm:grid-cols-2">
          <EmployeeStatusBanner state="in_review" />
          <EmployeeStatusBanner state="needs_info" />
        </div>
      </Card>
    </>
  );
}
