# Problem Statement Coverage

**Assessment date:** 2026-10-17 (updated after the scope-resolution follow-up)
**Branch assessed:** `chore/proofline-project-scaffold`
**Baseline commit:** `be26b35` (the docs-only repository as cloned)
**Requirement source:** [`docs/problem-statement.md`](./problem-statement.md)
**Assessor's role:** this is a self-assessment of the design and the scaffold by the
engineer who built it, not an independent evaluation.

> **Historical baseline.** Sections 1–8 describe the `chore/proofline-project-scaffold`
> snapshot named above. They are not a description of the current `backend` branch.
> The receipt-intelligence implementation status is recorded in section 9 below.

## 0. Requirement sources, and what is still missing

Every requirement below is traced to a quoted source. The wording lives in
[`docs/problem-statement.md`](./problem-statement.md), which exists so that this matrix
references a document in the repository rather than a file outside it.

| Source | What it is | Status |
|---|---|---|
| **A** | The original "Receipt Graveyard" hackathon problem statement | **NOT SUPPLIED.** `docs/problem-statement.md` section 2 is a deliberately empty slot. |
| **B** | This project's own problem statement, from `PROOFLINE_BUILD_PLAN.md` section 0 | Available. **Derived wording**, not the original. |
| **C** | The approved scoping decision listing the required coverage areas | Available, reproduced verbatim in `docs/problem-statement.md` section 3. |

**The traceability mapping.** Requirements **R1 to R16** in section 2 are the sixteen
required coverage areas of **source C**, section 3.5, in that document's own order, one
requirement for one bullet. The labels are therefore verbatim-derived from an approved
source, not invented here.

**What that does and does not prove.** It proves this matrix covers everything this
project was asked to build. It does **not** prove the request list is complete, because
source C is a derived requirements document. If the original statement contains a
requirement source C omits, this report would not notice its absence. That is precisely
the failure mode the empty slot in `docs/problem-statement.md` exists to prevent, and it
is why source A is still listed as an open action in section 7.

**Nothing here has been reconstructed.** No plausible-sounding version of source A has
been written, because a reconstruction would silently redefine what the project is judged
against and every coverage claim built on it would then be measured against the wrong
target.

## 1. Status vocabulary

| Status | Meaning |
|---|---|
| `DOCUMENTED` | Written down and decided. No code. |
| `SCAFFOLDED` | Schema, interface, module boundary or DTO exists. **Does not solve the problem.** |
| `IMPLEMENTED` | Working code that does the thing, reachable through a real path. |
| `TESTED` | Implemented **and** covered by passing tests that would fail if it broke. |
| `NOT ADDRESSED` | No design and no code. |

A schema column is not a capability. An interface with one stub implementation is not a
capability. Nothing below is marked `IMPLEMENTED` merely because a folder, table or type
annotation exists.

## 2. Traceability matrix

---

### R1 - Messy, faded, rotated, cropped, handwritten and incomplete receipts

- **Problem requires:** correct handling of the real quality distribution, including
  partially readable receipts, rather than clean machine-printed samples.
- **Proposed approach:** a provider-neutral `ReceiptExtractor` adapter; explicit
  `unreadable` representation per field; `UNKNOWN` whenever a critical value is
  unreliable; no fabrication of confidence.
- **Components:** `app/extraction/base.py`, `app/extraction/unavailable.py`,
  `expense_field_evidence.uncertainty_reason`, the usability rule
  `FieldSnapshot.usable`.
- **Status after the receipt OCR slice:** `TESTED` for runtime invocation and pipeline
  status handling on a synthetic image; no field extraction is implemented. The
  adapter protocol, unreadable representation and "do not fabricate" rule remain in
  place. A synthetic receipt is not evidence of real receipt accuracy.
- **Evidence needed to mark implemented:** a chosen provider, a labelled degraded-image
  set, per-field accuracy including the missing-field detection rate.
- **Risk:** high. This is the core capability and it does not exist. Accuracy on faded
  and handwritten receipts is unknown and may be poor.
- **Essential or optional:** essential.

---

### R2 - Correct extraction of merchant, dates, totals, currency and itemization

- **Problem requires:** reliable structured values for the fields a policy decision
  depends on.
- **Proposed approach:** typed `ExtractedField` per field with provenance; subtotal /
  tax / discount / total kept distinct; currency detected rather than assumed from a
  symbol-free number; line items captured separately.
- **Components:** `EXTRACTABLE_FIELDS`, `ExtractedLineItem`, `line_items`,
  field-evidence tables.
- **Status:** `SCAFFOLDED`. IndicOCR returns raw page Markdown/blocks, while no
  structured field has been extracted or persisted.
- **Evidence needed:** per-critical-field exact/normalised accuracy on the real set,
  with sample size.
- **Risk:** high. Also note the build plan's warning: previous IndicOCR/PaddleOCR-VL
  work on electricity bills is not evidence for expense receipts.
- **Essential or optional:** essential.

---

### R3 - Layered expense policies and interacting rule conditions

- **Problem requires:** multiple rules that interact - category, location, trip vs
  office, time, category caps interacting with aggregate limits.
- **Proposed approach:** a deterministic registry of typed rules; a documented nine-step
  evaluation order; each rule independently tri-state; policy versions with effective
  periods; resolution of which version governs.
- **Components:** `app/policy/base.py`, `registry.py`, `evaluator.py`, `resolution.py`,
  `policy_documents` / `policy_versions` / `policy_rules` / `policy_assignments`.
- **Status:** `SCAFFOLDED`. The engine, ordering, registry, resolution and versioning
  exist; **the registry contains zero rules**, because no policy document has been
  supplied. This is deliberate: an invented rule that approves or rejects real claims is
  worse than no rule.
- **Evidence needed:** the authoritative policy document with clause references, plus
  PASS/FAIL/UNKNOWN tests per clause including boundaries.
- **Risk:** high, and the largest single external dependency in the project. Without the
  policy there is no product, only an engine.
- **Essential or optional:** essential.

---

### R4 - Employee-specific allowances, hierarchy and approval requirements

- **Problem requires:** different employees governed by different limits and different
  required approvals; managers approving reports.
- **Proposed approach:** memberships carry grade/department/cost centre/office; a
  historised `reporting_relationships` table; `allowance_profiles` assignable through
  scoped `policy_assignments`; `approval_tasks` with a recorded `requirement_basis`.
- **Components:** `organization_memberships`, `reporting_relationships`,
  `role_assignments`, `allowance_profiles`, `policy_assignments`, `approval_tasks`,
  `app/policy/resolution.py`.
- **Status:** `SCAFFOLDED`. Entities, constraints and the resolver exist. **No grade
  levels, no allowances and no approval rules exist**, because they are organizational
  and policy data. Precedence is deliberately not assumed.
- **Scope-resolution sub-status (follow-up commit):** the half of this requirement that
  is *matching a claim to the assignments that apply to it* is now **implemented and
  tested for all ten supported dimensions** - `organization`, `office_location`,
  `department`, `cost_center`, `job_grade`, `trip`, `employee`, `legal_entity`,
  `jurisdiction` and `expense_category` - with a regression test per dimension and a test
  that fails if a dimension is ever added without being classified. Three of those
  dimensions (legal entity, jurisdiction, expense category) previously could never match
  at all, so an assignment scoped to them looked configured and did nothing.
  This does **not** raise R4's status: matching is not applying. With no allowance
  profile and no rule, nothing is still computed, and no limit reaches an employee.
- **Evidence needed:** the organization's grade structure and allowance policy, plus
  approval-stage rules.
- **Risk:** medium-high. The model supports the shape; the content is missing, and the
  precedence semantics are genuinely undecided.
- **Essential or optional:** essential for the employee-specific claims in the expanded
  requirements.

---

### R5 - Required business context such as client names and attendee counts

- **Problem requires:** certain categories need context that a receipt cannot supply
  (who the client was, how many attended), and a claim without it is incomplete.
- **Proposed approach:** explicit fields with provenance; a structural finding that
  reports `UNKNOWN` when the policy that would define the requirement has not been
  verified; employee-facing correction path.
- **Components:** `expenses.client_name`, `attendee_count`,
  `ExpenseFieldName.CLIENT_NAME`, the `required_business_context_present` structural
  check, `CreateExpenseRequest`/`UpdateExpenseRequest`.
- **Status:** `SCAFFOLDED`. Fields and the check exist; the check deliberately returns
  `UNKNOWN` rather than guessing which categories require what. The request DTOs exist;
  no route accepts them.
- **Evidence needed:** the policy clause listing required context per category.
- **Risk:** low technically; blocked on policy.
- **Essential or optional:** essential.

---

### R6 - Category caps and daily/cumulative limits

- **Problem requires:** per-category caps and period limits, correctly scoped.
- **Proposed approach:** `allowance_profile_items` with `period_type` and a nullable
  `limit_amount`; aggregate scope gathering with a period; explicit inclusion basis.
- **Components:** `allowance_profile_items`, `ALLOWANCE_PERIOD_TYPES`,
  `gather_related_expenses`, `DEFAULT_AGGREGATE_INCLUDED_STATUSES`,
  `policy_assignments`.
- **Status:** `SCAFFOLDED`. The schema can store a cap **only if it cites a source
  clause** (CHECK constraint), which is tested. No cap exists, no cap is evaluated.
- **Evidence needed:** the policy's actual caps, period definitions, and which claim
  states count.
- **Risk:** high. Three policy questions are unresolved: individual vs cumulative, what
  happens when exceeded, and which states count.
- **Essential or optional:** essential if the policy contains caps.

---

### R7 - Non-reimbursable items and partial eligibility

- **Problem requires:** some items on a receipt are not reimbursable, and an item may be
  partially eligible.
- **Proposed approach:** `LineItemEligibility` with `PARTIAL` and `UNKNOWN`; eligibility
  is a policy outcome, never inferred from a keyword; `ineligibility_reason` required
  when an item is marked ineligible (CHECK constraint).
- **Components:** `line_items.eligibility`, `ineligibility_reason`, `policy_rules`.
- **Status:** `SCAFFOLDED`. Enum and constraint exist and are tested. **No keyword
  blacklist and no eligibility rule exists**, because inferring an exclusion from a word
  without a policy clause is exactly the silent rule the design forbids.
- **Evidence needed:** policy clauses on alcohol, tips, taxes, service charges,
  discounts and mixed categories.
- **Risk:** medium-high. Mixed eligible/ineligible baskets are genuinely hard.
- **Essential or optional:** essential if the policy excludes categories.

---

### R8 - Arithmetic inconsistencies

- **Problem requires:** detect when the receipt's own numbers do not add up.
- **Proposed approach:** a deterministic arithmetic check comparing subtotal, tax,
  discount and total; `ARITHMETIC_MISMATCH` finding type; the build plan's warning not
  to assume line items sum to the total when tax/tip/discounts explain a difference.
- **Components:** `FindingType.ARITHMETIC_MISMATCH`, evaluator step 3.
- **Status:** `SCAFFOLDED`. The finding type and the declared evaluation step exist; the
  comparison **is not implemented**, because it needs extracted values that do not
  exist. The evaluator currently reports `UNKNOWN` with the reason "no amount is
  available to check".
- **Evidence needed:** extraction working, plus the policy's tolerance for rounding.
- **Risk:** low technically, but it is currently a placeholder and must not be described
  as working.
- **Essential or optional:** essential.

---

### R9 - Exact and image-variant duplicates, including cross-channel candidates

- **Problem requires:** find the same transaction submitted twice, including when the
  second image is rotated, cropped or recompressed, and including across channels.
- **Proposed approach:** independent named signals - exact SHA-256, perceptual
  similarity, normalised field match, channel context - assembled into a **candidate**
  with an algorithm version and a ranking score that is explicitly not a probability.
  A human confirms or dismisses, with a reason.
- **Components:** `app/duplicates/signals.py`, `duplicate_candidates`,
  `uq_duplicate_candidates_pair`, `DuplicateCandidateResponse`,
  `ResolveDuplicateRequest`.
- **Status:** `SCAFFOLDED`, and partially `TESTED` as pure logic. Exact-hash and
  normalised-field signals are implemented and tested, including the documented hard
  negative (two different meals with identical totals). **Perceptual similarity is
  explicitly not implemented** and returns no score rather than a fabricated one.
  Persistence, candidate generation from real data and the confirm/dismiss routes do
  not exist.
- **Evidence needed:** perceptual hashing over normalised images; a labelled set of
  positive and hard-negative pairs; precision and recall with sample size.
- **Risk:** high. The most visually impressive demo case is the least built. The
  cross-channel `email_simulated` route returns `501`.
- **Essential or optional:** essential.

---

### R10 - Suspicious patterns that warrant review without unsupported fraud claims

- **Problem requires:** surface things a human should look at, without accusing anyone.
- **Proposed approach:** findings carry `severity` (impact and routing) and never a
  guilt verdict; a duplicate is a candidate, never fraud; the UI copy distinguishes
  "needs information", "policy issue", "possible duplicate" and "under review".
- **Components:** `FindingSeverity`, `DuplicateStatus`, employee-facing
  `employee_message` separate from the reviewer `message`, warning text in
  `app/duplicates/signals.py` notes.
- **Status:** `DOCUMENTED` and enforced in wording; the model deliberately contains no
  fraud or risk-score entity at all. A unit test asserts no severity value implies fraud.
- **Evidence needed:** none to keep the current stance; this is a deliberate refusal of a
  capability, not a gap.
- **Risk:** low, and upside down: the risk is a future contributor adding a "fraud score".
- **Essential or optional:** the *refusal* is essential to the product's ethics.

---

### R11 - Month-long accumulation and re-evaluation as claims arrive or change

- **Problem requires:** an individual claim can be fine while the month is not; a later
  claim can change the verdict on an earlier one.
- **Proposed approach:** aggregate scope gathering over a period; a context fingerprint
  over the scope and contributing claim versions; re-evaluation planning with explicit
  triggers; superseded findings retained rather than rewritten.
- **Components:** `app/context/scope.py`, `app/context/reevaluation.py`,
  `scope_fingerprint`, `uq_findings_identity`.
- **Status:** `SCAFFOLDED`, with the pure logic `TESTED`. Fingerprint stability,
  absent-dimension handling and re-evaluation planning are unit-tested. **No aggregate
  finding can occur**, because it needs an active aggregate rule.
- **Evidence needed:** the policy's cumulative rule, its period definition and its
  inclusion basis.
- **Risk:** high for the demo narrative, since this is the build plan's headline "every
  receipt passed individually; the day did not" moment and it is not demonstrable.
- **Essential or optional:** essential.

---

### R12 - Multi-employee account security and role-based access

- **Problem requires:** one employee must not see or change another's data; HR, managers,
  finance and administrators must hold only their assigned capabilities.
- **Proposed approach:** verified identity -> database-loaded actor -> permission gate ->
  resource scope. Two independent gates. Explicit per-role permission sets with no
  "admin implies everything". Organization/tenant scoping on every owned record.
- **Components:** `app/core/security.py`, `app/core/permissions.py`,
  `app/services/actor_service.py`, `app/services/scope_service.py`,
  `role_assignments`, `reporting_relationships`.
- **Status:** `IMPLEMENTED` and `TESTED`. This is the only requirement area that reaches
  those levels. Covered by 20+ security tests including cross-employee read refusal with
  a positive control, cross-organization refusal, role-claim spoofing refusal, terminated
  membership refusal, and demo-mode absence. Production authentication is **not**
  implemented and refuses every request rather than accepting an unverified token.
- **Evidence needed for the authentication half:** a real identity provider integration
  and security testing. Authorization is done; authentication is stubbed.
- **Risk:** medium. The model is sound and tested; the identity provider is the gap, and
  it is a large one.
- **Essential or optional:** essential.

---

### R13 - Employee corrections and reviewer workflows

- **Problem requires:** a reviewer can request specific missing information; the employee
  can correct it; the claim is re-evaluated; status is visible to the employee.
- **Proposed approach:** `request_correction` decision with a mandatory reason; versioned
  claims with `expected_version`; correction creates a new field-evidence version rather
  than erasing the old one; `needs_info` status; re-evaluation on correction.
- **Components:** `review_decisions`, `UpdateExpenseRequest`, `DecisionRequest`,
  `expense_field_evidence`, `ck_review_decisions_rejection_requires_reason`.
- **Status:** `SCAFFOLDED`. The schema, DTOs and invariants exist and the "rejection
  requires a reason" constraint is tested. **No route implements a decision or a
  correction**, so the workflow cannot be exercised.
- **Evidence needed:** the routes, plus end-to-end tests of the correction loop.
- **Risk:** medium. Mostly mechanical once the claim routes exist.
- **Essential or optional:** essential.

---

### R14 - Explainable findings, policy provenance and audit history

- **Problem requires:** every finding traceable to evidence, a rule and a clause; every
  review action recorded.
- **Proposed approach:** findings carry the source clause, the inputs, the calculation,
  expected/observed values and the policy version; a `FAIL` cannot be constructed
  without evidence (model invariant); `audit_events` is append-only with a database
  trigger; field-level provenance per claim version.
- **Components:** `findings`, `source_reference`, `FindingDraft.__post_init__`,
  `audit_events` + `trg_audit_events_append_only`, `expense_field_evidence`.
- **Status:** `SCAFFOLDED`, with key invariants `TESTED`: the append-only trigger refuses
  UPDATE and DELETE, a `FAIL` without evidence raises, deleting a parent leaves audit
  rows intact, provenance cannot claim extraction without a receipt. **No finding is
  ever produced**, because no rule runs.
- **Evidence needed:** rule execution plus the reviewer UI that renders the trace.
- **Risk:** low-medium. The hardest part (the schema and the invariants) is done.
- **Essential or optional:** essential.

---

### R15 - Currency normalization where required

- **Problem requires:** compare amounts across currencies if the policy demands it.
- **Proposed approach:** original amount/currency preserved; a separate reporting amount
  with an explicit rate, rate date and rate source; conversion only when policy requires
  it; never a default rate.
- **Components:** `expenses.amount_reporting`, `reporting_rate`,
  `reporting_rate_date`, `reporting_rate_source`, `NonNegativeMoney`, `MoneyString`.
- **Status:** `DOCUMENTED` and `SCAFFOLDED`. Decimal handling is `TESTED` - money is
  `NUMERIC`, serialises as a string, and refuses a JSON number. **Conversion is not
  implemented**: no rate source exists and `amount_reporting` is always null.
- **Evidence needed:** the policy's conversion rule and an approved rate source.
- **Risk:** medium. The rate source is an unresolved policy question.
- **Essential or optional:** essential only if the policy requires conversion.

---

### R16 - Human review and accountable reimbursement decisions

- **Problem requires:** a human remains accountable; the product does not auto-reject.
- **Proposed approach:** every claim decision is a reviewer action with an actor, reason
  and timestamp; overrides require explicit authorization and a reason; approval with
  unresolved blocking findings is disallowed absent an authorized override.
- **Components:** `review_decisions`, `approval_tasks`, `ReviewAction`,
  `delegation_basis`, audit events.
- **Status:** `SCAFFOLDED`. The schema models it and constrains it; **no decision route
  exists**. Nothing in the system can currently approve or reject anything, which is at
  least not the wrong direction.
- **Evidence needed:** the decision routes, permission and transition tests.
- **Risk:** medium.
- **Essential or optional:** essential.

---

## 3. Scorecard

Sixteen requirement areas, counted **unweighted** and **once each**.

| Status reached | Count | Requirements |
|---|---|---|
| `TESTED` | 0 | none |
| `IMPLEMENTED` (not tested end to end) | 1 | R12, authorization half only (production authentication is stubbed) |
| `SCAFFOLDED` | 14 | R1, R2, R3, R4, R5, R6, R7, R8, R9, R11, R13, R14, R15, R16 |
| `DOCUMENTED` only | 1 | R10 |
| `NOT ADDRESSED` | 0 | none |
| **Total** | **16** | |

Zero areas reached `TESTED`. Fourteen reached `SCAFFOLDED`, which as section 1 states
means the schema, interface or DTO exists - **not** that the problem is solved. Only R12
has working code on a real path.

## 4. Method and meaning of any percentage

Any percentage here measures **the assessment, not the product.** There is exactly one
figure that describes what the software can do today.

**Verified functional completion: 1 / 16 = 6%.**

- **Denominator:** the 16 requirement areas in section 2. This is a count of *areas*, not
  a weighting by effort or by importance. Areas differ enormously in size - R2 (extraction
  accuracy) is far larger than R15 (currency normalisation) - so this number must not be
  read as "6% of the work is done".
- **Numerator:** areas where working code is reachable through a real path and covered by
  tests that would fail if the behaviour broke. That is R12, and only its authorization
  half; production authentication refuses every request rather than working.
- **Unchanged by the scope-resolution follow-up, deliberately.** That fix made the
  policy-assignment matcher correct and tested for all ten dimensions, which is real work
  and 77 new tests - but it does not let a single claim reach a reimbursement decision, so
  it does not move this numerator. Recording it as an increase would be exactly the
  inflation section 3's status definition forbids.
- **What it is not:** it is not an accuracy figure, not a benchmark, and not a comparison
  against any other implementation.

I deliberately do **not** report a "design coverage percentage". Every one of the sixteen
areas has a written design decision, so the figure would be 100% - which is technically
true and practically useless, and exactly the kind of number that flatters a scaffold. The
honest substitute is the count in section 3: fourteen areas scaffolded, one documented,
one implemented.

**What the scaffold actually delivers, stated without a percentage:** 28 domain tables
with real constraints; one applied, verified and reversible migration; a FastAPI service
that starts and serves health, metadata and three authenticated identity endpoints; a
tested authorization model covering horizontal and vertical escalation; 159 passing backend
tests; 23 passing frontend tests; a generated TypeScript contract with a drift guard that
was verified to fail; three client applications totalling 23 routes, every one a labelled
placeholder; CI that runs all of it without a single secret; and twelve documents.

It is not a working expense auditor. **No receipt has ever been processed by this
system.**

## 5. What the scaffold genuinely delivers

- **Structural guarantees that are hard to retrofit:** the CHECK constraints that make an
  unsourced allowance limit and an unvalidated active rule *unstorable*; the partial
  unique indexes that make duplicate findings and reversed duplicate pairs impossible;
  the trigger that makes audit history append-only; the separation of claim values from
  per-field provenance.
- **A tested authorization model** covering horizontal and vertical escalation, with
  refusals and their positive controls.
- **An honest contract** that a machine can check: a contract test fails the build if an
  endpoint is served without being documented, if an enum diverges, or if money becomes a
  JSON number.
- **A reversible migration** exercised by every test run.
- **Documentation that states what is missing**, including a machine-readable list at
  `GET /api/v1/meta`.

## 5a. What the scaffolding phase delivered, commit by commit

Recorded so the state of this assessment can be checked against the history rather than
taken on trust.

| Commit | Scope |
|---|---|
| `chore: add repository hygiene configuration` | `.gitignore`, `.gitattributes`, `.editorconfig`, `.dockerignore`, `.env.example` |
| `docs: reconcile Proofline architecture and API contracts` | Contract corrections, build plan section 17, 11 documents, README, AGENTS |
| `chore(backend): scaffold FastAPI application and schemas` | Config, errors, logging, middleware, enums, DTOs, security interfaces, routing, health, OpenAPI |
| `chore(database): add schema migrations and storage foundations` | 28 tables, constraints, 8 hand-written indexes, the initial migration, private storage |
| `chore(backend): add policy engine, extraction adapter and domain services` | Policy engine (zero rules), extraction protocol, context scope, duplicate signals, audit writer, services |
| `test(backend): add scaffold tests and deterministic fixtures` | 159 tests, dev scripts, fixture manifest |
| `chore(api-client): establish shared OpenAPI TypeScript client` | Workspace, generated contract, drift guard |
| `chore(dashboard): scaffold internal finance and admin console` | 11 routes, navigation, tokens, 9 tests |
| `chore(employee-portal): scaffold employee expense experience` | 7 routes, wording rules, 7 tests |
| `chore(mobile): scaffold Expo employee application` | 5 screens, theme vocabulary, 7 tests |
| `fix(policy): reconcile scope selectors with the documented dimensions` | Scope selector split, migration `0002_scope_selector`, 77 new tests, `docs/problem-statement.md` |

Two notes on what these commits do **not** mean:

1. Commits 3-5 of the backend are horizontal slices of one deployable service, so they are
   review units rather than independently bootable revisions. The service was validated as a
   whole at the tests commit.
2. No commit in this sequence processes a receipt, evaluates a rule or moves a claim through
   a workflow, because none of that exists yet.

## 6. What realistically depends on missing inputs

| Input | Blocks |
|---|---|
| The authoritative policy document | R3, R4, R5, R6, R7, R11, R15, R16 and every rule test |
| The receipt dataset and its usage rights | R1, R2, R8 and every extraction metric |
| A chosen extraction provider and API key | R1, R2, R8 |
| A labelled positive/negative duplicate set | R9 |
| The organization's grade structure and allowances | R4 |
| A Supabase project | production storage and authentication |
| Traffic/volume expectations | async vs sync revisited |

Eight of sixteen requirement areas cannot be finished without the policy document. That
single missing artefact is a bigger threat to this project than any engineering task
remaining.

## 7. Largest remaining risks

1. **The policy document does not exist in the repo.** Without it the product has no
   rules, and the engine is a well-built machine with nothing to run.
2. **No receipt has been processed.** Extraction quality on the real dataset is entirely
   unknown; it could be excellent or unusable.
3. **The two headline demo moments are the least built.** Both the cross-channel
   duplicate candidate and the month-wide aggregate finding depend on the two items
   above.
4. **Perceptual duplicate matching is unimplemented**, and it is the part that makes the
   duplicate story visually convincing.
5. **Production authentication is a stub.** Fine for a demo, fatal for anything real.
6. **Scope has grown faster than delivery.** The brief expanded from two clients to
   three, and added hierarchy, allowances, HR/manager/org administration and a full
   authorization model. The authorization model is done; the rest is schema.
7. **No independent review.** This document is a self-assessment.

## 8. Overall assessment

**Fit to the problem: strong in design, unproven in execution.**

The design attacks the right problem. It refuses the two shortcuts that would make a
demo look better and the product worse: inventing policy thresholds, and letting a
similarity score or a language model make a reimbursement decision. It puts the
constraints in the database rather than in a document, which is why an unsourced limit
genuinely cannot be stored. It separates "the receipt says" from "the employee says" at
the storage level. And it treats `UNKNOWN` as a first-class answer, which is the single
most important design decision in an auditing product.

**What differentiates it** is evidence discipline rather than model novelty: every
finding must cite a clause, carry its calculation and be attributable to a version; a
`FAIL` without evidence cannot be constructed; a duplicate is a candidate until a human
says otherwise; and the audit trail is append-only at the database level. Most expense
tools demo a confident answer. This one is built to show its work and to say "I cannot
tell" when it cannot.

**What would prevent it from solving the problem convincingly:**

- Not obtaining the policy document. This is the existential risk. Eight of sixteen
  requirement areas are blocked on it, and the demo's two best moments are among them.
- Not obtaining the receipt data, or obtaining it without permission to use an external
  model, leaving extraction as a protocol with no implementation.
- Spending remaining time on surfaces rather than on the extraction-to-finding path, which
  is the only path that demonstrates the product.
- Letting the expanded scope (three clients, hierarchy, allowances, six administrative
  areas) consume the time needed for the vertical slice that actually proves the thesis.

**The single highest-value next step** is not more scaffolding. It is: obtain the policy
document and the receipt set, and build one complete vertical slice - one receipt, one
verified rule, one finding with a clause and a calculation, visible on the dashboard and
traceable in the audit log. That slice is worth more than all three frontend shells.

## 9. Receipt-intelligence milestone status (2026-10-18)

The current `backend` branch extends the historical baseline with a real upload-to-job
path: employee-owned draft creation, one- or up-to-20-image private upload, signature and
size validation, SHA-256, persisted pending extraction runs, bounded in-process processing,
authorized receipt/status/content reads, explicit owner retry, and per-run normalized
structured results. OpenCode Go is the configurable structured provider; IndicOCR remains an
OCR-only option. The result is schema-versioned and field statuses preserve missing or
uncertain values. Decimal reconciliation is a backend extraction-review signal, not a
policy finding. Raw provider text and OCR Markdown remain unpersisted and absent from DTOs.

Offline tests verify provider request serialization, schema and response validation,
retry/error mapping, bounded worker concurrency, upload and batch persistence, private
content authorization, historical retry behavior, and extraction validation. The optional
live OpenCode Go upload-to-persistence test was **not run** in this milestone. No labeled
receipt set is available, so there is no measured receipt accuracy, latency or cost claim.
The worker is process-local, retries are explicit after restart to avoid automatic
re-submission and possible duplicate provider charges, production Supabase authentication
and hosted private storage are still absent,
and policy rule execution and reimbursement processing remain unavailable. Versioned
claim correction, submission, scoped human review decisions and authorized audit reads
are implemented as workflow records only; human approval is not a policy result.

The portal and console consume the claim list/detail and human review lifecycle. This
milestone does not make Proofline a complete expense auditor and does not change the
historical sixteen-area scorecard above.

## 9. Maintenance of this document

Update at each milestone with the same rigour. Specifically:

- Re-mark statuses only when evidence exists, not when code is written.
- Recompute section 3 and recompute the numerator and denominator in section 4 explicitly.
- Keep the distinction between design coverage and verified functional completion. If the
  two numbers ever converge, either the product is finished or the assessment has
  become dishonest.
- Reconcile section 2 against the verbatim problem statement once it is supplied.

