import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function UploadPage() {
  return (
    <>
      <PageHeader
        title="Add a receipt"
        description="Photograph the receipt or choose an image, then check what was read from it before you submit."
      />

      <PlaceholderNotice
        title="Upload is not implemented"
        whatIsMissing={
          "The canonical upload route is POST /api/v1/expenses/{expense_id}/receipts. It is " +
          "not implemented, and no extraction provider has been selected, so this build " +
          "cannot read a receipt at all. The image would be stored privately if it were, and " +
          "never exposed through a public URL."
        }
        blockedOn="The expense creation and receipt upload routes."
      />

      <Card title="What will happen when you add a receipt" description="Four steps.">
        <ol className="space-y-3 text-sm">
          <li>
            <span className="font-medium">1. Check the file.</span>{" "}
            <span className="text-[var(--color-text-muted)]">
              The real file type is read from the file itself, not from its name. Oversized
              files are refused before anything is stored.
            </span>
          </li>
          <li>
            <span className="font-medium">2. Store it privately.</span>{" "}
            <span className="text-[var(--color-text-muted)]">
              The image is kept in private storage. It is never reachable by a permanent
              public link, and only you and authorized finance reviewers can see it.
            </span>
          </li>
          <li>
            <span className="font-medium">3. Read the details.</span>{" "}
            <span className="text-[var(--color-text-muted)]">
              Merchant, date, total and currency are extracted as evidence. Anything the
              reader is unsure about is marked as uncertain rather than guessed.
            </span>
          </li>
          <li>
            <span className="font-medium">4. You confirm.</span>{" "}
            <span className="text-[var(--color-text-muted)]">
              Nothing is submitted until you have seen and confirmed the values.
            </span>
          </li>
        </ol>
      </Card>

      <Card title="What we cannot promise" description="Worth knowing before you rely on it.">
        <p className="max-w-prose text-sm text-[var(--color-text-muted)]">
          A claim that looks fine here can still be questioned after you submit it, because
          limits and checks depend on the whole picture — your history, the month, and which
          policy version applies. This product never promises reimbursement.
        </p>
      </Card>
    </>
  );
}
