import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function PolicyAssignmentAdminPage() {
  return (
    <>
      <PageHeader
        title="Policy assignment"
        description="Which approved policy version and allowance profile applies to which scope, and from when."
      />

      <PlaceholderNotice
        title="Assignment administration is not implemented"
        whatIsMissing={
          "The policy-assignment and allowance-profile routes are not implemented. The " +
          "scope model, effective dates, priority and approval state exist in the schema, " +
          "but nothing manages them yet."
        }
        blockedOn="The policy administration routes, and an approved policy to assign."
      />

      <Card
        title="Scope dimensions the model supports"
        description="Supported dimensions, not a claim that every organization uses all of them."
      >
        <ul className="grid grid-cols-2 gap-2 text-sm text-[var(--color-text-muted)]">
          <li>organization / legal entity</li>
          <li>jurisdiction</li>
          <li>office location</li>
          <li>department</li>
          <li>cost centre</li>
          <li>job grade</li>
          <li>trip</li>
          <li>expense category</li>
          <li>employee</li>
          <li>explicit, time-bounded exception</li>
        </ul>
      </Card>

      <Card
        title="Exceptions are deliberately narrow"
        description="An exception is authorized, justified and bounded in time."
      >
        <p className="max-w-prose text-sm text-[var(--color-text-muted)]">
          A policy exception requires a reason, an effective start date and an approver, and
          a currency whenever it carries an amount. None of those are optional in the
          schema, so an exception cannot be created quietly and cannot become permanent
          policy by accident.
        </p>
      </Card>
    </>
  );
}
