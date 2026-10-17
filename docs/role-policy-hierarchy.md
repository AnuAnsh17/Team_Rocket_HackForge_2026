# Role, Hierarchy and Policy Resolution

**Status:** the entities, constraints, resolver interface and documentation exist.
The resolver is implemented (`app/policy/resolution.py`) and returns *unresolved* in
every case today, because no policy has been supplied. No grade level, allowance,
cap, threshold or approval rule has been invented anywhere in this repository.

## Why employee-specific policy needs more than a flat rule list

Two employees submitting the same 1,400.00 INR meal receipt may be governed by
different limits, different required approvals and different required context. A single
global threshold would either over-approve for one and over-reject for the other. So
policy is *resolved* per claim, from the employee's authoritative current profile.

## Dimension model

The schema supports these scope dimensions on `policy_assignments`:

| Dimension (`PolicyAssignmentScopeType`) | Resolved from |
|---|---|
| `organization` | the claim's organization |
| `legal_entity` | modelled; not resolvable until the organization records it |
| `jurisdiction` | `organizations.jurisdiction_code` |
| `office_location` | `organization_memberships.office_location_id` |
| `department` | `organization_memberships.department_id` |
| `cost_center` | `organization_memberships.cost_center_id` |
| `job_grade` | `organization_memberships.job_grade_id` |
| `trip` | `expenses.trip_id` |
| `expense_category` | `expenses.category` |
| `employee` | the claim's membership |
| explicit exception | `policy_exceptions`, time-bounded and authorised |

These are **supported** dimensions, not a claim that every organization uses this
hierarchy. An organization with no grades simply leaves `job_grade_id` null and that
dimension never matches.

## Precedence is configuration, not specificity

This is the most important rule in this document.

**The resolver does not assume that a more specific scope overrides a broader one, and
does not assume that a higher job grade means a higher allowance.** Both are common
conventions and both are policy semantics. Assuming either would silently change who
gets reimbursed.

`priority` is an integer on each assignment. It is compared **only after** the resolver
has established that the assignments genuinely apply to the claim. Resolution returns:

- **resolved** - exactly one approved policy version applies, with the applied
  assignments and their priorities recorded;
- **unresolved** - with an explicit reason, in any of these cases:
  - no approved assignment covers the claim's organization, context and effective period;
  - two approved assignments at equal priority point at different policy versions;
  - the matching assignments reference policy versions that are not approved;
  - a required dimension is missing (for example the organization's timezone);
  - the claim has no reliable transaction date, so the effective period cannot be
    determined.

`resolved: false` is a first-class answer, not an error. The caller is told the policy
context is unknown rather than handed a guess, and the claim evaluates to `UNKNOWN`
with `recommendation: review`.

## Effective dates

`policy_versions` and `policy_assignments` both carry `effective_from` / `effective_to`.
Matching uses the claim's **transaction date**, never today's date. A claim dated in
March must be judged against the policy in force in March, even if it is reviewed in
December. Both tables constrain `effective_to >= effective_from`.

`organizations.timezone` and `office_locations.timezone` exist because a period-based
rule needs a day boundary. Neither is defaulted. An unconfigured timezone produces an
unresolved reason - a guess would silently move claims between periods.

## Allowance profiles

`allowance_profiles` is a named set of allowances; `allowance_profile_items` holds the
individual lines. An item may be stored with **no amount** (a named category with no
verified cap is legitimate and useful). It may **not** be stored with an amount unless a
source clause and currency are recorded - enforced by
`ck_allowance_profile_items_limit_requires_source`, so an unsourced limit cannot exist
in the database at all.

A profile is only meaningful when `review_state = 'approved'` and it is reached through
a `policy_assignment` whose `approval_state = 'approved'`.

## Approval requirements

`approval_tasks` records a required approval step: stage, sequence, required role,
assignee membership, status, and `requirement_basis` - free text explaining *why* the
step exists (which rule, grade, amount or hierarchy edge).

**Whether a stage is required at all is decided by the approved policy and the
organization's configured workflow.** This schema does not assume that every
organization has HR, manager and finance stages, and does not invent thresholds at
which any of them trigger. An unknown workflow configuration produces no task and is
reported as unresolved rather than guessed.

Manager authority is relationship-based, not role-based: `manager` permission is
useless without a live `primary` or `secondary` edge in `reporting_relationships`.
A `dotted` relationship is recorded for context and confers no approval authority.

## Re-evaluation when profile or assignment changes

Changing an employee's grade, department, cost centre, office, manager edge, allowance
assignment, or publishing a new policy version can invalidate findings on claims that
are still in flight. `app/context/reevaluation.py` models each trigger
(`MEMBERSHIP_CONTEXT_CHANGED`, `ALLOWANCE_ASSIGNMENT_CHANGED`, `POLICY_VERSION_CHANGED`,
…) and produces a plan of which claims to re-evaluate and why.

Today every plan is recorded with an explicit `skipped_reasons` entry explaining that
the sweep cannot run against an empty rule set, rather than silently doing nothing.

## Preserving the governing version for historical decisions

- `expenses.evaluated_policy_version_id` records the policy version that most recently
  governed an evaluation, so a past decision stays explainable after the policy moves on.
- `findings.policy_version_id` is on every finding.
- `review_decisions.policy_version_id` is captured at decision time.
- `review_decisions.delegation_basis` records the reporting or approval edge that
  authorised the actor, so "who was entitled to approve this" survives a reorganisation.
- Both `policy_versions` and `approval_tasks` changes are visible in `audit_events`.

## What is deliberately not built

- An editable policy-authoring UI. Policy changes require review, tests and a version
  change, so authoring is out of initial scope.
- Any precedence algorithm. Precedence is configuration; inventing one would be
  inventing policy.
- Grade levels, bands and allowance amounts. Organizational data.
- Approval thresholds. Policy data.
