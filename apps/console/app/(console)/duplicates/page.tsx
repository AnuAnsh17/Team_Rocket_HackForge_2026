import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function DuplicatesPage() {
  return (
    <>
      <PageHeader
        title="Duplicate candidates"
        description="Possible duplicates with the independent signals behind each match, for a human to confirm or dismiss."
      />

      <PlaceholderNotice
        title="Candidates cannot be generated or listed yet"
        whatIsMissing={
          "Listing reads GET /api/v1/duplicates, and generating candidates needs persisted " +
          "claims and receipt images. Neither exists. The exact-hash and field-match signals " +
          "are implemented and unit-tested as pure functions, but nothing calls them from a " +
          "stored claim."
        }
        blockedOn="The receipt upload route and candidate persistence."
      />

      <Card
        title="How a candidate will be presented"
        description="Signals are shown separately, so a reviewer can judge the evidence rather than a score."
      >
        <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">Exact hash</span> — byte-identical
            files. Deterministic and reliable.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Perceptual similarity</span> —{" "}
            <strong>not implemented</strong>. It needs orientation-normalised image hashing
            and a threshold tuned against labelled pairs. No score is produced, because a
            fabricated one would be trusted.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Field agreement</span> — merchant,
            date, amount and currency. Shown, but never sufficient alone: two different
            meals can share a total and a date, and a test asserts exactly that case.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Channel context</span> — corroborating
            only.
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          Confirming or dismissing requires a reason and writes an audit event. Confirmation
          never labels an employee as fraudulent, and no similarity score can reject a claim
          on its own.
        </p>
      </Card>
    </>
  );
}
