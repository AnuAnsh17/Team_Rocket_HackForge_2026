import { Card, EmptyState, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function CorrectionsPage() {
  return (
    <>
      <PageHeader
        title="Needs your input"
        description="Claims where finance has asked you for something specific."
      />

      <PlaceholderNotice
        title="No corrections can be requested or answered"
        whatIsMissing={
          "Reviewer decisions and claim corrections are not implemented. When they are, this " +
          "page will state exactly what is missing, let you add it, and re-check the claim. A " +
          "correction will create a new version of the claim rather than overwriting the old " +
          "one, so what you originally submitted stays on record."
        }
        blockedOn="The decision and correction routes."
      />

      <Card title="What a correction will never do" description="Two guarantees.">
        <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">
              It will not erase what you submitted.
            </span>{" "}
            A correction adds a version. The original values and the original receipt remain.
          </li>
          <li>
            <span className="text-[var(--color-text)]">
              It will not change your receipt.
            </span>{" "}
            Re-reading a receipt never overwrites a value a person has already confirmed.
          </li>
        </ul>
      </Card>

      <EmptyState
        title="Nothing needs you right now"
        description="No claim has a pending question, and corrections are not available in this build."
      />
    </>
  );
}
