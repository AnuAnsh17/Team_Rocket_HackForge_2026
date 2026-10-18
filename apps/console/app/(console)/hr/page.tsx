import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function HrReviewPage() {
  return (
    <>
      <PageHeader
        title="HR review"
        description="Employment status and profile context for a claim, and missing HR information."
      />

      <PlaceholderNotice
        title="No employee records are loaded"
        whatIsMissing={
          "This page reads scoped membership and profile data. The organization " +
          "administration routes are not implemented, and the HR reviewer role is " +
          "deliberately scoped: HR sees employment and profile context, and cannot resolve " +
          "finance findings or confirm duplicates."
        }
        blockedOn="The membership and profile read routes."
      />

      <Card
        title="What HR can and cannot do here"
        description="Taken from docs/authorization-matrix.md, which the backend enforces."
      >
        <ul className="space-y-2 text-sm">
          <li className="text-[var(--color-text)]">
            Granted: <span className="text-[var(--color-text-muted)]">
              profile:read_scoped, expense:read_org_scoped, hr:review, membership:read,
              approval_task read and decide, policy:read
            </span>
          </li>
          <li className="text-[var(--color-text)]">
            Not granted: <span className="text-[var(--color-text-muted)]">
              finding:resolve, duplicate:resolve, expense:decide_scoped
            </span>
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          These are enforced by the backend on every request. This screen only decides what
          to display.
        </p>
      </Card>
    </>
  );
}
