import { Card, EmptyState, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function ApprovalsPage() {
  return (
    <>
      <PageHeader
        title="My approval tasks"
        description="Approvals required by reporting line, grade, amount or policy."
      />

      <PlaceholderNotice
        title="No approval tasks can be created or listed"
        whatIsMissing={
          "Approval requirements come from the approved policy and the organization's " +
          "configured workflow. Neither exists, so nothing decides that a stage is " +
          "required, and this scaffold deliberately does not assume that every " +
          "organization has manager, HR and finance stages."
        }
        blockedOn="The approved policy document and the approval-task routes."
      />

      <Card
        title="Authority comes from a reporting relationship, not a job title"
        description="A manager link is shown only where a live relationship exists."
      >
        <p className="max-w-prose text-sm text-[var(--color-text-muted)]">
          Manager authority is resolved from a dated reporting relationship: only a live{" "}
          <span className="font-mono text-xs">primary</span> or{" "}
          <span className="font-mono text-xs">secondary</span> edge confers it. A{" "}
          <span className="font-mono text-xs">dotted</span> relationship is recorded for
          context and grants nothing. The relationships are stored with effective dates, so
          &ldquo;who was entitled to approve this in March&rdquo; stays answerable after a
          reorganisation.
        </p>
      </Card>

      <EmptyState
        title="No tasks assigned"
        description="Approval stages are not configured yet, so nothing has been routed to you."
      />
    </>
  );
}
