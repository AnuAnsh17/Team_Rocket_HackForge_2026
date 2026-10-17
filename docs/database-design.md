# Database Design

**Engine:** PostgreSQL 18 (`postgres:18-alpine`). **ORM:** SQLAlchemy 2.x over psycopg3.
**Migrations:** Alembic, `backend/migrations/`. Baseline: `0001_initial_schema`.

**28 tables.** Verified by `backend/tests/integration/test_schema_integrity.py`, which
asserts the table set, the hand-written indexes, the append-only trigger and the
numeric type of every money column against a real database - not against SQLite, where
none of those guarantees have a meaningful equivalent.

## Entity relationships

```
organizations ─┬─ departments / cost_centers / office_locations / job_grades
               ├─ allowance_profiles ──── allowance_profile_items
               ├─ policy_documents ────── policy_versions ──┬── policy_rules
               │                                             └── policy_assignments
               ├─ policy_exceptions
               └─ users ── organization_memberships ─┬── reporting_relationships
                                                     └── role_assignments

organization_memberships ──┬── trips
                           └── expenses ─┬── expense_field_evidence
                                         ├── line_items
                                         ├── receipts ── extraction_runs
                                         ├── findings
                                         ├── duplicate_candidates (x2, as a pair)
                                         ├── review_decisions
                                         └── approval_tasks

audit_events        (no FKs - append-only, outlives its subjects)
idempotency_keys    (FK to users)
```

## Table responsibilities

### Tenancy and structure

| Table | Responsibility |
|---|---|
| `organizations` | The tenant boundary for every owned record. `slug` unique. `timezone` and `reporting_currency` are **nullable on purpose**: neither has been supplied, and defaulting them would invent a day-boundary rule and a currency. |
| `departments` | Self-referencing hierarchy. Unique `(organization_id, code)`. |
| `cost_centers` | Unique `(organization_id, code)`. |
| `office_locations` | A policy-resolution dimension. Carries `city`, `region`, `country_code` and its own optional `timezone`. |
| `job_grades` | **Empty. By design.** Grade levels and bands are organizational data; inventing a ladder would create the "higher grade means higher allowance" assumption the design forbids. |

### Identity, membership and authority

| Table | Responsibility |
|---|---|
| `users` | A global person. Carries **no** roles and **no** organization: identity is deliberately separate from authority. `auth_provider` + `external_subject` are the link to the identity provider and are uniquely paired. |
| `organization_memberships` | The org-scoped **employment** record: status, employee code, grade, department, cost center, office, joined/ended dates. Putting employment context here rather than in a separate profile table avoids two records that can disagree. Unique `(organization_id, user_id)`. |
| `reporting_relationships` | A historised manager edge with effective dates, rather than a manager column. This is what keeps "who approved this in March" answerable after a reorganisation. `employee_membership_id <> manager_membership_id` is enforced. |
| `role_assignments` | Grants one role inside one scope. `scope_id` is always populated (it equals the organization id for organization scope) because PostgreSQL treats NULLs as distinct in a unique index and an organization-scope grant with a NULL scope could otherwise be duplicated. |

### Policy and allowance

| Table | Responsibility |
|---|---|
| `policy_documents` | The source document and its `source_file_sha256`, which answers "which exact file governed this rule". The file itself is not stored here. |
| `policy_versions` | `review_state`, effective period, approver, source hash. Only `approved` versions govern. |
| `policy_rules` | One deterministic rule. `parameters` JSONB holds validated values only. `is_active` is constrained (see below). |
| `policy_assignments` | Assigns a version to a scope with an explicit `priority` and `approval_state`. A scope carries exactly one selector: `scope_id` (UUID) for a dimension that addresses a row in this database, or `scope_key` (text) for a dimension recorded as a code or name and having no table of its own. Which is which is defined once in `app/core/enums.py`; see `docs/role-policy-hierarchy.md`. Uniqueness is over the *effective* selector via the index below, not a plain unique constraint. |
| `policy_exceptions` | An explicit, authorized, time-bounded deviation. Requires a reason, an effective start, an approver when approved, and a currency when it carries an amount. |
| `allowance_profiles` / `allowance_profile_items` | A named set of allowances and its individual lines. Items carry the sourcing constraint below. |

### Claims and evidence

| Table | Responsibility |
|---|---|
| `trips` | Optional. Recorded only when actually supplied; the system never infers a trip from an employee's home city, because that would silently change which policy applies. |
| `expenses` | One claim. `version` is the optimistic-concurrency token. Holds current field values plus the original amount/currency and the reporting-conversion quartet (all NULL unless policy requires conversion). |
| `expense_field_evidence` | Immutable per-version, per-field provenance: value, `source`, `reviewed`, `confidence`, receipt region, `uncertainty_reason`, `is_current`. |
| `line_items` | Receipt lines with a policy-derived `eligibility`. |
| `receipts` | Private storage coordinates, `sha256`, optional `perceptual_hash`, dimensions, and derived variants via `derivation_type` + `parent_receipt_id`. |
| `extraction_runs` | One execution per row, so re-extraction appends rather than overwriting. Raw text is **not** stored: only `raw_text_sha256`, because retention rules are unanswered. |

### Review, audit and idempotency

| Table | Responsibility |
|---|---|
| `findings` | One tri-state rule outcome against one claim version, with evidence, calculation, expected/observed, `scope_fingerprint` and supersession link. |
| `duplicate_candidates` | A candidate pair with independent named signals, `algorithm_version`, `ranking_score` and reviewer resolution. |
| `review_decisions` | An executed decision, with the reporting edge that authorised it captured at decision time. |
| `approval_tasks` | A required approval step. Whether a step is required is policy/workflow configuration, not an assumption. |
| `audit_events` | Append-only application history. No foreign keys. |
| `idempotency_keys` | Stored first response for a retried mutation. Unique `(actor_user_id, idempotency_key)`. |

## Keys, constraints and indexes

### Naming convention

A `MetaData` naming convention generates `pk_`, `fk_`, `uq_`, `ck_`, `ix_` names
deterministically, so autogenerated migrations are reviewable and constraint names do
not differ between databases.

**Non-obvious rule:** PostgreSQL requires *index* names to be unique per **schema**,
while *constraint* names need only be unique per **table**. The convention therefore
produces globally unique names, and explicit `name=` arguments on `UniqueConstraint`
are forbidden - passing `name="organization_id_code"` on several tables would have
created colliding unique index names and failed the migration.

### Integrity guards (the interesting ones)

| Constraint | Table | Guarantee |
|---|---|---|
| `ck_policy_rules_source_requires_validation` | `policy_rules` | A rule may be `is_active` only with a source clause, validator, validation timestamp and evaluator type. An invented rule cannot be stored. |
| `ck_allowance_profile_items_limit_requires_source` | `allowance_profile_items` | An amount may be stored only with a cited clause and a currency. |
| `ck_expense_field_evidence_extraction_requires_receipt` | `expense_field_evidence` | `receipt_extraction` provenance requires a receipt id, so employee input cannot masquerade as receipt evidence. |
| `ck_review_decisions_rejection_requires_reason` | `review_decisions` | A rejection or correction request must carry a human-entered reason. |
| `ck_findings_failure_requires_evidence` | `findings` | A `FAIL` must carry an expected condition or a calculation. |
| `ck_findings_resolution_requires_state` | `findings` | `resolved`/`dismissed` requires a resolver and a timestamp. |
| `ck_duplicate_candidates_resolution_requires_state` | `duplicate_candidates` | A non-`open` candidate requires a resolver, timestamp and reason. |
| `ck_line_items_ineligibility_requires_reason` | `line_items` | An item may be `ineligible` only with a recorded reason. |
| `ck_policy_versions_approval_requires_approver` | `policy_versions` | `approved` requires an approver and timestamp. |
| `ck_users_external_identity_consistent` | `users` | Provider and subject are both set or both null. |
| `ck_expenses_amount_requires_currency` | `expenses` | An amount never exists without its currency. |
| `ck_policy_assignments_scope_selector_consistent` | `policy_assignments` | A scope carries exactly the selector its dimension needs and no other: a UUID-valued dimension requires `scope_id` and forbids `scope_key`; a text-valued dimension requires `scope_key` and forbids `scope_id`. This is what makes a category assignment stored against a UUID unstorable, rather than merely unlikely. |
| `ck_policy_assignments_scope_key_canonical` | `policy_assignments` | A text selector must equal its own canonical form: trimmed, internal whitespace collapsed, lowercased and non-blank. Enforced as a single equation against `scope_key` so trimming, collapsing and lowercasing cannot be partially applied. A blank key is refused because it could never match a claim, so the assignment would look configured and never apply. See `docs/role-policy-hierarchy.md` for the contract and its documented residue. |

### Hand-written indexes (Alembic cannot generate these)

| Index | Purpose |
|---|---|
| `uq_expense_field_evidence_current` (partial, `WHERE is_current`) | At most one current provenance row per (claim, field), so the denormalised columns and the evidence rows cannot drift. |
| `uq_duplicate_candidates_pair` | Unique on `(least(a,b), greatest(a,b), algorithm_version)`, so (A,B) and (B,A) cannot both exist and a reviewer is never shown one pair twice. |
| `uq_findings_identity` | Unique on `(expense_id, rule_id, expense_version, scope_fingerprint, COALESCE(policy_version_id, <zero-uuid>))`. Makes duplicate findings on a retry impossible rather than unlikely. The `COALESCE` is required because a structural finding legitimately has no policy version and PostgreSQL treats NULLs as distinct. |
| `uq_policy_assignments_scope_selector` | Unique on `(organization_id, policy_version_id, scope_type, COALESCE(scope_id::text, ''), COALESCE(scope_key, ''))`. Replaces the plain unique constraint that covered this table before text-valued dimensions existed. A plain constraint cannot express it: exactly one selector column is always NULL and PostgreSQL treats NULLs as distinct, so the same assignment could have been inserted twice. There is deliberately **no `lower()` here**: `scope_key` already stores the canonical form (enforced by the CHECK above), so uniqueness is over exactly the string the resolver compares. An earlier version applied `lower()` in the index while the resolver applied `casefold()`, which let two keys the resolver considered identical both be stored. |
| `ix_audit_events_entity`, `ix_audit_events_organization_created`, `ix_audit_events_actor_created`, `ix_audit_events_correlation` (partial) | The audit screens' query paths. |
| `ix_expenses_organization_status`, `ix_expenses_membership_expense_date`, `ix_expenses_trip` (partial) | Claim list, per-employee history and aggregate scope gathering. |
| `ix_receipts_organization_sha256` | The exact-duplicate signal lookup. Deliberately **not** unique. |
| `ix_receipts_expense`, `ix_extraction_runs_receipt`, `ix_findings_expense_status`, `ix_findings_result_severity`, `ix_duplicate_candidates_status`, `ix_approval_tasks_expense`, `ix_memberships_organization_status`, `ix_policy_assignments_scope`, `ix_policy_rules_active` (partial) | Review, queue and configuration paths. |

A partial index on `expenses (trip_id) WHERE trip_id IS NOT NULL` exists specifically
because `trip_id` is nullable and most claims have no trip.

### Append-only enforcement

```sql
CREATE FUNCTION proofline_audit_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not permitted', TG_OP
        USING ERRCODE = 'restrict_violation';
END; $$;

CREATE TRIGGER trg_audit_events_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION proofline_audit_events_append_only();
```

This is database-level append-only enforcement. It is **not** cryptographic
immutability: a database superuser can drop the trigger. It is not claimed to be more
than it is.

## Claim versioning and audit history semantics

- `expenses.version` starts at 1 and increments on every correction. It is the
  optimistic-concurrency token: a mutation carries `expected_version`, and a mismatch
  is refused with `STALE_VERSION` rather than overwriting newer work.
- `expense_field_evidence` rows are immutable and keyed by
  `(expense_id, expense_version, field_name)`. A correction inserts a new version's
  rows and moves `is_current`; it never edits an existing row.
- `findings` are keyed to the claim version that produced them and are never deleted.
  A superseded finding is linked through `superseded_by_finding_id`.
- `audit_events` records the actor, action, entity, safe before/after snapshots, the
  governing policy version and the correlation id. It shares a transaction with the
  change it describes: if the mutation fails, the event rolls back with it.
- **Nothing is hard-deleted to hide a change.** The only deletes in the system are
  demo-reset (scoped to the synthetic organization) and storage-object erasure for a
  retention request.

## Migration and seed procedures

```bash
# Apply
cd backend && ./.venv/Scripts/alembic upgrade head

# Roll back one revision / all the way
./.venv/Scripts/alembic downgrade -1
./.venv/Scripts/alembic downgrade base

# Show current revision
./.venv/Scripts/alembic current

# Autogenerate a NEW revision (never edit an applied one in place)
./.venv/Scripts/alembic revision --autogenerate -m "describe the change"
```

Verified behaviour of `0001_initial_schema`: upgrade creates 29 tables (28 + the
Alembic version table), the trigger and the hand-written indexes; `downgrade base`
removes all of them and drops the trigger function; re-upgrade restores the schema.

`migrations/env.py` reads the database URL from application settings, so there is one
source of database configuration and no credential can be committed to
`alembic.ini`.

### Seeding

```bash
# Load the deterministic synthetic dataset through the API (demo mode required)
curl -X POST http://localhost:8000/api/v1/demo/seed      -H "X-Demo-Actor-Id: <seeded admin user id>"

# Or directly, via the CLI helper
./.venv/Scripts/python scripts/dev_seed.py
```

The seed is idempotent: identifiers are derived deterministically with `uuid5`, so
running it twice reuses existing rows rather than duplicating them. It creates one
fictional organization, fictional people, memberships, role grants, reporting edges and
one **draft, empty** policy version - and deliberately no job grades, no allowance
limits, no policy rules and no claims. See `docs/demo-runbook.md`.

`scripts/dev_reset.py` removes only the synthetic organization and demo-provider
users, and refuses to run when `APP_ENV` is not a development value.

## Nullable dimensions and aggregate correctness

The build plan warns that nullable dimensions cause duplicate aggregate rows. Mitigations:

- No aggregate table exists, so there is nothing to reconcile.
- `EvaluationScope.dimensions` records an absent dimension as the explicit value
  `<absent>` rather than omitting the key, so "no trip" is distinct from "not
  consulted" and the fingerprint is stable.
- `gather_related_expenses` returns nothing when the period is unknown, and the caller
  records an unresolved reason. Returning every claim in the organization instead
  would produce a confidently wrong aggregate.
- `DEFAULT_AGGREGATE_INCLUDED_STATUSES` is an explicit, overridable constant rather
  than a condition buried in a query, because which states count is a policy question
  that has not been answered.
