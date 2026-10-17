# Proofline — Product, Architecture, API Contract & Delivery Plan

> **Purpose:** This is the shared source of truth for the Proofline team and coding agents (including Hermes). Read this document before implementing or changing a cross-cutting feature. The backend contract and deterministic policy engine are authoritative; Android and web clients must consume them rather than reimplement business rules.

## 0. Project status and decision rules

- **Product:** Proofline — evidence-first expense intelligence.
- **Problem:** The Receipt Graveyard — turn messy receipts and a layered expense policy into accurate, explainable, reviewable reimbursement decisions, including duplicates and month-wide patterns.
- **Repository:** https://github.com/AnuAnsh17/Team_Rocket_HackForge_2026
- **Primary experience:** Finance review dashboard. **Secondary experience:** employee Android app.
- **Time constraint:** No fixed 20-hour deadline is assumed in this plan. Optimize for a complete, reliable, polished product and demo; still deliver in vertical slices so integration risk stays controlled.
- **Policy source:** The actual policy document and supplied receipt dataset are authoritative. Any numeric caps, time windows, approval thresholds, currency conversion rules or eligibility rules in examples below are illustrative only until verified against that source.
- **Model choice:** Select an available model after testing its API, schema support, latency, price, data terms and current availability. Do not hard-code a stale model name. Keep the extraction provider replaceable.
- **No unsupported claims:** Do not claim fraud detection, calibrated confidence, production readiness, legal compliance, or accuracy percentages without validation evidence.
- **Scope was expanded during scaffolding (2026-10-17).** The product is now three client experiences - an employee Android app, an employee web portal and an internal HR/Finance/Admin console - sharing one backend, with a full authentication and authorization model, an employee hierarchy, allowance profiles and scoped policy assignments. Section 17 records these requirements; `docs/architecture-decisions.md` records the decisions taken to satisfy them.

### Non-negotiable engineering rules

1. One canonical backend, one canonical API contract, one policy evaluator, one finding model and one audit history.
2. Clients do not calculate authoritative policy decisions. They display the result returned by the backend.
3. LLMs can extract, classify or assist with mapping policy text; deterministic code evaluates approved policy rules.
4. Missing/ambiguous evidence produces `UNKNOWN`, not a silent pass and not an automatic accusation of misconduct.
5. A duplicate candidate is not a confirmed duplicate. A policy exception is not inherently fraud.
6. Policy rules must cite a verified source clause and policy version. Do not invent policy thresholds to make a demo more dramatic.
7. Every review action is authorized on the server and recorded in an append-only application audit history.
8. Preserve original receipt files and extraction history; corrections create traceable versions rather than erasing evidence.
9. Secrets, provider keys, service-role database keys and private receipts must never be committed or exposed in client bundles.
10. The app, dashboard, seeded data, API docs and tests must all conform to this document. If a change is needed, update the contract first and coordinate all owners.

---

## 1. Product thesis and users

**Thesis:** Finance does not need another receipt scanner. It needs an auditor that connects each claim to the receipt evidence, the applicable policy clause and the rest of the employee's expense history—and explains each finding so a human can verify and resolve it.

### Primary users

- **Employee:** captures or uploads a receipt, reviews extracted values, adds business context, submits a claim, corrects missing information and follows its status.
- **Finance reviewer:** triages exceptions, checks source evidence, compares likely duplicates, reviews calculations, requests corrections and records decisions.
- **Finance/admin operator:** manages the approved policy version, reviews audit history, imports a dataset and monitors aggregate spending. During a prototype demo, identity may be simulated, but the UI must clearly identify the demo environment.

### Product outcomes

- Less manual transcription and repetitive review.
- Fewer missed duplicates and context-dependent policy breaches.
- Faster resolution of incomplete claims.
- Reproducible, evidence-linked decisions and a clear audit history.
- A measured, honest understanding of extraction and rule-evaluation performance.

The product must not optimize for rejecting more expenses. It should minimize unnecessary manual effort while surfacing genuine exceptions and preserving fair human review.

## 2. Product experience

### 2.1 Employee Android app

Recommended stack: **React Native + Expo + TypeScript**. Keep UI and API logic typed. Use camera/gallery or a supported document-scanning flow; test on a physical Android device. A responsive web/PWA employee flow may be used as a fallback or alternate entry path, but it must use the same API and rules.

Screens:

1. **Home:** submitted this month, pending, needs information, recent claims and a prominent scan/upload action. Totals must be derived from API data.
2. **Capture/import:** camera or gallery, preview, rotate/crop where practical, file type/size validation and clear upload progress.
3. **Review extraction:** editable merchant, transaction date, currency, total, category, purpose and policy-required context. Mark uncertain fields; do not present model confidence as a calibrated probability.
4. **Pre-flight policy guidance:** call the backend preview endpoint. It is advisory; aggregate state and reviewer decisions can change after submission.
5. **Submit:** create the claim once, prevent accidental duplicate submissions with an idempotency key, show a stable claim ID.
6. **Claims/status:** show status and plain-language explanation, not internal-only rule identifiers as the sole explanation.
7. **Correction flow:** show the specific missing/conflicting information requested by the reviewer; submit a correction as a new version and trigger re-evaluation.

Employee-facing copy must distinguish “needs information”, “policy issue”, “possible duplicate” and “under review”. Avoid accusatory wording.

### 2.2 Finance web dashboard

Recommended stack: **Next.js (App Router) + TypeScript + Tailwind CSS**. Use a consistent design system, loading/error/empty states, responsive layouts, accessible contrast and realistic seeded data. The dashboard is the main demonstration surface.

Pages:

1. **Overview:** submitted claims, awaiting review, open findings by severity, duplicate candidates, spend against a real configured budget only if supplied, prioritized review queue and recent audit activity. Every KPI must come from actual backend data, not hardcoded numbers.
2. **Expense review workbench (showpiece):** three panes—original receipt, extracted/corrected fields with evidence, and findings with rule clause, expected/observed values, calculation, contributing receipts, policy version and recommended action. Actions: approve, reject with reason, request correction, escalate, confirm/dismiss duplicate candidate where relevant.
3. **Exceptions and duplicates:** filters for missing/uncertain fields, arithmetic mismatch, individual rule findings, aggregate violations and duplicate candidates. Side-by-side receipt comparison should expose the evidence behind a match.
4. **Policy registry:** display the approved policy version, effective date and rule clauses used by the engine. An editable policy-authoring product is out of initial scope; policy updates require review, tests and a version change.
5. **Audit history:** actor, action, timestamp, affected entity, before/after values, policy version and correlation/request ID. CSV export is a useful feature if the core flow is stable.
6. **Analytics:** only add charts that answer finance questions and are backed by actual data. Do not let charts displace review-workbench quality.

### 2.3 Product “wow” moments

Build these as true end-to-end features, not scripted animations:

- **“Every receipt passed individually; the day did not.”** When the actual policy has a cumulative limit, a new qualifying claim causes a deterministic aggregate finding. The reviewer sees the exact set of contributing claims, the sum, limit, excess and source clause. Use actual policy conditions; if this policy does not have such a rule, choose the strongest equivalent interaction the policy supports.
- **Cross-channel duplicate candidate.** The same transaction arrives through two paths (one may be a demo-simulated email import) with a changed crop/rotation/compression. The system shows matched signals and both images. Reviewer confirmation or dismissal is logged. Never auto-reject based only on a similarity score.
- **“Show me why.”** Clicking a finding reveals the input evidence, deterministic calculation, rule/source clause, policy version and previous actions. Missing or unreliable evidence is visibly marked `UNKNOWN`.

A further product direction, after the core works, is **pre-flight expense guidance** to help employees understand the relevant limit and required information before submission. Never promise reimbursement based on a pre-flight check.

---

## 3. Recommended architecture

### 3.1 Technology choices

| Layer | Default | Responsibility |
|---|---|---|
| Android | React Native + Expo + TypeScript | Receipt capture, editable fields, submit/status/correction |
| Web | Next.js + TypeScript + Tailwind CSS | Finance review and admin interfaces |
| API/backend | Python + FastAPI + Pydantic | Canonical API, authorization, workflow, extraction orchestration, policy evaluation |
| Database | PostgreSQL (Supabase-managed Postgres is acceptable) | Claims, policy versions, findings, duplicate candidates, audit records |
| Object storage | Private Supabase Storage bucket or equivalent | Original receipt images and derived crops |
| Extraction | Provider adapter around a currently available multimodal/receipt extraction model; optional local OCR adapter | Receipt field extraction only, never the authority for policy decisions |
| Tests | pytest for backend; TypeScript lint/type checks and client tests | Unit, contract, integration, regression and evaluation tests |
| Deployment | One backend service, managed database/storage, web deployment and Android test build | Stable demo environments with environment-based configuration |

Use a provider adapter (`ReceiptExtractor` interface) so models can be changed without changing the policy engine or clients. A vision model can be the initial practical extractor; benchmark it on the real receipt set. OCR-specific models such as the team's earlier IndicOCR/PaddleOCR-VL experiments are candidates only after testing on this dataset. Provider/model availability, latency, price and privacy terms must be verified at implementation time.

### 3.2 Logical architecture

```text
Android Employee App                 Next.js Finance Dashboard
         |                                      |
         +-------------- HTTPS / JSON ----------+
                            |
                    FastAPI API Layer
                            |
             Authentication / authorization
                            |
       +--------------------+---------------------+
       |                    |                     |
 Expense & Receipt     Policy Service       Review / Decision
 Workflow Service      + Evaluator           Service
       |                    |                     |
       +------------- Expense Context Engine -----+
                            |
       +--------------------+---------------------+
       |                    |                     |
 Extraction Adapter   PostgreSQL          Private Object Storage
       |               (canonical data)    (receipt evidence)
 Vision/OCR provider
                            |
                    Append-only Audit Events
```

### 3.3 Backend module boundaries

Suggested monorepo structure (adapt only if the repo already has a sound structure; do not relocate files without checking):

```text
/
  README.md
  PROOFLINE_BUILD_PLAN.md
  docs/
    api-contract.md
    policy-assumptions.md
    architecture-decisions.md
    demo-runbook.md
    evaluation.md
  backend/
    app/main.py
    app/api/routes/
    app/core/config.py
    app/core/security.py
    app/schemas/                 # Pydantic request/response models
    app/models/                  # persistence models
    app/services/                # expense, receipt, review, policy
    app/extraction/              # provider-neutral interface and adapters
    app/policy/                  # rule registry, evaluator, rule implementations
    app/context/                 # aggregate/re-evaluation logic
    app/duplicates/              # exact, perceptual and field matching
    app/audit/                   # append-only event writer and readers
    migrations/
    tests/unit/
    tests/integration/
    scripts/evaluate_receipts.py
  apps/
    mobile/
    dashboard/
  packages/
    api-client/                  # generated or hand-typed shared client
    contract/                    # canonical OpenAPI/JSON schema artifacts if needed
  data/
    samples/                      # only rights-cleared/synthetic fixtures; no secrets
    manifests/
  .env.example
```

Do not maintain separate copied types in both clients. Generate a TypeScript API client from FastAPI's OpenAPI schema where practical, or create a checked-in shared schema with contract tests. API changes are contract changes and must be coordinated.

---

## 4. Canonical domain model

Use UUIDs for public IDs, UTC timestamps for events, ISO 8601 dates/timestamps, `Decimal`/PostgreSQL `NUMERIC` for money, and ISO 4217 currency codes. JSON amounts are numbers with documented precision; never use floating-point arithmetic for authoritative money calculations. Keep transaction currency/amount separate from normalized reporting amount and preserve the applied exchange-rate source/time when conversion is required.

### Core entities

- **User:** employee or reviewer identity, role, display name, organization/department attributes needed for policy evaluation. Do not put secrets in this entity.
- **Trip:** employee, date window, destination and business purpose; use only when supplied or entered, and do not infer a trip from home city.
- **Expense:** one reimbursement claim, stable ID, employee, channel, transaction date, merchant, original total/currency, category/purpose/context, current workflow status, version and timestamps.
- **Receipt:** private object-storage key, MIME type, file hash, optional perceptual hash, extraction run/version, raw extracted text where allowed and field-level evidence.
- **Line item:** description, amount/currency, tax/discount signals where available, eligibility decision and reason. Unknown eligibility is allowed; don't infer an exclusion just from a keyword without policy and adequate evidence.
- **Policy version and rule:** source document identity/hash, approved version, effective period, exact clause reference, evaluator type, validated parameters and review state.
- **Finding:** result (`PASS`, `FAIL`, `UNKNOWN`), finding type, severity, rule/version reference, evidence, calculation, expected/observed values, related expenses, status and resolution metadata.
- **Duplicate candidate:** expense pair, independent similarity signals, algorithm version, candidate status (`open`, `confirmed`, `dismissed`) and reviewer resolution.
- **Review decision:** action, actor, reason, notes, timestamp, prior/new expense version and applicable policy version.
- **Audit event:** append-only application event with entity reference, actor/system identity, action, timestamp, before/after snapshot or safe diff, policy version and correlation ID.
- **Aggregate view:** prefer querying or materializing policy-defined totals from eligible records. If materialized, make rebuild/reconciliation possible and ensure null dimensions do not cause duplicate aggregate rows.

### Workflow status enum

Canonical expense status values:

- `draft`
- `submitted`
- `needs_info`
- `in_review`
- `approved`
- `rejected`
- `withdrawn` (only if withdrawal is part of the implemented workflow)

Do not use expense workflow status to represent every finding. A claim can have multiple findings. Duplicate candidate state and finding state are separate from the claim status.

### Finding result and severity

- Result: `PASS | FAIL | UNKNOWN`.
- Severity: `info | warning | blocking`—severity describes impact/workflow; it does not prove fraud.
- Finding lifecycle: `open | acknowledged | resolved | dismissed`.
- Duplicate lifecycle: `open | confirmed | dismissed`.
- Review action: `approve | reject | request_correction | escalate`.

Validate each enum in the backend. Use stable machine-readable codes; provide separate employee/reviewer display messages.

---

## 5. Canonical API contract

**The FastAPI OpenAPI document is the canonical machine-readable API contract.** Keep this section and the generated OpenAPI schema in sync. Every endpoint uses a versioned `/api/v1` prefix. Standard JSON responses use stable field names, documented nullability, ISO date formats, decimal money semantics, pagination and error shapes.

### 5.1 Conventions

- Base path: `/api/v1`.
- JSON request/response unless the endpoint explicitly accepts multipart upload or CSV.
- Use `Authorization: Bearer <token>` for real auth. During demo-only mode, a clearly labelled seeded-user identity may be used behind the backend boundary; do not accept arbitrary role claims from the client in a way that grants production permissions.
- Include `X-Request-ID`/correlation ID on requests and responses. Use `Idempotency-Key` for claim submission and decision mutations where retries could create duplicate effects.
- Dates: `YYYY-MM-DD`; timestamps: UTC ISO 8601; currency: ISO 4217; money: JSON decimal representation, persisted with `NUMERIC`.
- List endpoints support consistent pagination (`limit`, `cursor` or `offset`) and filters. Do not return private receipt URLs to unauthorized users.
- Errors use one envelope, for example `{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [...], "request_id": "..." } }`.
- State-changing operations are transactionally persisted. A successful decision must not update the status while failing to append the audit event.

### 5.2 Endpoint inventory

#### Health and contract

- `GET /api/v1/health` — service health, no secrets.
- `GET /api/v1/openapi.json` — generated schema (framework may expose equivalent route).

#### Users and trips

- `GET /api/v1/users` — demo/admin scoped list.
- `GET /api/v1/trips` — trips accessible to current user, filterable by date/destination.
- `POST /api/v1/trips` — create trip if trip creation is in scope.

#### Expense claims

- `POST /api/v1/expenses` — create a draft from JSON metadata. Upload receipt images separately through `POST /api/v1/expenses/{expense_id}/receipts`. Both clients must use this flow.
- `GET /api/v1/expenses` — list with filters: status, employee, date range, category, city/trip and channel; permissions enforced server-side.
- `GET /api/v1/expenses/{expense_id}` — canonical details including safe extraction results and current open findings.
- `PATCH /api/v1/expenses/{expense_id}` — employee/reviewer correction of allowed fields; increment version, record the correction, and re-evaluate dependent findings/aggregates.
- `POST /api/v1/expenses/{expense_id}/submit` — submit a draft when draft/finalize semantics are needed; if not used, document the single-step flow.
- `POST /api/v1/expenses/{expense_id}/decisions` — reviewer action with required reason for rejection/correction/escalation as appropriate.
- `GET /api/v1/expenses/{expense_id}/audit` — history authorized for the caller.

#### Receipts and extraction

<!-- Upload is expense-scoped; see docs/api-contract.md decision log entry 1. -->
- `GET /api/v1/receipts/{receipt_id}` — receipt metadata and extraction status, not a public object-store path.
- `GET /api/v1/receipts/{receipt_id}/content` — authorized streaming or short-lived signed URL.
- `POST /api/v1/receipts/{receipt_id}/reextract` — authorized re-extraction with a recorded extractor version and no deletion of prior run history.

#### Policy and preview

- `GET /api/v1/policy/versions/current` — current approved policy version.
- `GET /api/v1/policy/rules` — rules active for a given date/context.
- `GET /api/v1/policy/rules/{rule_id}` — verified clause reference and rule metadata.
- `POST /api/v1/policy/check` — advisory pre-flight check; no claim write. Input contains relevant expense fields and context. Output uses the same finding schema and clearly marks unresolved aggregate/context inputs.

#### Findings and duplicates

- `GET /api/v1/findings` — filter by status, result, severity, type, employee and date.
- `GET /api/v1/findings/{finding_id}` — finding plus evidence references, calculations, and related expense IDs.
- `POST /api/v1/findings/{finding_id}/resolve` — reviewer resolution with a reason; append audit event.
- `GET /api/v1/duplicates` — duplicate candidate list and matched signals.
- `POST /api/v1/duplicates/{candidate_id}/confirm` — record confirmed duplicate with actor/reason.
- `POST /api/v1/duplicates/{candidate_id}/dismiss` — record dismissal with actor/reason.

#### Analytics and audit

- `GET /api/v1/analytics/overview` — KPI counts and values with period and aggregation basis.
- `GET /api/v1/analytics/spend` — sums by category/city/employee/date when allowed by policy/data.
- `GET /api/v1/audit` — filterable audit events.
- `GET /api/v1/audit/export` — CSV export for authorized reviewers/admins; escape spreadsheet formula payloads.

#### Demo utilities (non-production only)

- `POST /api/v1/demo/seed` — reset/load an approved synthetic demo dataset only when demo mode is explicitly enabled.
- `POST /api/v1/demo/reset` — clear seeded demo data only; inaccessible in production.
- `POST /api/v1/demo/import/email` — simulate email-channel arrival; never present it as a real email integration.

Endpoint names and canonical DTOs are defined in `docs/api-contract.md`. The team must sign off before parallel client implementation. Generate OpenAPI from FastAPI and add contract checks; keep both aligned. Do not casually rename endpoints after integration begins.

### 5.3 Canonical expense response example

The following is an illustrative contract example, not a real policy result. All clients must use the same fields:

```json
{
  "id": "exp_01JEXAMPLE",
  "version": 2,
  "employee": { "id": "usr_01JEXAMPLE", "display_name": "Demo Employee" },
  "channel": "android",
  "trip_id": null,
  "merchant": { "value": "Example Cafe", "source": "receipt_extraction", "reviewed": false },
  "expense_date": { "value": "2026-10-14", "source": "receipt_extraction", "reviewed": true },
  "amount": { "value": "1400.00", "currency": "INR", "source": "receipt_extraction",
              "reviewed": true },
  "category": "meal",
  "business_purpose": "Client meeting",
  "client_name": null,
  "attendee_count": 2,
  "status": "needs_info",
  "receipts": [
    { "id": "rcpt_01JEXAMPLE", "content_url": "/api/v1/receipts/rcpt_01JEXAMPLE/content", "extraction_status": "success" }
  ],
  "findings": [
    {
      "id": "fnd_01JEXAMPLE",
      "type": "required_field_missing",
      "rule_id": "POLICY-CLIENT-MEAL",
      "policy_version": "approved-version-id",
      "result": "UNKNOWN",
      "severity": "blocking",
      "message": "A client name is required for this expense type.",
      "evidence": { "field": "client_name", "observed": null },
      "calculation": null,
      "recommended_action": "request_correction",
      "status": "open"
    }
  ],
  "created_at": "2026-10-17T12:00:00Z",
  "updated_at": "2026-10-17T12:05:00Z"
}
```

Rules:
- Use stable fields across all clients; avoid ad hoc fields for one screen.
- A field's provenance should be represented consistently (receipt extraction, employee input, reviewer correction, imported system data, computed value).
- A field can have a value and still be uncertain; carry extraction/evidence metadata separately from the business value.
- Do not treat employee-entered data as receipt evidence.
- Use a canonical finding schema for both per-expense and aggregate findings. An aggregate finding must contain the related claim IDs and the evaluated scope.

### 5.4 Decision request example

```json
{
  "action": "request_correction",
  "reason_code": "MISSING_REQUIRED_CONTEXT",
  "reason": "Please provide the client name required by the applicable policy.",
  "notes": "Required for this claim type."
}
```

Backend invariants:
- Validate actor permission and allowed transition on the server.
- Reject stale writes when `expected_version` does not match the current expense version (optimistic concurrency).
- A correction or decision is atomic with its audit event and required re-evaluation jobs/records.
- Approving a claim with unresolved blocking findings must require an explicit, permission-checked override with a reason, if policy and workflow permit overrides at all.
- A rejected claim requires a human-entered reason.
- Re-running extraction must not silently overwrite reviewer-corrected values; preserve extraction runs and value provenance.

---

## 6. Policy engine — deterministic, versioned, testable

### 6.1 Source of truth

Use the actual company policy document. Store its version, effective date, source-file hash and clause/section/page references. Every implemented rule must state whether it is directly supported by the source, derived through an approved interpretation, or awaiting clarification. Keep unresolved interpretations in `docs/policy-assumptions.md` and visible to the team.

Do not let an LLM decide whether to reimburse a claim. An LLM may assist in drafting candidate rules from text, but an authorized human must validate the rule and its tests before it becomes active.

### 6.2 Tri-state rule evaluation

Each rule returns exactly one of:

- `PASS`: enough reliable information exists and the rule is satisfied.
- `FAIL`: enough reliable information exists and the rule is breached.
- `UNKNOWN`: required fields, policy context or reliable evidence are missing/ambiguous.

`UNKNOWN` must never silently pass. Route it to the correct path: employee correction, reviewer assessment, or non-blocking informational notice depending on the rule and impact. Do not force every unknown into the same workflow status if a reviewer can resolve it without the employee.

### 6.3 Rule interface

Every rule implementation should accept a typed claim, relevant policy version, policy context, and a snapshot of relevant claims, and return a typed finding. Conceptually:

```python
class PolicyRule(Protocol):
    rule_id: str
    policy_version: str
    source_reference: str

    def evaluate(self, expense, context) -> Finding:
        """Deterministically return PASS, FAIL or UNKNOWN with evidence."""
```

A finding should contain:

- stable `rule_id` and `policy_version`;
- result and severity;
- source clause reference/text excerpt;
- inputs used and their provenance;
- explicit calculation for numeric decisions;
- expected condition and observed values;
- related expense/receipt IDs for aggregate/duplicate findings;
- reviewer-safe explanation and recommended next action.

### 6.4 Evaluation order

1. Validate schema, file metadata and claim invariants.
2. Establish field provenance and whether critical values are usable.
3. Run deterministic arithmetic/date/currency sanity checks where applicable.
4. Run individual-expense policy rules.
5. Resolve relevant policy scope (business trip vs office, destination, date, employee/context) from trusted data; missing context yields `UNKNOWN`.
6. Normalize currency if and only if the policy requires it, using a documented rate source/date and preserving original values.
7. Run aggregate/context rules and duplicate candidate generation.
8. Persist findings and the policy/evaluator version; update workflow state from a centralized transition function.
9. Record audit events and enqueue any dependent re-evaluations.

### 6.5 Re-evaluation and history

Re-evaluate affected claims after a relevant receipt upload, employee correction, reviewer correction, claim status transition that affects aggregate basis, policy-version change, or duplicate resolution. Never delete prior findings to hide history. Mark superseded/resolved findings and create version-linked results so the reviewer can inspect what changed and why.

Policy evaluation should be idempotent for the same input versions and policy version. A retry must not create duplicate findings or duplicate audit events unintentionally.

### 6.6 Monetary and aggregate rules

- Use decimal arithmetic, explicit rounding rules and currency codes.
- Separate individual caps from aggregate caps; do not accidentally apply both as one rule.
- Derive grouping dimensions and inclusion basis from actual policy semantics, not convenience.
- Explicitly document timezone/date boundary, business-trip location, city mapping, claim status inclusion, refunds/credits and partial eligibility treatment where relevant.
- If totals are materialized, provide reconciliation/rebuild logic and transaction-safe update behavior. For an initial version, a correct query is preferable to premature aggregate-table complexity.
- A new expense may change an aggregate finding on other claims. Record that change as a new evaluation/finding event rather than silently rewriting the past.

---

## 7. Receipt extraction and evidence pipeline

### 7.1 Extraction interface

Implement a provider-neutral interface. The provider may use a vision model or conventional OCR/layout models; selection is based on a small real-data benchmark and current API availability. Keep prompts, schema, model name/version and request IDs in server-side configuration/logs, without logging secrets or unnecessary sensitive data.

Return structured fields with value, source/provenance, optional confidence/quality signals, optional page/region evidence where supported, and an explicit `unreadable`/`missing` representation. Do not fabricate a confidence value if the provider doesn't supply a meaningful one.

Potential fields, if visible/applicable:

- merchant;
- transaction date/time;
- subtotal, tax, tip/service charge, discount and total;
- original currency;
- item descriptions, quantities and item amounts;
- receipt/invoice number;
- payment reference only if it is needed and safe to collect.

### 7.2 Extraction rules

- Store original bytes, MIME type, hash and file size after validation.
- Never evaluate policy solely on raw unverified model output; run deterministic schema and consistency checks.
- Distinguish subtotal from final total. Do not assume line items sum exactly to the total when tax/tip/discounts may explain a difference.
- Detect unknown currency rather than assuming INR from a symbol-free number.
- Do not infer a client name, attendee count, purpose or trip solely from a receipt unless the evidence explicitly supports it; collect business context from the employee or approved system.
- OCR corrections are user/reviewer edits with provenance and versions; retain the original extraction.
- Show the receipt crop or source image next to fields where feasible, but don't claim region accuracy until validated.
- Use a safe live extraction path and a clearly labelled verified-cache fallback for the demo. Never claim a cached response was live inference.
- Limit provider payloads and retention to what the chosen service and organization's privacy rules allow. Use environment secrets; never bundle keys into mobile/web clients.

### 7.3 Evaluation

Create a human-labelled receipt set containing clean, faded, rotated, cropped, handwritten/partially handwritten, mixed-currency, itemized and incomplete cases if those exist in the supplied material. Track field-level exact/normalized accuracy, missing-field detection, correction rate and latency. Evaluate on the actual dataset; electricity-bill performance from previous experiments is useful background but not proof of expense-receipt performance.

---

## 8. Duplicate detection

Generate **candidates**, never automatic fraud findings, using independent signals:

1. Exact cryptographic file hash for byte-identical files.
2. Perceptual/image similarity after orientation normalization and optional resizing. Tune and test against positive and negative pairs; no universal Hamming-distance cutoff is assumed.
3. Normalized merchant, transaction date/time (with a documented tolerance), amount, currency and receipt/invoice identifiers where available.
4. Cross-channel metadata and employee context as secondary signals—not sole proof.

Each candidate records algorithm/version, individual signals, related receipt/expense IDs, score/decision basis, status, timestamps and reviewer resolution. Similarity scores must be described as ranking signals unless calibrated against a representative labelled set. Two expenses with the same total/date are not necessarily duplicates.

Test duplicate detection using actual known positive pairs and hard negative pairs such as two different meals with identical totals. Report precision and recall with the sample size. A reviewer can confirm or dismiss; both actions require a reason and audit event.

---

## 9. Data, security and privacy

### Prototype minimum

- Use synthetic/authorized receipts for fixtures and demo seeding.
- Keep receipt object storage private. Use backend authorization and short-lived signed URLs or authorized streaming.
- Keep API keys and database service-role credentials in server-side environment variables only.
- Never expose stack traces, SQL errors, keys or receipt payloads in user-facing errors.
- Enforce file type, size and basic content validation; use safe filenames/object keys.
- Separate demo utilities from production mode and disable seed/reset endpoints in production.
- Use role checks on every sensitive backend endpoint even if a demo user switcher is used in the UI.
- Use least-privilege access and organization/employee scoping for claims and receipts.
- Sanitize CSV exports against spreadsheet formula injection.
- Avoid logging receipt images, full OCR text, payment identifiers or personal information unless necessary.

### Production path

Before a real pilot: real authentication, server-side role/tenant isolation, database policies as appropriate, encryption in transit/at rest, secrets management, backup/restore testing, retention/deletion policy, incident handling, access logs, dependency scanning, rate limits, upload malware scanning where appropriate, and legal/privacy review for the jurisdictions and vendors involved. Do not claim compliance merely because these items are planned.

---

## 10. Wow-case/demo data design

Create an explicit manifest of fixtures and expected outcomes. Seed roughly 30–40 claims only if that volume adds realistic context; a smaller, correctly labelled set is better than a large unverified set. Use synthetic employee names and fictional companies/receipts unless real data usage is explicitly authorized.

Required cases:

1. Clean receipt with reliable required fields.
2. Faded or rotated receipt with one uncertain critical field, sent through correction path.
3. Required business-context field missing.
4. Arithmetic mismatch where the receipt genuinely supports the comparison.
5. Individually acceptable claims whose relevant aggregate exceeds a real policy limit (only if the policy contains such a rule).
6. The same receipt/transaction sent through two channels, one image altered; detector creates a candidate and reviewer resolves it.
7. A hard negative duplicate case: same amount/date but a distinct transaction.
8. A clear policy exception.
9. A rule that returns `UNKNOWN` because necessary evidence/context is absent.
10. Correction or status change that causes affected findings to be re-evaluated and preserves history.

For each fixture include: fixture ID, input receipt/image path, claim metadata, expected extracted fields with tolerances, relevant policy version, expected rule results, expected duplicate relationships, and expected state transitions. The demo should reset to deterministic state.

### Demo narrative (3–5 minutes)

1. Explain that reading the receipt is only the first step; policy context and month-wide relations matter.
2. Capture/upload a real receipt from the Android app, show extraction, correct an uncertain field, and submit.
3. On the dashboard, open a contextual aggregate finding with its contributing claims and transparent calculation.
4. Show a cross-channel duplicate candidate with side-by-side image and matched signals; resolve it as a reviewer.
5. Open a finding's evidence trace and show source clause/version, inputs, calculation and audit history.
6. Show the employee-facing correction/status update.
7. Finish with measured evaluation results, dataset size and honest limitations.

Have a recorded fallback and verified cached extraction for approved demo fixtures. Label fallback use honestly in code/runbook. The product must still have a real live end-to-end path; do not rely on a completely pre-scripted demo.

---

## 11. Testing strategy and definition of done

### Backend tests

- Unit tests for every rule: PASS, FAIL and UNKNOWN cases, including boundary conditions.
- Decimal and currency rounding tests.
- Policy-scope tests: office vs business trip, city/destination, timezone/date boundary, missing context.
- Aggregate tests: inclusion basis, new claim, correction, approval/rejection where relevant, duplicate resolution and re-evaluation of other claims.
- Duplicate detector tests: positive pairs, hard negatives, rotation/crop/recompression and algorithm version.
- State-transition and permission tests for every review action.
- Audit atomicity tests: a successful state-changing action must write an audit event; failed mutations must not create partial state.
- Idempotency and optimistic concurrency tests.
- File upload, unauthorized receipt access and signed-URL expiry tests.

### Contract/integration tests

- Check the generated OpenAPI document and canonical client types.
- Mobile upload → backend storage → dashboard list/detail works.
- Real extraction → employee correction → deterministic evaluation works.
- Dashboard action → audit history → mobile status update works.
- Error, timeout, retry and duplicate-submit paths have understandable behavior.
- Demo seed/reset is deterministic and disabled outside demo mode.

### Product evaluation

Report at minimum:

- Field-level extraction accuracy by critical field and total sample size.
- Policy result correctness on a labelled set of claim/rule pairs.
- Duplicate candidate precision and recall on labelled positive and negative pairs.
- Percentage requiring correction or human review.
- Time to resolve representative exceptions, preferably compared with a human-only baseline if one is available.

Do not set artificial accuracy claims. Define acceptance targets after inspecting the dataset and then report actual results, including failures and limitations.

### Definition of done

- A real receipt from a physical Android device or clearly identified employee web fallback completes capture → extraction → correction → submit → evaluate → finance review → decision/correction → status update → audit.
- A policy-supported aggregate case works with exact scope and transparent calculation.
- A cross-channel duplicate candidate is generated from tested signals and can be confirmed/dismissed by a reviewer.
- Every displayed finding exposes evidence, rule/version and next action appropriate to its type.
- Frontend types agree with the OpenAPI schema; no independent client-side policy implementation exists.
- Relevant automated tests pass and evaluation metrics are reproducible.
- Private receipt access and demo-only endpoints are configured safely.
- Dashboard and app have polished loading/error/empty states and no broken primary navigation.
- The demo resets deterministically, has a recorded fallback and has been rehearsed end to end.

---

## 12. Team ownership and agent coordination

Replace placeholder names with confirmed team members; ownership is a proposal, not an assertion about identity.

### Anurag — Backend, extraction and policy

Owns FastAPI, persistence/migrations, canonical Pydantic models, extraction adapter, rule evaluator, context/duplicate engine, audit persistence, API docs and backend tests. Must not change a public response shape without coordinating the contract.

### Hrishabh — Employee Android app and integration

Owns React Native/Expo app, upload/correction/status UX, employee-safe messages, typed API-client integration, physical-device testing and cross-client end-to-end tests. Coordinates deployment setup if agreed by the team.

### Akash — Finance dashboard

Owns Next.js dashboard, typed API integration, review workbench, evidence panel, exceptions/duplicate UI, audit timeline and analytics that are genuinely used. Must not duplicate policy calculations or derive authoritative claim status locally.

### Shared responsibilities

- All read this plan and `docs/api-contract.md` before coding.
- One person is the contract maintainer; backend owner proposes contract changes, all affected clients sign off.
- Use one repo and a branch/PR workflow. Avoid unrelated commits on shared branches while parallel work is underway.
- Every agent task must name files/modules, inputs/outputs, acceptance criteria and tests.
- Keep commits small and coherent; do not let multiple agents simultaneously rewrite the same files.
- Before large edits, inspect the repository and existing conventions; modify the smallest relevant surface.
- Do not install new libraries or change framework versions without checking compatibility and documenting why.
- When requirements are ambiguous, record an explicit question or assumption in `docs/policy-assumptions.md`; do not silently make up a business rule.

### Integration gates

1. **Gate 0 — Architecture/contract:** domain models, status/result enums, API endpoints, schema and policy source documented.
2. **Gate 1 — Mock vertical slice:** one mock receipt flows through mobile/client → API → database → dashboard → decision → status.
3. **Gate 2 — Real extraction:** same path with live extraction and a field correction.
4. **Gate 3 — Policy engine:** rule tests pass and findings render with evidence.
5. **Gate 4 — Context:** aggregate and duplicate wow cases behave correctly, including a hard negative.
6. **Gate 5 — Resilience/security:** retries, permissions, private image access, errors and idempotency tested.
7. **Gate 6 — Polish/freeze:** no new features until end-to-end acceptance checks pass.
8. **Gate 7 — Demo rehearsal:** real flow rehearsed; dataset reset and fallback verified.

---

## 13. Hermes / coding-agent operating instructions

Use this document as persistent project context. Before implementing any task, an agent must:

1. Read `PROOFLINE_BUILD_PLAN.md`, `docs/api-contract.md` and relevant architecture/policy notes.
2. Inspect current repository state and existing code before editing.
3. Identify the contract surface and downstream clients affected by the change.
4. State assumptions and acceptance tests in its task plan (in the PR/issue or team notes).
5. Implement the smallest coherent increment and add/update tests.
6. Run relevant tests, linting, type checks and OpenAPI/schema checks; report exact commands/results and failures.
7. Update documentation when behavior, contracts, environment variables or deployment steps change.
8. Never fabricate successful test output, model results, metrics or demo behavior.
9. Never store API keys, receipt data or private user data in source control.
10. Never change policy thresholds or policy meanings unless the approved policy source and team have validated the change.

### Suggested task prompt template

```text
Project: Proofline (read PROOFLINE_BUILD_PLAN.md and docs/api-contract.md first).
Task:
Scope/files:
Contract impact:
Acceptance criteria:
Tests to add/run:
Out of scope:
Report back with changed files, exact test commands/results, assumptions, and remaining risks.
```

### Suggested initial agent order

1. **Contract/architecture agent:** review and get team sign-off on the existing `docs/api-contract.md`, `docs/policy-assumptions.md`, canonical enums/schemas and API endpoint decisions; then implement FastAPI routes/models and check generated OpenAPI against the contract. Do not implement multiple screens first.
2. **Backend agent:** scaffold health, database connection/migrations, core claim/receipt models, mock extraction and the end-to-end claim/decision path.
3. **Dashboard and mobile agents:** implement against the frozen OpenAPI schema and typed client. Use mock fixtures until the first backend slice is reachable; do not invent alternative response shapes.
4. **Policy agent:** translate only verified policy clauses to deterministic rules with tests; make unresolved clauses explicit.
5. **Integration/test agent:** run contract tests, end-to-end workflow, known aggregate/duplicate fixtures and privacy checks.
6. **Polish agent:** refine visual system, loading and error states, evidence trace, demo seed/reset, accessibility and presentation only after core behavior is correct.

---

## 14. Deployment and environment contract

Maintain `.env.example` with placeholders only, for example:

```dotenv
APP_ENV=development
DEMO_MODE=true
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=REPLACE_ME
SUPABASE_SERVICE_ROLE_KEY=SERVER_ONLY_REPLACE_ME
RECEIPT_STORAGE_BUCKET=receipts-private
EXTRACTION_PROVIDER=REPLACE_ME
EXTRACTION_MODEL=REPLACE_WITH_VERIFIED_MODEL
EXTRACTION_API_KEY=SERVER_ONLY_REPLACE_ME
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Actual configuration can change based on the selected provider and deployment host. No real values belong in this file or Git history. The mobile app should contain only public configuration that is safe to ship; service-role keys and AI credentials must remain on the server.

Document local setup, migrations, seed/reset procedure, test commands, start commands, deployed URLs and recovery instructions in `README.md` and `docs/demo-runbook.md`. Check health endpoints and storage permissions before rehearsal.

---

## 15. Post-hackathon validation path

1. Interview finance users about current receipt intake, review effort, policies, duplicate handling and accounting workflows.
2. Run the product in **shadow mode** beside their existing workflow; recommendations do not control payment or rejection.
3. Compare system findings with human outcomes; track false positives, missed issues, correction rate and review time.
4. Improve policy coverage and extraction based on real failure cases; do not optimize for rejection rate.
5. Only after evidence of value, add production authentication/tenant isolation, stronger operational monitoring, retention controls and integrations (CSV first, then the accounting systems used by pilot customers).
6. Keep a human accountable for disputed, uncertain, high-impact and policy-override decisions.

---

## 16. Decisions that must be resolved before implementation

These questions are deliberately not filled with invented values:

- Where is the actual company policy document, and which version is authoritative?
- Which supplied receipts, metadata and expected outcomes are available, and what use is authorized?
- What is the required company timezone and date-boundary rule?
- Which expenses count toward each cap, and at which workflow states?
- What policy source/rate date is required for foreign-currency conversion, if any?
- Does an individual cap limit the reimbursable portion or require review/rejection of the whole claim?
- Which approval/override permissions does the problem statement require?
- Are external AI APIs permitted for provided receipt data, and what are the cost/privacy constraints?
- Does the hackathon require a native APK, or is a physical-device Expo app/PWA acceptable?
- Who are the final three owners, and who maintains the API contract?

Until answered, implement only the parts that do not depend on these assumptions and keep uncertain policy-dependent behavior explicit.

---

## 17. Scope expansion and scaffolding decisions (2026-10-17)

The product scope was expanded during the scaffolding phase. These are now **explicit
product requirements**, not optional direction. Implementation status is tracked in
`docs/problem-statement-coverage.md`; decisions and trade-offs are in
`docs/architecture-decisions.md`.

### 17.1 Three client experiences, one backend

| Client | Stack | Purpose |
|---|---|---|
| Employee Android app | React Native + Expo + TypeScript | Receipt capture, extraction review, submission, status, corrections |
| Employee web portal | Next.js + TypeScript + Tailwind | First-class employee experience: upload, correct, personal expense history, personal allowance overview |
| Internal HR/Finance/Admin console | Next.js + TypeScript + Tailwind | One console with role-specific navigation for HR review, manager approval, finance review, finance administration, organization administration and policy administration |

Rules that follow from this:

- The employee portal and the internal console are separate applications, so an
  authorization defect in one cannot expose the other and the employee bundle does not
  ship internal review code.
- The internal console is **one** application with role-specific routes, not three
  duplicated applications for HR, finance and administrators.
- All three consume the same generated API client. No client defines its own expense
  model.
- An employee may access only their own claims, receipts, status, allowance profile and
  history, except for explicitly authorized delegated access. Ownership is enforced by
  the backend, never by frontend filtering.

### 17.2 Authentication and authorization as core requirements

Not a later cosmetic feature. The architecture must include:

1. Identity verification through validated authentication tokens.
2. Server-side JWT signature, issuer, audience and expiry validation using the chosen
   provider's supported mechanism. **Supabase Auth is the initial choice.**
3. Server-controlled membership and authorization records; a client can never grant
   itself a role or privilege.
4. Organization/tenant scoping for every organization-owned record.
5. Resource-level access checks on expenses, receipts, findings, history, policy,
   uploads and mutations.
6. A user cannot reach another employee's data by changing a URL, UUID, parameter or
   payload.
7. Employee access limited to their own claims and permitted profile fields.
8. Managers reach direct reports only through explicitly authorized relationships.
9. HR and finance access scoped to the claims, fields, departments or queues they are
   authorized for.
10. Organization and policy administrators receive only their assigned capabilities.
11. Sensitive actions audited with actor, target, action, timestamp, reason and
    request/correlation id.
12. Role changes, deactivation, token revocation/expiry and membership loss considered
    in the security design.

A demo identity switcher is permitted **only** in explicitly enabled non-production demo
mode, must be impossible to use to gain another user's identity or administrative
permissions in production, and must fail closed when disabled. See
`docs/authentication-security.md` and `docs/authorization-matrix.md`.

### 17.3 Hierarchy, allowance profiles and policy assignment

Different employees may have different limits, privileges, required approvals and
allowances. The data model and architecture must support:

- Organizations / legal entities; users and organization memberships.
- Employee profile and employment status; manager/reporting relationships (historised).
- Department, cost centre, office/location and destination context.
- Grade, job level or employee band.
- Allowance/benefit profiles; policy documents and versions; policy rules.
- Policy assignments with scope, effective dates and approval state.
- Explicit, reviewed, time-bounded exceptions/overrides.
- Approval tasks and decisions.
- Audit history of policy-assignment changes.

Resolution dimensions: organization/legal-entity baseline; jurisdiction/office/location;
grade; department/cost centre; trip or expense context; explicit authorized exception.

**Do not assume that a higher job level means a higher allowance, and do not assume that
the most specific policy always wins.** The approved policy determines the semantics.
The design must make precedence, effective dates and exceptions explicit and
deterministic. If applicable rules conflict or required context is absent, resolution
must report an explicit unresolved/UNKNOWN outcome for review rather than inventing a
decision. See `docs/role-policy-hierarchy.md`.

### 17.4 Contract corrections agreed during scaffolding

Recorded in full, with reasons, in the decision log at the top of
`docs/api-contract.md`:

1. `POST /api/v1/expenses/{expense_id}/receipts` is the only receipt-upload route. The
   bare `POST /api/v1/receipts` is removed.
2. `RecommendedAction` (`none`, `review`, `request_correction`, `escalate`) is its own
   enum, distinct from `ReviewAction`.
3. One canonical money structure carrying `value`, `currency`, `source`, `reviewed`,
   optional `confidence`, optional `evidence` and `uncertainty_reason`.
4. Invalid `FieldSource` values in examples corrected to `receipt_extraction`.
5. Public identifiers are UUIDs.
6. Pagination is `limit` + opaque `next_cursor` + `total`.

### 17.5 What the scaffolding phase deliberately did not build

No OCR pipeline, no policy rules, no reimbursement thresholds, no claim or decision
routes, no live authentication. Any such gap must remain explicit in the code, the API
metadata (`GET /api/v1/meta`) and the coverage report - never implied to work.

---

## One-line team summary

**Proofline is an evidence-first expense auditor: one source-of-truth backend, a deterministic versioned policy engine, context-aware duplicate and aggregate checks, a mobile employee workflow, and a finance workbench where every finding can be traced to evidence and a human decision.**
