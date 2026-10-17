# Proofline API Contract

**Contract version:** 1.0-draft  
**Base path:** /api/v1  
**Status:** Implementation baseline pending team sign-off. FastAPI's generated OpenAPI becomes the machine-readable source of truth and must remain aligned with this document.

## 1. Core invariants

1. One shared API serves the employee app and finance dashboard.
2. Only the backend performs authoritative policy evaluation and workflow state transitions.
3. Both clients use the same canonical DTOs, enums, error envelope and pagination conventions.
4. Money is persisted using NUMERIC/Decimal. JSON money values are decimal strings.
5. Dates use ISO YYYY-MM-DD; timestamps use ISO 8601 UTC; currencies use ISO 4217 codes.
6. State-changing operations are authorized, validated, concurrency-aware and audited transactionally.
7. Missing/ambiguous evidence returns UNKNOWN. A possible duplicate is not a confirmed duplicate.
8. Receipt content is private; do not return permanent public object-storage URLs.
9. Extraction is evidence, not policy authority.
10. Do not implement business rules or thresholds before mapping them to a verified policy clause.

## 2. Canonical enums

- ExpenseStatus: draft, submitted, needs_info, in_review, approved, rejected, withdrawn. Implement withdrawn only if required.
- RuleResult: PASS, FAIL, UNKNOWN.
- FindingSeverity: info, warning, blocking. Severity describes impact/routing, not guilt or fraud.
- FindingStatus: open, acknowledged, resolved, dismissed.
- DuplicateStatus: open, confirmed, dismissed.
- ExpenseChannel: android, web, bulk, email_simulated. email_simulated is demo-only, not a real email integration.
- ReviewAction: approve, reject, request_correction, escalate.
- FieldSource: receipt_extraction, employee_input, reviewer_correction, imported_data, computed.

All enums are validated by the backend. Clients must not invent local alternatives.

## 3. Canonical DTOs

### Field evidence

~~~json
{
  "value": "Example value or null",
  "source": "receipt_extraction",
  "reviewed": false,
  "confidence": 0.91,
  "evidence": {
    "receipt_id": "rcpt_example",
    "page": 1,
    "region": [0.1, 0.2, 0.5, 0.1]
  },
  "uncertainty_reason": null
}
~~~

Value may be null when missing/unreadable. Confidence is optional and is a provider/quality signal, not a calibrated probability. Evidence regions are optional only when supported; never fabricate coordinates. Employee-entered values must not masquerade as receipt evidence.

### Money

~~~json
{ "value": "1400.00", "currency": "INR" }
~~~

Use decimal strings in JSON and Decimal/NUMERIC in calculations/storage. Preserve original transaction amount/currency. If reporting-currency conversion is required by policy, store normalized amount, rate, rate date and source separately.

### Finding

~~~json
{
  "id": "fnd_example",
  "type": "aggregate_limit_exceeded",
  "rule_id": "POLICY-RULE-ID",
  "policy_version": "approved-version-id",
  "result": "FAIL",
  "severity": "blocking",
  "message": "Plain-language explanation.",
  "source_reference": {
    "document_id": "policy-document-id",
    "clause": "Section 2.3",
    "text_excerpt": "Verified clause excerpt."
  },
  "evidence": {
    "related_expense_ids": ["exp_a", "exp_b"],
    "receipt_ids": ["rcpt_a", "rcpt_b"],
    "inputs": {"observed_total": "4200.00", "limit": "3500.00", "currency": "INR"}
  },
  "calculation": "1400.00 + 1400.00 + 1400.00 = 4200.00; applicable limit = 3500.00",
  "expected": "Within the verified policy limit",
  "observed": "4200.00 INR across the evaluated scope",
  "recommended_action": "review",
  "status": "open",
  "created_at": "2026-10-17T12:00:00Z"
}
~~~

Numeric examples and clause references above are illustrative only. Every implemented finding must use verified policy evidence. Aggregate findings include the exact evaluated scope and contributing expense IDs where known.

### Expense response

~~~json
{
  "id": "exp_example",
  "version": 1,
  "employee": {"id": "usr_example", "display_name": "Demo Employee"},
  "trip_id": null,
  "channel": "android",
  "merchant": {
    "value": "Example Cafe",
    "source": "receipt_extraction",
    "reviewed": false,
    "confidence": 0.94,
    "evidence": {"receipt_id": "rcpt_example", "page": 1},
    "uncertainty_reason": null
  },
  "expense_date": {
    "value": "2026-10-14",
    "source": "receipt_extraction",
    "reviewed": true,
    "confidence": 0.91,
    "evidence": {"receipt_id": "rcpt_example", "page": 1},
    "uncertainty_reason": null
  },
  "amount": {"value": "1400.00", "currency": "INR"},
  "amount_reporting": null,
  "category": "meal",
  "business_purpose": "Client meeting",
  "client_name": null,
  "attendee_count": 2,
  "status": "needs_info",
  "receipts": [
    {
      "id": "rcpt_example",
      "content_url": "/api/v1/receipts/rcpt_example/content",
      "extraction_status": "success",
      "uploaded_at": "2026-10-17T12:00:00Z"
    }
  ],
  "line_items": [],
  "findings": [],
  "created_at": "2026-10-17T12:00:00Z",
  "updated_at": "2026-10-17T12:00:00Z"
}
~~~

Keep this response shape consistent across clients. Optional fields must be documented as nullable or omitted consistently in OpenAPI. Do not expose storage keys, provider secrets or unnecessary raw provider payloads.

### Duplicate candidate and review decision

A duplicate candidate includes its ID, both expense IDs, status, signal details (exact hash, perceptual similarity, normalized-field match), algorithm version, optional ranking score, creation time and reviewer resolution metadata. A score is not a calibrated probability unless evaluated.

A review decision includes ID, expense ID, actor, action, reason code, reason, optional notes, previous/new status, expense version, policy version and timestamp.

## 4. Common API behavior

### Request metadata

- Base path is always /api/v1.
- X-Request-ID is optional from the client; the server creates one if absent and returns it.
- Idempotency-Key is required for create/submit and encouraged for decision mutations.
- Use expected_version on corrections and decisions to reject stale writes.
- JSON is used unless an endpoint explicitly accepts multipart upload or CSV.

### Error envelope

~~~json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed.",
    "details": [],
    "request_id": "req_example"
  }
}
~~~

Recommended codes: VALIDATION_ERROR, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, CONFLICT, STALE_VERSION, IDEMPOTENCY_CONFLICT, POLICY_CONTEXT_UNKNOWN, EXTRACTION_FAILED, RATE_LIMITED, INTERNAL_ERROR. Never send stack traces or secrets to clients.

### Pagination

~~~json
{
  "items": [],
  "page": {"limit": 50, "next_cursor": null, "total": 0}
}
~~~

All list endpoints document accepted filters and sort order. The total may be omitted only if that choice is consistent and documented.

## 5. Endpoints

### System
- GET /api/v1/health — service status, no secrets.
- GET /api/v1/openapi.json — generated OpenAPI document.

### Users and trips
- GET /api/v1/users — reviewer/admin or demo-scoped list.
- GET /api/v1/trips — trips accessible to current user; reviewer access is permission-scoped.
- POST /api/v1/trips — create a trip if trip creation is in scope.

### Expenses
- POST /api/v1/expenses — create a draft from JSON metadata; returns the canonical Expense.
- POST /api/v1/expenses/{expense_id}/receipts — multipart upload; validate file, store privately, create receipt record and start extraction.
- GET /api/v1/expenses — paginated list; supported filters may include status, employee, date range, category, city/trip and channel.
- GET /api/v1/expenses/{expense_id} — canonical details and current findings.
- PATCH /api/v1/expenses/{expense_id} — correct allowed fields; requires expected_version, records provenance and re-evaluates relevant findings/context.
- POST /api/v1/expenses/{expense_id}/submit — submit a draft, validate and evaluate, record event, return updated expense; idempotent with same key.
- POST /api/v1/expenses/{expense_id}/decisions — reviewer action.
- GET /api/v1/expenses/{expense_id}/audit — authorized claim history.

Decision request:

~~~json
{
  "action": "request_correction",
  "reason_code": "MISSING_REQUIRED_CONTEXT",
  "reason": "Please provide the field required by the applicable policy.",
  "notes": null,
  "expected_version": 3
}
~~~

Reject requires a reason. Correction requests must state what is missing. Only authorized reviewers can decide. Approval with unresolved blocking findings is disallowed unless an explicitly authorized policy/workflow override exists and a reason is mandatory. A successful mutation and audit event are atomic.

### Receipts and extraction
- GET /api/v1/receipts/{receipt_id} — authorized metadata and extraction status.
- GET /api/v1/receipts/{receipt_id}/content — authorized stream or time-limited signed URL.
- POST /api/v1/receipts/{receipt_id}/reextract — re-run extraction with recorded provider/model version; never silently overwrite employee/reviewer-corrected values.

### Policy
- GET /api/v1/policy/versions/current — approved version metadata.
- GET /api/v1/policy/rules — active rules and source references.
- GET /api/v1/policy/rules/{rule_id} — one rule.
- POST /api/v1/policy/check — no-write advisory evaluation using the same evaluator. Missing database-only context returns UNKNOWN where applicable; response includes findings and advisory=true.

### Findings
- GET /api/v1/findings — paginated filters for result, severity, status, type, employee and date.
- GET /api/v1/findings/{finding_id} — finding and permitted evidence/related expense references.
- POST /api/v1/findings/{finding_id}/resolve — resolve/dismiss with actor and reason; preserve prior history.

### Duplicate candidates
- GET /api/v1/duplicates — paginated candidates with signal details.
- POST /api/v1/duplicates/{candidate_id}/confirm — confirm with reason and audit event.
- POST /api/v1/duplicates/{candidate_id}/dismiss — dismiss with reason and audit event.

Confirmation triggers the approved workflow and relevant re-evaluation; it must not automatically label an employee fraudulent.

### Analytics and audit
- GET /api/v1/analytics/overview — counts/spend with reporting period and aggregation basis.
- GET /api/v1/analytics/spend — authorized grouping by supported date/city/category/employee dimensions.
- GET /api/v1/audit — paginated, filterable audit events.
- GET /api/v1/audit/export — authorized CSV export with spreadsheet formula-injection mitigation.

### Demo-only utilities

Only enabled when DEMO_MODE=true and never enabled in production:
- POST /api/v1/demo/seed — load a deterministic synthetic fixture set.
- POST /api/v1/demo/reset — reset only demo-created records.
- POST /api/v1/demo/import/email — simulate an email-channel submission; not a real integration.

Return 404 or 403 for these routes when demo mode is disabled and require a privileged demo actor when enabled.

## 6. Authorization baseline

Production must authenticate private endpoints and enforce employee/organization scope server-side. UI role switchers are never a security boundary. Demo mode must show a banner and must not be deployable as production configuration.

- Employee: create/read/correct own claims, submit and see employee-safe status/messages.
- Reviewer: read permitted claims, review findings/duplicates, take allowed decisions.
- Admin: manage approved policy versions and demo fixtures; access audit/export only as permitted.

## 7. Re-evaluation, history and idempotency

Re-evaluate applicable claims after submission, correction, relevant status changes, policy-version changes or duplicate resolution. Preserve old findings as resolved/superseded history and create version-linked results. Make evaluation idempotent for the same expense version, relevant-context version and policy version. A retry must not multiply findings or audit events.

Aggregate findings contain the exact evaluated scope and contributor IDs. Changes must trigger re-evaluation of affected claims and be audit-visible.

## 8. Contract-test checklist

- [ ] FastAPI OpenAPI matches this document; clients are generated or contract-tested.
- [ ] Both clients use identical enums and canonical response shapes.
- [ ] Draft → receipt upload → extraction → correction → submit → evaluation works.
- [ ] Reviewer decision changes status and audit history atomically.
- [ ] Stale versions and idempotency retries behave predictably.
- [ ] Policy preview and final submission use the same evaluator/version.
- [ ] Aggregate findings show contributors and recalculate when the relevant basis changes.
- [ ] Duplicate candidates contain signals and can be confirmed/dismissed with reasons.
- [ ] Employee cannot read another employee's receipt or mutate their claim.
- [ ] Demo routes are disabled outside explicit demo mode.
