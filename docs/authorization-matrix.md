# Authorization Matrix

**Status:** the permission model and claim lifecycle routes are implemented and tested
(`app/core/permissions.py`, `backend/tests/unit/test_permissions.py`,
`backend/tests/security/test_authorization.py`, and claim lifecycle integration tests).

## The rule that shapes everything else

**A privileged-sounding role name grants nothing.** Every capability is an explicit
permission, and every role's permission set is enumerated literally in
`ROLE_PERMISSIONS`. There is deliberately no "admin implies everything" shortcut.
The test suite asserts that no role holds the complete permission set.

Authorization is enforced in two independent stages, and **both must pass**:

1. **Permission** - a coarse capability gate. "May this actor decide claims at all?"
2. **Scope** - a resource-level check in `app/services/scope_service.py`. "May this
   actor decide *this* claim?"

Permission without scope is a horizontal privilege-escalation bug. Scope without
permission is a missing gate. Neither substitutes for the other.

## Permissions by role

Own-record permissions (`expense:create_own`, `expense:read_own`,
`expense:update_own`, `expense:submit_own`, `expense:withdraw_own`,
`receipt:upload_own`, `receipt:read_own`, `receipt:reextract_own`,
`profile:read_own`, `allowance:read_own`) are held by every role that represents a
person, including every administrative role. Nobody is exempt from being an employee.

| Role | Additional permissions beyond own-record | Explicitly NOT granted |
|---|---|---|
| `employee` | none | any scoped read, any decision |
| `manager` | `expense:read_team`, `receipt:read_scoped`, `profile:read_scoped`, `expense:decide_scoped`, `finding:read`, `approval_task:read`, `approval_task:decide` | organization-wide read, HR, policy, org administration |
| `hr_reviewer` | `profile:read_scoped`, `expense:read_org_scoped`, `hr:review`, `membership:read`, `approval_task:read`, `approval_task:decide`, `policy:read` | `finding:resolve`, `duplicate:resolve`, `expense:decide_scoped` |
| `finance_reviewer` | `expense:read_org_scoped`, `receipt:read_scoped`, `profile:read_scoped`, `expense:decide_scoped`, `finding:read`, `finding:resolve`, `duplicate:read`, `duplicate:resolve`, `approval_task:*`, `policy:read`, `analytics:read`, `audit:read` | `membership:manage`, `role:manage`, `audit:export` |
| `finance_admin` | the finance reviewer set, plus `review_queue:manage`, `analytics:read_org`, `audit:export` | `membership:manage`, `role:manage` |
| `org_admin` | `org:read`, `org:manage`, `membership:read`, `membership:manage`, `role:manage`, `profile:read_scoped`, `policy:read`, `policy_assignment:manage`, `allowance:manage`, `audit:read` | `expense:decide_scoped`, `finding:resolve`, `duplicate:resolve`, `audit:export` |
| `policy_admin` | `policy:read`, `policy:manage`, `policy_assignment:manage`, `allowance:manage`, `org:read`, `audit:read` | `membership:manage`, `role:manage`, `expense:decide_scoped` |
| `auditor` | `audit:read`, `audit:export`, `analytics:read`, `analytics:read_org`, `expense:read_org_scoped`, `finding:read`, `duplicate:read`, `policy:read` | **every mutation** - the auditor holds no write permission of any kind |
| `service` | `finding:read`, `expense:read_org_scoped` | everything else; internal scheduled work only |

Two entries deserve a note because they are the ones a reviewer would expect to be
broader than they are:

- **`org_admin` cannot decide expenses.** Administering people and administering
  claims are different jobs. An organization administrator who should also review
  claims must be granted `finance_reviewer` as well, which makes the extra authority
  visible in the role-assignment audit trail rather than implied by a job title.
- **`hr_reviewer` cannot resolve finance findings or confirm duplicates.** HR sees
  employment and profile context; the money decision stays with finance.

## Scope enforcement

`app/services/scope_service.py` implements the resource-level checks:

- `require_same_organization` - the tenant boundary. A valid permission from one
  organization never authorises access to another's records.
- `require_expense_read` - the owning employee; authorized finance, HR and auditor
  roles within the organization; a manager only through an active `primary` or
  `secondary` reporting edge. A `dotted` relationship is recorded for context and
  confers no approval authority.
- `require_expense_write` - the owner or an authorized finance reviewer.

Claim routes separately require the corresponding permission. An org-scoped read
role does not automatically receive mutation rights, and a manager's review
permission still requires a direct-report relationship. Claim submission, correction
and reviewer decisions use optimistic versions, idempotency keys and an audit event
in the same database transaction. Reviewer actions are workflow decisions and do not
turn unresolved policy into a `PASS`.

A record the caller may not see raises the **same** error a missing record raises, so
claim existence is not disclosed to an unauthorized caller.

## Reporting relationships

`reporting_relationships` is a table with effective dates rather than a manager column
on the membership row. That is what keeps "who approved this in March" answerable
after a reorganization. Only `primary` and `secondary` edges confer authority;
`effective_to` must be null or in the future for the edge to be live.

## Status codes

| Situation | Response |
|---|---|
| No credentials | `401 UNAUTHENTICATED` |
| Credentials resolve to no active user | `401 UNAUTHENTICATED` |
| Valid user, no active membership | `403 FORBIDDEN` |
| Valid membership, missing permission | `403 FORBIDDEN` |
| Valid permission, resource out of scope | `404 NOT_FOUND` (deliberately not 403) |
| Requested organization not one they belong to | `403 FORBIDDEN` |
| Demo mode disabled | `404` for demo routes; demo auth provider not constructed |

The 401/403 split is meaningful: a terminated membership is `403`, not `401`, because
we still know who the caller is - they simply may not act. A deactivated *user* is
`401`, because then there is no valid identity at all. Both are asserted in
`backend/tests/security/test_authorization.py`.

## What is still missing

- Role assignment lifecycles (`granted_at`, `revoked_at`, `reason`) are modelled and
  read, but no administration route writes them yet.
- Department-, cost-centre- and queue-level narrowing of finance review is modelled
  (`scope_type` / `scope_id` on `role_assignments`) but not yet applied to queries
  because review queues are configured by the approved workflow, which does not exist.
- Token revocation and expiry handling depend on choosing and implementing the
  production identity provider. See `docs/authentication-security.md`.
