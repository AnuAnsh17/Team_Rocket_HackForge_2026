import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function OrganizationAdminPage() {
  return (
    <>
      <PageHeader
        title="Organization administration"
        description="Memberships, roles, departments, cost centres, office locations and grades."
      />

      <PlaceholderNotice
        title="No administration routes exist"
        whatIsMissing={
          "The membership, role-assignment, department, cost-centre, location and grade " +
          "routes are not implemented. The tables and constraints exist; nothing reads or " +
          "writes them over HTTP yet."
        }
        blockedOn="The organization administration routes."
      />

      <Card
        title="Why grade data is absent rather than example data"
        description="Grade levels, bands and allowances are organizational data."
      >
        <p className="max-w-prose text-sm text-[var(--color-text-muted)]">
          The <span className="font-mono text-xs">job_grades</span> table ships empty, and
          the demo seed creates no grades, no allowance profiles and no limits. Inventing a
          grade ladder would silently create the assumption that a higher grade means a
          higher allowance, which the design explicitly refuses. The real set comes from the
          organization.
        </p>
      </Card>

      <Card
        title="A privileged role name grants nothing"
        description="What organization administrators can and cannot do."
      >
        <ul className="space-y-2 text-sm">
          <li className="text-[var(--color-text)]">
            Granted: <span className="text-[var(--color-text-muted)]">
              org:read, org:manage, membership:read, membership:manage, role:manage,
              profile:read_scoped, policy:read, policy_assignment:manage, allowance:manage,
              audit:read
            </span>
          </li>
          <li className="text-[var(--color-text)]">
            Not granted: <span className="text-[var(--color-text-muted)]">
              expense:decide_scoped, finding:resolve, duplicate:resolve, audit:export
            </span>
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          Administering people and deciding claims are different jobs. An administrator who
          should also review claims must be granted the finance reviewer role, which makes
          the extra authority visible in the role-assignment audit trail rather than implied
          by a job title. Enforced by the backend; a test asserts that no role holds every
          permission.
        </p>
      </Card>
    </>
  );
}
