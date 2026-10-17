import { Card, EmptyState, EmployeeStatusBanner, PageHeader, PlaceholderNotice } from "@/components/ui";

/**
 * Employee home.
 *
 * Renders no totals. Every figure here would have to come from the backend, and the
 * expense endpoints are not implemented, so a plausible number would be invented.
 */
export default function HomePage() {
  return (
    <>
      <PageHeader
        title="My expenses"
        description="What you have submitted, what is waiting, and anything that needs you."
      />

      <PlaceholderNotice
        title="Nothing can be submitted yet"
        whatIsMissing={
          "Receipt upload, extraction and claim submission are not implemented, so there is " +
          "nothing to show here. This page will list this month's submitted total, pending " +
          "claims, anything needing your input and your recent claims - all derived from the " +
          "backend, never hard-coded."
        }
        blockedOn="The receipt upload and expense routes."
      />

      <Card title="How your claim will be described" description="Four states, four different meanings.">
        <div className="grid gap-3 sm:grid-cols-2">
          <EmployeeStatusBanner state="needs_info" />
          <EmployeeStatusBanner state="in_review" />
          <EmployeeStatusBanner state="policy_issue" />
          <EmployeeStatusBanner state="possible_duplicate" />
        </div>
      </Card>

      <EmptyState
        title="No claims yet"
        description="You have not submitted anything, and submission is not available in this build yet."
      />
    </>
  );
}
