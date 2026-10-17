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

| Dimension (`PolicyAssignmentScopeType`) | Resolved from | Selector |
|---|---|---|
| `organization` | the claim's organization | UUID |
| `legal_entity` | `organizations.legal_entity_name` | text key |
| `jurisdiction` | `organizations.jurisdiction_code` | text key |
| `office_location` | `organization_memberships.office_location_id` |
| `department` | `organization_memberships.department_id` |
| `cost_center` | `organization_memberships.cost_center_id` |
| `job_grade` | `organization_memberships.job_grade_id` |
| `trip` | `expenses.trip_id` |
| `expense_category` | `expenses.category` | text key |
| `employee` | the claim's membership | UUID |
| explicit exception | `policy_exceptions`, time-bounded and authorised | - |

These are **supported** dimensions, not a claim that every organization uses this
hierarchy. An organization with no grades simply leaves `job_grade_id` null and that
dimension never matches.

### Two kinds of selector, and why the distinction is explicit

A dimension is matched by **one** of two selectors (columns on `policy_assignments`):

- **UUID-valued** (`scope_id`): the dimension addresses a row in this database -
  organization, office location, department, cost centre, job grade, trip, employee.
- **Text-valued** (`scope_key`): the dimension is an attribute recorded as a code or a
  name, and has no table of its own, so there is no id to point at - legal entity,
  jurisdiction, expense category.

Which is which is defined **once**, in
`app/core/enums.py::UUID_VALUED_SCOPE_TYPES` / `TEXT_VALUED_SCOPE_TYPES`, and everything
else derives from that pair: the database CHECK constraint that refuses a mismatched
selector, the resolver's dispatch, and the tests. A dimension added to the enum without
being classified raises instead of silently never matching.

### The scope key normalization contract

Defined once, in `backend/app/core/scope_keys.py`. A text scope key's canonical form is:

```
canonical = collapse_whitespace(raw).casefold()
```

- `collapse_whitespace` trims, and collapses internal runs to one space, every character
  in `SCOPE_KEY_WHITESPACE`. That set is pinned by a test to exactly Python's
  `str.isspace()` definition (29 characters), so it cannot drift.
- `casefold()`, not `lower()`: case folding is the Unicode operation for caseless
  comparison, and the two differ for real input (`"straße".casefold() == "strasse"`).
- The canonical form is idempotent.

**`scope_key` stores the canonical form.** It is a matching key, not a display string:
display values come from the source entity, such as `organizations.legal_entity_name`.
The unique index is over that canonical column, so **database uniqueness is over exactly
the string the resolver compares** — by construction, not by two implementations agreeing.

That construction is deliberate, because the two had drifted. The resolver previously used
`strip().casefold()` while the index used `lower(coalesce(scope_key, ''))`, so `"in-mh"`
and `" in-mh "` could both be stored even though the resolver treated them as one key, and
Python's case folding is not PostgreSQL's lowercasing. The fix was not to reimplement case
folding in SQL; it was to remove the second implementation.

**What the database verifies independently.** A CHECK constraint requires that a stored
text key equals its own canonical form (trimmed, collapsed, lowercased, non-blank), using
PostgreSQL's `lower()` and the same whitespace character list. This is defence in depth
against a write that bypasses the application, and it is what refuses a blank key —
one that could never match anything.

**Known residue.** PostgreSQL cannot compute `casefold()`. A row written by a path that
bypasses the application *and* uses a character PostgreSQL's `lower()` leaves alone *and*
that Python's `casefold()` would change could still be stored non-canonically. Matching
canonicalizes **both** sides, so such a row still matches correctly rather than becoming
inert; the residue is that it could coexist with its canonical twin, which surfaces as a
reported resolution *conflict* rather than a silent duplicate. Closing it completely would
mean either restricting keys to ASCII (rejecting legitimate non-ASCII legal entity names)
or maintaining a hand-written replica of Unicode case folding in SQL — the mistake this
contract was written to undo.

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
