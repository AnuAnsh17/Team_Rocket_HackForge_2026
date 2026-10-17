import { Card, EmptyState, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function AuditHistoryPage() {
  return (
    <>
      <PageHeader
        title="Audit history"
        description="Append-only record of who did what, with before and after values and a correlation id."
      />

      <PlaceholderNotice
        title="The organization-wide audit list is not implemented"
        whatIsMissing={
          "GET /api/v1/audit and the CSV export are not implemented. An actor can read " +
          "their own trail today at GET /api/v1/me/audit; the org-wide, filtered view " +
          "needs the reviewer permission model and the audit routes."
        }
        blockedOn="The audit read and export routes."
      />

      <Card
        title="What already holds"
        description="These are enforced by the database and covered by tests, not only documented."
      >
        <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">Append-only</span> — a trigger raises
            on UPDATE and DELETE against{" "}
            <span className="font-mono text-xs">audit_events</span>.
          </li>
          <li>
            <span className="text-[var(--color-text)]">No cascading foreign keys</span> — an
            audit record outlives the entity it refers to. A cascading action would make the
            database try to modify an append-only table, which is why deleting an
            organization previously failed.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Atomic with the change</span> — the
            event and the state change it describes share one transaction.
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          This is database-level append-only behaviour. It is <strong>not</strong>{" "}
          cryptographic immutability and is not tamper-evident against someone with database
          superuser rights.
        </p>
      </Card>

      <EmptyState
        title="No events to show"
        description="The org-wide audit view is not implemented yet. An actor's own trail is available from the API."
      />
    </>
  );
}
