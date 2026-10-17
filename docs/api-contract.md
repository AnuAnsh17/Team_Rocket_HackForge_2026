# Proofline API Contract

**Contract version:** 1.1.1-scaffold
**Base path:** /api/v1
**Status:** Implemented baseline. FastAPI's generated OpenAPI document is the
machine-readable source of truth and must remain aligned with this document. A
contract test (`backend/tests/contract/test_openapi_contract.py`) fails the build
when an implemented route is missing from this file.

This document describes the **whole** contract, including endpoints that are not
implemented yet. Section 6 states, per route, whether it is implemented, declared
unimplemented, or planned. Nothing here should be read as a claim that an
unimplemented route works.

## Decision log

| Change | Decision | Reason |
|---|---|---|
| 1.0-draft -> 1.1 | Receipt upload is only `POST /api/v1/expenses/{expense_id}/receipts` | The build plan listed a second bare `POST /api/v1/receipts`. Two upload routes would mean two authorization paths and orphan receipts. The expense-scoped route makes ownership checks and cleanup trivial. |
| 1.0-draft -> 1.1 | `RecommendedAction` added as its own enum | The build plan used `request_correction` and this document used `review`, which is not a `ReviewAction`. Advice and executed decisions are different things. |
| 1.0-draft -> 1.1 | One canonical `amount` structure including provenance | The two documents disagreed on whether an amount carries `source`/`reviewed`. Provenance must not depend on which field it is. |
| 1.0-draft -> 1.1 | Invalid `FieldSource` examples corrected to `receipt_extraction` | The build plan used `"source": "receipt"`, which is not a member of its own enum. |
| 1.0-draft -> 1.1 | All public ids are UUIDs | Replaces `exp_01JEXAMPLE`-style prefixed ids, which imply a sequential/opaque scheme the schema does not use. |
| 1.0-draft -> 1.1 | Pagination is `limit` + opaque `next_cursor` + `total` | The old prose allowed "limit, cursor or offset". One shape is required for a shared client. |
| 1.0-draft -> 1.1 | Demo routes answer 404 when demo mode is off | The old text allowed 404 or 403. 404 does not disclose that a disabled demo surface exists. |
| 1.0-draft -> 1.1 | `Idempotency-Key` required on create/submit/decision mutations | The old text required it for create/submit and merely encouraged it elsewhere, which is not a testable rule. |
| 1.1 -> 1.1.1 | A policy-assignment scope carries exactly one of `scope_id` (UUID) or `scope_key` (text), decided by the dimension | Three of the ten dimensions are not UUID-valued (legal entity, jurisdiction, expense category), and a single UUID column could not express them, so assignments scoped to those dimensions never matched. Uniqueness is now over the effective selector. No route is affected today: the policy routes are declared unimplemented. |

---

## 1. Core invariants

1. One shared API serves the employee Android app, the employee web portal and the
   internal HR/Finance/Admin console.
2. Only the backend performs authoritative policy evaluation and workflow state
   transitions. Neither client implements a reimbursement rule.
3. All clients use the same canonical DTOs, enums, error envelope and pagination.
4. Money is persisted as NUMERIC/Decimal. JSON money values are **decimal strings**.
   A JSON number is rejected on input, because binary floating point cannot
   represent most currency amounts exactly.
5. Public identifiers are UUIDs. Dates are ISO `YYYY-MM-DD`; timestamps are ISO 8601
   UTC; currencies are ISO 4217 codes.
6. State-changing operations are authorized, validated, concurrency-aware and
   audited in the same transaction as the change they cause.
7. Missing or ambiguous evidence returns `UNKNOWN`. A possible duplicate is never a
   confirmed duplicate.
8. Receipt content is private. No DTO contains a storage key, bucket name or
   permanent URL.
9. Extraction produces evidence, never a policy decision.
10. No business rule or threshold may be implemented before it maps to a verified
    policy clause. See `docs/policy-assumptions.md`.

---

## 2. Canonical enums

These are the only permitted values. `GET /api/v1/meta/enums` publishes the same
list from the running service, and the contract test compares the two.

| Enum | Values |
|---|---|
| `ExpenseStatus` | `draft`, `submitted`, `needs_info`, `in_review`, `approved`, `rejected`, `withdrawn` |
| `ExpenseChannel` | `android`, `web`, `bulk`, `email_simulated` |
| `RuleResult` | `PASS`, `FAIL`, `UNKNOWN` |
| `FindingSeverity` | `info`, `warning`, `blocking` |
| `FindingStatus` | `open`, `acknowledged`, `resolved`, `dismissed` |
| `FindingType` | `required_field_missing`, `field_uncertain`, `arithmetic_mismatch`, `individual_limit_exceeded`, `aggregate_limit_exceeded`, `ineligible_category`, `ineligible_line_item`, `missing_policy_context`, `policy_conflict`, `duplicate_candidate`, `approval_required`, `extraction_failed` |
| `DuplicateStatus` | `open`, `confirmed`, `dismissed` |
| `ReviewAction` | `approve`, `reject`, `request_correction`, `escalate` |
| `RecommendedAction` | `none`, `review`, `request_correction`, `escalate` |
| `FieldSource` | `receipt_extraction`, `employee_input`, `reviewer_correction`, `imported_data`, `computed` |
| `LineItemEligibility` | `eligible`, `ineligible`, `partial`, `unknown`, `not_evaluated` |
| `ExtractionStatus` | `pending`, `running`, `success`, `partial`, `failed`, `unavailable` |
| `DerivationType` | `original`, `crop`, `rotation`, `recompression`, `thumbnail` |
| `StorageBackend` | `local`, `supabase`, `s3` |
| `MembershipStatus` | `active`, `on_leave`, `suspended`, `terminated`, `invited` |
| `RoleCode` | `employee`, `manager`, `hr_reviewer`, `finance_reviewer`, `finance_admin`, `org_admin`, `policy_admin`, `auditor`, `service` |
| `PolicyReviewState` | `draft`, `proposed`, `approved`, `superseded`, `retired` |
| `ApprovalState` | `pending`, `approved`, `rejected` |
| `ApprovalTaskStatus` | `pending`, `in_progress`, `approved`, `rejected`, `cancelled`, `skipped` |
| `PolicyAssignmentScopeType` | `organization`, `legal_entity`, `jurisdiction`, `office_location`, `department`, `cost_center`, `job_grade`, `trip`, `expense_category`, `employee` |
| `PolicyExceptionType` | `limit_override`, `category_allowance`, `approval_waiver`, `other` |
| `AuditActorType` | `user`, `system`, `service`, `demo` |
| `TripStatus` | `planned`, `active`, `completed`, `cancelled` |
| `ExpenseFieldName` | `merchant`, `expense_date`, `amount`, `currency`, `category`, `business_purpose`, `client_name`, `attendee_count`, `trip_id`, `receipt_number` |

Notes that are semantics, not style:

- `RecommendedAction` is **not** `ReviewAction`. A recommendation is advice attached
  to a finding; a `ReviewAction` is a decision an authorized reviewer actually
  executes. `recommended_action: "review"` therefore has no `ReviewAction`
  equivalent, which is why the enums are separate.
- `FindingSeverity` describes impact and routing. It never asserts guilt or fraud.
- `ExpenseStatus.WITHDRAWN` is reserved. No endpoint produces it (section 6).
- `email_simulated` is a demo-only channel. It must never be presented as a real
  email integration.
- `LineItemEligibility.NOT_EVALUATED` and `UNKNOWN` are both legitimate. An item
  whose treatment depends on an unverified rule stays `UNKNOWN`; it is never
  reported as ineligible.

---

## 3. Canonical DTOs

### 3.1 Field value and provenance

```json
{
  "value": "Example Merchant",
  "source": "receipt_extraction",
  "reviewed": true,
  "confidence": 0.94,
  "evidence": { "receipt_id": "0198f2b4-...", "page": 1, "region": null },
  "uncertainty_reason": null
}
```

- `source` is mandatory and is assigned by the server from the caller's role. A
  client never sends it, so an employee cannot claim reviewer provenance.
- `confidence` is an optional provider quality signal. It is **not** a calibrated
  probability, and it is `null` whenever the provider supplies no meaningful value
  rather than being invented.
- `evidence.region` is populated only when the provider actually reports
  coordinates. An absent region is `null`; it is never fabricated.
- A field can hold a value and still be uncertain. `uncertainty_reason` carries why.
- Employee-entered values never masquerade as receipt evidence: the database refuses
  a row claiming `receipt_extraction` provenance without a receipt id.
- A value whose provenance is missing, or which is flagged uncertain, is not
  `usable` and cannot be relied on by a deterministic rule. That decision is made in
  exactly one place (`FieldSnapshot.usable`), so no rule re-implements it.

### 3.2 Money - the single canonical monetary structure

```json
{
  "value": "1400.00",
  "currency": "INR",
  "source": "receipt_extraction",
  "reviewed": true,
  "confidence": 0.91,
  "evidence": { "receipt_id": "0198f2b4-...", "page": 1 },
  "uncertainty_reason": null
}
```

This is a contract decision made during scaffolding, recorded in the decision log
above. There is now exactly one structure, used everywhere an amount appears,
including provenance - because a reviewer must always be able to see whether a total
came from a receipt or from the employee.

Implementation notes:

- `value` serialises as a decimal string, never a JSON number.
- The generated JSON schema says `string` for `value`. Without an explicit
  annotation Pydantic emits `number` alongside it for `Decimal`, which would make a
  generated TypeScript client do float arithmetic and silently lose paise before the
  value ever reached the API.
- Sending a JSON number for `value` is rejected with `VALIDATION_ERROR`.
- `NonNegativeMoney` is the derived-value variant (`value`, `currency`, `rate`,
  `rate_date`, `rate_source`) used for `amount_reporting`. It carries no `source`
  because a converted figure is computed, not observed. It is `null` unless the
  approved policy requires conversion; this build applies no exchange rate.

### 3.3 Finding

See the canonical shape in `docs/database-design.md` and the example in the
appendix. Rules:

- `result` is tri-state and `UNKNOWN` is a legitimate, non-accusatory answer.
- A `FAIL` finding cannot be constructed without either `expected` or `calculation`.
  The model raises, so a failure without evidence cannot reach a reviewer.
- `source_reference` is `null` only for structural checks that do not depend on a
  policy clause, such as "the claim has a receipt".
- `recommended_action` is advisory. It does not itself change the claim.
- Superseded findings are retained and linked through `superseded_by_finding_id`.
  History is never deleted to hide a change.
- Aggregate findings include the exact evaluated scope and contributor ids.

### 3.4 Expense

```json
{
  "id": "0198f2b4-...",
  "version": 2,
  "organization_id": "0198f2b4-...",
  "employee": { "id": "0198f2b4-...", "display_name": "Demo Employee", "is_active": true },
  "channel": "android",
  "status": "needs_info",
  "trip_id": null,
  "trip": null,
  "merchant": { "value": "Example Cafe", "source": "receipt_extraction", "reviewed": false,
                "confidence": 0.94,
                "evidence": { "receipt_id": "0198f2b4-...", "page": 1, "region": null },
                "uncertainty_reason": null },
  "expense_date": { "value": "2026-10-14", "source": "receipt_extraction", "reviewed": true },
  "amount": { "value": "1400.00", "currency": "INR", "source": "receipt_extraction",
              "reviewed": true },
  "receipt_number": null,
  "category": "meal",
  "business_purpose": "Client meeting",
  "client_name": null,
  "attendee_count": 2,
  "amount_reporting": null,
  "receipts": [
    { "id": "0198f2b4-...",
      "content_url": "/api/v1/receipts/0198f2b4-.../content",
      "extraction_status": "pending",
      "detected_mime_type": "image/jpeg",
      "derivation_type": "original",
      "uploaded_at": "2026-10-17T12:00:00Z" }
  ],
  "line_items": [],
  "findings": [],
  "evaluated_policy_version_id": null,
  "submitted_at": null,
  "decided_at": null,
  "created_at": "2026-10-17T12:00:00Z",
  "updated_at": "2026-10-17T12:05:00Z"
}
```

Rules:

- `version` is the optimistic-concurrency token. It is mandatory on every mutation
  as `expected_version`, and a mismatch is refused with `STALE_VERSION` rather than
  silently overwriting newer work.
- `content_url` is a relative path to an authorized endpoint. It is not a storage
  path, it is not public, and the endpoint re-checks authorization on every request.
- `line_items` never carries per-field provenance. Only whole claim fields have a
  tracked source.
- `amount_reporting` is `null` unless the approved policy requires conversion.

### 3.5 Line item

```json
{
  "id": "0198f2b4-...",
  "line_number": 1,
  "description": "Set menu",
  "quantity": "2.000",
  "unit_amount": "700.00",
  "amount": "1400.00",
  "currency": "INR",
  "tax_amount": null,
  "discount_amount": null,
  "category": null,
  "eligibility": "not_evaluated",
  "ineligibility_reason": null
}
```

An item may only be marked `ineligible` when a reason is recorded; the database
enforces it.

### 3.6 Receipt, extraction run and duplicate candidate

A receipt DTO carries `id`, `expense_id`, `storage_backend`, `content_url`,
`original_filename`, `detected_mime_type`, `byte_size`, `sha256`, `perceptual_hash`,
image dimensions, `derivation_type`, `parent_receipt_id`, `extraction_status`,
`uploaded_at` and its `extraction_runs`. It never carries an object key or bucket
name. `sha256` is a real duplicate signal and is indexed but deliberately not
unique: two identical uploads are legitimate and are exactly the case the detector
must surface.

An extraction run carries `provider`, `model`, `prompt_version`, `status`,
timings, `latency_ms`, `error_code` and `is_cached_result`. `is_cached_result`
exists so a cached demo response is never presented as live inference. Runs are
append-only: re-extraction adds a run and never overwrites the previous one or a
reviewer-corrected value.

A duplicate candidate carries `id`, `status`, both expense ids,
`algorithm_version`, a list of independent `signals`, `ranking_score`,
`cross_channel`, reviewer resolution and timestamps. `ranking_score` orders a review
queue. It is not a probability and is not calibrated against any labelled set.
A candidate is never a confirmed duplicate and never fraud; confirmation requires a
human decision with a reason.

---

## 4. Common API behaviour

### 4.1 Request metadata

- Base path is always `/api/v1`.
- `X-Request-ID` is optional from the client. The server creates one when absent and
  always returns it as `X-Request-ID`. A client-supplied value is accepted only if it
  is short and printable; otherwise it is replaced.
- `Idempotency-Key` is required on create, submit and every decision mutation. A
  retry with the same key and body replays the stored response; a retry with the same
  key and a different body is refused with `IDEMPOTENCY_CONFLICT`.
- `expected_version` is required on corrections and decisions.
- JSON is used unless an endpoint explicitly accepts multipart upload or CSV.

### 4.2 Error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed.",
    "details": [ { "location": ["body", "amount"], "message": "...", "type": "value_error" } ],
    "request_id": "req_example"
  }
}
```

Recommended codes: `VALIDATION_ERROR`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`,
`CONFLICT`, `STALE_VERSION`, `IDEMPOTENCY_CONFLICT`, `POLICY_CONTEXT_UNKNOWN`,
`EXTRACTION_FAILED`, `UNSUPPORTED_MEDIA_TYPE`, `PAYLOAD_TOO_LARGE`, `RATE_LIMITED`,
`NOT_IMPLEMENTED`, `INTERNAL_ERROR`.

The contract test asserts that every documented code is implemented, so a code
cannot be promised here without existing in `app/core/errors.py`.

No response ever contains a stack trace, SQL fragment, driver message, credentials
or receipt payload. Unexpected errors return a generic message plus the request id.

### 4.3 Pagination

```json
{ "items": [], "page": { "limit": 50, "next_cursor": null, "total": 0 } }
```

- `limit` defaults to 50 and is capped at 200.
- `next_cursor` is opaque and integrity-checked. It is emitted only when a further
  page exists, so a client never loops on an empty trailing page. The current
  implementation encodes an offset and is deliberately opaque so it can become a
  keyset cursor later without a contract change.
- `total` may be omitted (`null`) only when that choice is consistent and documented
  for that endpoint.

### 4.4 Time boundaries and currency

- Timestamps are UTC ISO 8601 with a `Z` suffix.
- The day boundary for any period-based rule is defined by the organization's or
  location's configured timezone. It is **not** defaulted; an unconfigured timezone
  produces an unresolved reason and therefore `UNKNOWN`, never a guess.
- Conversion happens only when the approved policy requires it, using a documented
  rate source and date. No rate is applied by this build.

---

## 5. Endpoint inventory and implementation status

Status values:

- **Implemented** - served today and covered by tests.
- **Not implemented** - the route is absent or answers `501`. Also declared by
  `GET /api/v1/meta` under `unimplemented_capabilities`.
- **Deferred** - deliberately not built yet because it depends on the unverified
  policy document or on an undecided provider.

### 5.1 Implemented

| Route | Purpose |
|---|---|
| `GET /api/v1/health` | Service and dependency health. Unauthenticated by design. No secrets. |
| `GET /api/v1/openapi.json` | Generated OpenAPI document. |
| `GET /api/v1/meta` | Contract version, implemented endpoint count, declared unimplemented capabilities. |
| `GET /api/v1/meta/enums` | Canonical enum catalogue; the machine-readable form of section 2. |
| `GET /api/v1/me` | The caller's own organization membership. |
| `GET /api/v1/me/roles` | The caller's own non-revoked role grants with their scope. |
| `GET /api/v1/me/audit` | Audit events attributed to the caller. |
| `POST /api/v1/demo/seed` | Load the deterministic synthetic dataset. Demo mode only. |
| `POST /api/v1/demo/reset` | Remove only the synthetic dataset. Demo mode only. |
| `POST /api/v1/demo/import/email` | Present but answers `501`: no email integration exists. |

`/api/v1/me` deliberately returns no permission list. Permissions are enforced
server-side; publishing them to a client would invite a client to rely on them,
which is the trust boundary this design refuses.

### 5.2 Definitions written, routes deferred

The request and response models for the following exist in `app/schemas` and are
exercised by tests, but the routes are not wired up. They are the next vertical
slice, not abandoned work.

| Route | Blocked on |
|---|---|
| `POST /api/v1/expenses` | Workflow implementation. `CreateExpenseRequest` is defined. |
| `GET /api/v1/expenses` | Workflow, plus review-queue scoping. |
| `GET /api/v1/expenses/{expense_id}` | Workflow. |
| `PATCH /api/v1/expenses/{expense_id}` | Workflow and field-provenance writes. |
| `POST /api/v1/expenses/{expense_id}/submit` | Workflow and idempotency wiring. |
| `POST /api/v1/expenses/{expense_id}/decisions` | Approval workflow, which depends on the real policy. |
| `GET /api/v1/expenses/{expense_id}/audit` | Workflow. |
| `POST /api/v1/expenses/{expense_id}/receipts` | The upload route, plus a configured storage backend. |
| `GET /api/v1/receipts/{receipt_id}` | Upload route. |
| `GET /api/v1/receipts/{receipt_id}/content` | Upload route. |
| `POST /api/v1/receipts/{receipt_id}/reextract` | An extraction provider. |
| `GET /api/v1/policy/versions/current` | An approved policy document. |
| `GET /api/v1/policy/rules` | An approved policy document. |
| `GET /api/v1/policy/rules/{rule_id}` | An approved policy document. |
| `POST /api/v1/policy/check` | An approved policy document. |
| `GET /api/v1/findings` | Rule evaluation producing findings. |
| `GET /api/v1/findings/{finding_id}` | Rule evaluation. |
| `POST /api/v1/findings/{finding_id}/resolve` | Rule evaluation. |
| `GET /api/v1/duplicates` | Candidate persistence. |
| `POST /api/v1/duplicates/{candidate_id}/confirm` | Candidate persistence. |
| `POST /api/v1/duplicates/{candidate_id}/dismiss` | Candidate persistence. |
| `GET /api/v1/analytics/overview` | Claims data. |
| `GET /api/v1/analytics/spend` | Claims data. |
| `GET /api/v1/audit` | Org-scoped audit reads and the reviewer permission model. |
| `GET /api/v1/audit/export` | As above, plus CSV formula-injection mitigation. |
| `GET /api/v1/users` | Organization administration. |
| `GET /api/v1/trips` | Trip workflow. |
| `POST /api/v1/trips` | Trip workflow. |

### 5.3 Behavioural rules already fixed by the schema

These are decided now because they shape the migration, even though the routes come
later:

- `POST /api/v1/expenses` carries no `source` or `reviewed` field. Provenance is
  assigned by the server from the caller's role.
- `PATCH` accepts plain scalar values, never provenance. A client that could send
  `source: "reviewer_correction"` would be granting itself reviewer provenance.
- Extracting or re-extracting never overwrites a reviewer-corrected value.
- Re-running evaluation for the same claim version, policy version and scope cannot
  create a second finding: a unique index on that tuple makes it impossible rather
  than merely unlikely.
- A rejected claim requires a human-entered reason. The database refuses the row.

---

## 6. Authentication and authorization baseline

Production authentication is **not implemented**. `SupabaseAuthProvider.resolve_identity`
raises `NotImplementedYet` rather than accepting an unverified token. This is
deliberate: a permissive stub is the single most likely way for an authentication gap
to reach a deployed environment unnoticed.

- Demo mode uses `X-Demo-Actor-Id`. It is active only when `DEMO_MODE=true` and
  `APP_ENV` is not `production`/`staging`. Configuration validation refuses that
  combination at startup, so a demo deployment is impossible rather than merely
  discouraged.
- The demo header identifies a *user*, never a role. Roles, permissions and scope are
  loaded from the database on every request.
- A client-supplied role, employee id, department, grade, allowance or approval limit
  is ignored, not validated and trusted.
- `X-Demo-Organization-Id` is honoured only when the caller genuinely holds an active
  membership in that organization; otherwise the request is refused with `FORBIDDEN`.
  Silently answering from a different organization is exactly what a cross-tenant
  leak looks like.
- Permission checks are the coarse gate. Resource-level scope is enforced separately
  and both must pass.
- Status codes distinguish the two failure modes: no valid identity is `401`; a valid
  identity without an active membership or without the required authority is `403`.
  A terminated membership is therefore `403`, not `401` - we still know who this is,
  they simply may not act.

The full role/permission matrix is in `docs/authorization-matrix.md`. The intended
production design, including the JWT validation steps that must be implemented before
this is deployed, is in `docs/authentication-security.md`.

---

## 7. Re-evaluation, history and idempotency

- Re-evaluate affected claims after submission, correction, a relevant status change,
  a policy-version change, an allowance-assignment change or a duplicate resolution.
- Evaluation is idempotent for the same (claim version, policy version, context
  fingerprint). A retry cannot multiply findings or audit events.
- The context fingerprint hashes the resolved scope dimensions together with the
  contributing claim ids and versions. An absent dimension is recorded as an explicit
  value rather than omitted, so "no trip" is distinct from "not consulted".
- Superseded findings are retained and linked, never deleted.
- An audit event and the state change it describes share one transaction. If the
  mutation fails, the event is rolled back with it.
- `audit_events` is append-only at the database level: a trigger refuses `UPDATE` and
  `DELETE`. This is application/database-level append-only behaviour. It is **not**
  cryptographic immutability, and it must not be described as such.
- `audit_events` deliberately carries **no foreign keys**. A cascading referential
  action on a parent row would make PostgreSQL issue an `UPDATE` or `DELETE` against
  an append-only table, which the trigger then refuses - so deleting an organization
  failed because it tried to null out an audit column. An audit record must also
  survive the deletion of the entity it refers to. The reference columns are indexed
  UUIDs instead of constrained ones.
- No materialized aggregate table exists. Aggregates are computed by query over the
  included claims, which avoids the nullable-dimension double-counting hazard
  entirely. `trip_id` and the organizational dimensions are nullable, so any future
  grouping must handle an absent dimension explicitly rather than relying on a naive
  `GROUP BY`.

---

## 8. Contract-test checklist

Enforced today in `backend/tests/`:

- [x] Every implemented route appears in this document (contract test).
- [x] Documented enums match the service's enum catalogue.
- [x] Every documented error code exists in the implementation.
- [x] Money serialises as a decimal string and refuses a JSON number.
- [x] `RecommendedAction` is documented as its own enum.
- [x] Every contract route is either implemented or declared unimplemented.
- [x] Unauthenticated access to private routes is refused.
- [x] Demo routes are absent when demo mode is off (404).
- [x] Cross-organization access is refused.
- [x] An employee cannot read a colleague's claim.
- [x] A manager can read a direct report's claim and cannot read an unrelated one.
- [x] `audit_events` refuses `UPDATE` and `DELETE`.
- [x] Deleting a parent row does not attempt to rewrite audit history.
- [x] An unsourced allowance limit is refused by the database.
- [x] An active policy rule without a verified clause and validator is refused.
- [x] Migration applies and downgrades cleanly.

Outstanding, awaiting the corresponding implementation:

- [ ] Draft -> receipt upload -> extraction -> correction -> submit -> evaluation.
- [ ] Reviewer decision changes status and audit history atomically.
- [ ] Stale versions and idempotency retries behave predictably end to end.
- [ ] Policy preview and final submission use the same evaluator and version.
- [ ] Aggregate findings show contributors and recalculate when the basis changes.
- [ ] Duplicate candidates can be confirmed and dismissed with reasons.
- [ ] Receipt signed-URL expiry.
- [ ] CSV export formula-injection mitigation.
- [ ] Frontend types are generated from this contract rather than hand-written.


