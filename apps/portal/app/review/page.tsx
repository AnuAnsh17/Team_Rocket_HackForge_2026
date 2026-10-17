import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function ExtractionReviewPage() {
  return (
    <>
      <PageHeader
        title="Check the details"
        description="Confirm or correct what was read from your receipt before you submit it."
      />

      <PlaceholderNotice
        title="There is nothing to review"
        whatIsMissing={
          "No receipt has been read, because no extraction provider has been selected or " +
          "verified. When it is, this screen will show each field with where the value came " +
          "from, mark the ones the reader was unsure about, and let you correct them."
        }
        blockedOn="An extraction provider, and the receipt upload route."
      />

      <Card title="Each field will show its source" description="Why it matters that the two are distinguishable.">
        <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">Read from the receipt</span> — printed
            on the image. Shown with the region of the receipt it came from where the reader
            supports it.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Entered by you</span> — your own
            context, such as who the client was. Never shown as though it were on the
            receipt, and never stored as if it were evidence.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Uncertain</span> — the reader could
            not be sure. Marked explicitly, and it will ask you to confirm rather than
            assuming.
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          Some expenses also need details a receipt cannot contain, such as a client name or
          how many people attended. Which details are needed for which expense type is set by
          policy, and this build has no policy, so it will not guess.
        </p>
      </Card>
    </>
  );
}
