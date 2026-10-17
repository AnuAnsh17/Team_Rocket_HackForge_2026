import Link from "next/link";

import { Card, EmptyState, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function MyExpensesPage() {
  return (
    <>
      <PageHeader
        title="My expenses"
        description="Everything you have submitted, with its current status."
      />

      <PlaceholderNotice
        title="No claims to list"
        whatIsMissing={
          "This page reads GET /api/v1/expenses, which is not implemented. The server scopes " +
          "the response to you: it does not return a filtered view of everyone's claims, and " +
          "no filtering happens in this page."
        }
        blockedOn="The expense list route."
      />

      <Card title="What you will be able to open">
        <p className="text-sm text-[var(--color-text-muted)]">
          Each row will open a claim showing its status in plain language, the receipt image,
          any finding with the policy clause behind it, and who did what to it and when.
        </p>
        <p className="mt-3 text-sm">
          <Link className="underline" href="/corrections">
            Claims that need something from you
          </Link>
        </p>
      </Card>

      <EmptyState
        title="Nothing here yet"
        description="There are no claims to show, and submission is not available in this build."
      />
    </>
  );
}
