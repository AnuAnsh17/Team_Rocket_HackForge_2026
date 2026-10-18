# Proofline — Expense Compliance & Auditability

**Expense claims arrive as a receipt, a number and a story. Proofline turns them into evidence:
every field keeps its provenance, every policy outcome is explainable, and every human decision is
recorded — so a reviewer can defend the call and an auditor can retrace it.**

Reimbursement today runs on scattered receipts, unwritten policy and judgement calls nobody can
reconstruct later. Proofline puts one deterministic policy engine and one append-only audit history
behind a single API, and makes the hard questions answerable: *What was claimed? Who asserted it —
the employee, the receipt, or a reviewer? Which policy version governed it? Why did it pass, fail,
or come back **UNKNOWN**? Who decided, and when?*

> **What this is, precisely.** A working, tested backend and three clients with a real claim
> lifecycle, policy evaluation and audit trail. It is **not** a payment system, and receipt text
> extraction is **not** proven working — no extraction provider is enabled or benchmarked. The
> sections below state exactly which parts are verified and which are not.

| | Capability | Status |
|---|---|---|
| 💸 | Expense claim lifecycle — draft, submit, correct, escalate, approve, reject | ✅ Implemented and tested |
| 🧾 | Private receipt upload, batch upload, authorized content retrieval | ✅ Implemented and tested |
| 🔍 | Extraction runs persisted with per-field provenance | ⚠️ Plumbing complete; **no provider enabled or benchmarked** |
| ⚖️ | Deterministic policy engine with `PASS` / `FAIL` / **`UNKNOWN`** | ✅ Implemented; engine's own findings not yet persisted |
| 🛡️ | Supabase JWT verification (JWKS, issuer, audience, algorithm allow-list) | ✅ Implemented and tested; **not exercised against a live project** |
| 🔐 | Permission + organization-scope authorization on every route | ✅ Implemented and tested |
| 📊 | Analytics — overview, spend groups, two-dimensional spend matrix | ✅ Implemented and tested |
| 🧠 | Employee-facing advisory policy pre-flight (writes nothing) | ✅ Implemented and tested |
| 🗄️ | Append-only audit history (database trigger) | ✅ Implemented and tested |
| ♻️ | Idempotent mutations, optimistic concurrency | ✅ Implemented and tested |
| 🧬 | Duplicate candidates as **signals**, never fraud determinations | ✅ Model + ranking; no live caller yet |
| 🚫 | Payment or reimbursement execution | ❌ Does not exist anywhere in this codebase |

**Stack.** FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL 18 · Python 3.14 —
Next.js 16 (App Router) ×2 · React 19 · Expo / React Native · TypeScript 5.9 · Tailwind —
generated OpenAPI client (`openapi-typescript` + `openapi-fetch`) · Supabase Auth (JWKS) ·
Docker Compose · pytest · Vitest · Ruff · mypy.

## Why Proofline

Expense compliance fails in three places, and each one is an evidence problem:

1. **The claim is not traceable.** A total on a spreadsheet does not say whether it came from the
   receipt, from the employee's typing, or from a reviewer's correction. Proofline stores **per-field
   provenance**, so "who asserted this?" is a query, not an argument.
2. **The policy is not reproducible.** When the rule changes, nobody can reconstruct what governed a
   decision last quarter. Proofline resolves an explicit, versioned policy per claim, evaluates it
   deterministically, and reports `PASS`, `FAIL` or `UNKNOWN` — where `UNKNOWN` means *the evidence or
   the policy context is insufficient*, and never silently becomes a pass.
3. **The decision is not accountable.** A status change with no history is unauditable. Proofline
   appends an audit event in the same transaction as the decision it records, in a table that refuses
   `UPDATE` and `DELETE`.

It also keeps two things apart that are routinely conflated: a **possible duplicate** is a ranked
candidate for a human to confirm or dismiss — never a confirmed duplicate and never fraud; and a
**reviewer approving a claim** is a workflow decision — never a payment.

## What works today

**Fully implemented and tested**

- Claim lifecycle with real state transitions — `draft → submitted → in_review → approved/rejected`,
  including `needs_info` correction round trips that append new field evidence at a new claim version.
- Receipt upload (single and batch) with size limits and file-signature validation, private object
  storage, and receipt content served only through an authorization-checked endpoint — never a public URL.
- Deterministic policy engine: versioned policy resolution, category-applicable rules, tri-state results
  with expected/observed/calculation evidence, and an advisory pre-flight that **writes nothing**.
- Authorization: explicit permission checks plus organization scoping on every route — cross-tenant and
  cross-employee access refused, and hidden records answering exactly like missing ones.
- Audit trail: append-only by database trigger, with each decision and its audit event in one transaction.
- Idempotency keys on mutations and optimistic concurrency (`expected_version`) on state changes.
- Analytics projections: status, amount, completeness, department, location, category and monthly
  aggregates, spend groups across six dimensions, and a two-dimensional spend matrix.
- Supabase JWT verification as a pluggable provider (JWKS caching, issuer/audience validation,
  RS256/ES256 allow-list, clock leeway) alongside a demo header provider for local work.
- Internal console with a live dashboard and real Supabase sign-in; employee portal; Expo mobile app.

**Partial — real code, not yet proven end to end**

- **Receipt extraction.** Uploads persist an extraction *run*; the worker claims pending runs and reads
  stored bytes. `EXTRACTION_PROVIDER` defaults to `unavailable` and non-default providers fail closed,
  so **no text is proven to be extracted**. A benchmark dataset exists to evaluate accuracy; no accuracy
  claim is made here.
- **Persisted policy findings.** The engine returns findings; the write path that would persist them has
  no live caller in this revision. The advisory pre-flight is the only evaluation path wired to a route.
- **Duplicate-candidate generation.** Models, ranking and constraints exist; nothing calls the signal
  generator yet.
- **Client token wiring.** The console sends a Supabase access token. The portal and the mobile app are
  wired with no token provider yet, so they currently exercise the demo identity path.
- **Android app.** Maintained on the `mobile-app` branch; see *Verification and limitations*.

**Planned / not implemented** — payment execution, findings resolution routes, audit export, trips,
currency conversion, approval-task routing, production object storage (the S3 adapter raises).

## Interactive architecture

### ➡️ **[Explore the Architecture →](docs/architecture/index.md)**

Six interactive diagrams generated from this source, each citing the files and lines it describes,
all pinned to one revision:

| Diagram | What it answers |
|---|---|
| [System architecture](docs/architecture/proofline-system-architecture.html) | What Proofline is made of, and where a request goes |
| [Expense & receipt data flow](docs/architecture/proofline-expense-dataflow.html) | What happens to a receipt from upload to review |
| [Expense claim lifecycle](docs/architecture/proofline-expense-lifecycle.html) | Which states exist, and what does *not* move a claim |
| [Authentication & authorization](docs/architecture/proofline-auth-sequence.html) | How one protected request is authenticated and scoped |
| [Domain data model](docs/architecture/proofline-domain-erd.html) | The real tables, columns, keys and constraints |
| [Policy evaluation & audit](docs/architecture/proofline-policy-audit-flow.html) | How a policy result is produced, and what the audit record guarantees |

Each diagram ships with its editable source (`*.json`) and its validation receipts.

> **How to open them.** GitHub shows `.html` files as source, not as running pages, and this
> repository has **no GitHub Pages deployment configured** — so these links display or download the
> file rather than rendering it. To view a diagram interactively, clone the repository and open the
> `.html` file in a browser; they are self-contained and render offline. Full instructions and a
> suggested presentation order are in [`docs/architecture/index.md`](docs/architecture/index.md).

## Demo walkthrough

**[`docs/architecture/demo-runbook.md`](docs/architecture/demo-runbook.md)** is a three-minute
walkthrough for a live audience — the exact node to focus at each step, what to say, and the point to
land — plus an honesty checklist so the demo never overclaims.

Recommended order: **system architecture → expense data flow → claim lifecycle → policy & audit →
authentication**, with the data model as the technical appendix.

## Technology architecture

| Layer | Implementation |
|---|---|
| **Clients** | Internal console (Next.js 16) · employee portal (Next.js 16) · Expo / React Native mobile app |
| **API** | FastAPI on `/api/v1` — eight routers (health, meta, identity, expense lifecycle, analytics, expenses, receipts, policy) plus a demo-only router |
| **Contract** | `packages/api-client` — types generated from the live OpenAPI document, with CI drift detection |
| **Authorization** | Explicit role→permission map plus organization scoping; no admin shortcut |
| **Identity** | Supabase JWT verification via cached JWKS; demo header provider for local development |
| **Domain** | Expense workflow · receipts & private storage · extraction runs · policy engine · audit · analytics · duplicate signals |
| **Persistence** | PostgreSQL — 28 application tables across four Alembic migrations; enums as varchar + CHECK; money as exact `NUMERIC`, never float |
| **Integrity** | Append-only `audit_events` enforced by a database trigger; idempotency keys; optimistic concurrency |
| **Delivery** | Docker Compose for PostgreSQL; GitHub Actions runs contract, backend, console, portal and mobile jobs |

## Quick start

```bash
# 0. Prerequisites: Node 20+, Python 3.14, Docker Desktop running

# 1. Install workspace dependencies (once, at the repo root)
npm install

# 2. PostgreSQL on port 55432
npm run db:up

# 3. Backend
cd backend
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
cp ../.env.example ../.env          # then set DEMO_MODE=true for a local demo
./.venv/Scripts/alembic upgrade head
./.venv/Scripts/python.exe -m scripts.dev_seed     # safe, idempotent demo data
./.venv/Scripts/uvicorn app.main:app --reload --port 8000

# 4. Internal console (second terminal, from the repo root)
npm run console:dev                 # http://localhost:3001
```

- **API docs:** <http://localhost:8000/docs> — **OpenAPI:** <http://localhost:8000/api/v1/openapi.json>
- **Honest capability list:** <http://localhost:8000/api/v1/meta> (generated from the code)
- Full prerequisites, port-conflict fixes and troubleshooting: [`docs/development-setup.md`](docs/development-setup.md)

### Run the tests

```bash
# Backend — requires PostgreSQL (step 2 above)
cd backend
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/ruff.exe check app scripts tests
./.venv/Scripts/mypy.exe app scripts

# Frontend (repo root)
npm run typecheck && npm run lint && npm run test && npm run api:check
npm run console:build
```

No credentials are needed for the test suite. Two live-integration tests are opt-in and skip by
default (`RUN_OPENCODE_GO_INTEGRATION`, `RUN_INDICOCR_INTEGRATION`).

## Verification and limitations

**Verified.** The backend suite passes in full against a real PostgreSQL instance, with Ruff and mypy
clean and the generated contract free of drift. The console's tests, type checking, linting and
production build pass. Each of the six architecture diagrams passes schema validation, delivery,
strict checking and a real-browser check (light theme at four viewports, dark at two), and its
editable source validates against the same revision.

**Not verified — stated plainly.**

- **Receipt extraction accuracy:** no provider is enabled by default and none has been benchmarked.
  Passing tests prove the plumbing, not extraction quality.
- **Live Supabase authentication:** verification (JWKS, issuer, audience, algorithm allow-list) is
  implemented and covered by tests, but has **not** been exercised against a live Supabase project from
  this repository. Console sign-in is implemented; end-to-end sign-in against a real project is a
  deployment step, not a claim made here.
- **Android:** the Android app lives on the `mobile-app` branch and is **not** part of `main`. Its
  Supabase sign-in branch has an unresolved merge conflict. Passing Android builds do not establish
  authentication against a real Supabase project.
- **Visual review of the diagrams:** they pass automated browser checks; they have not been reviewed by
  eye at presentation resolution.
- **No payment execution** exists, and the audit trigger is database integrity — **not** cryptographic
  immutability, not WORM storage, and not a legal-admissibility claim.
- The fictional demo policy used by the local demo is **not** an authoritative company policy, and is
  seeded only under explicit local demo flags.

## Documentation map

| Document | What it covers |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Rules for anyone — human or agent — changing this repository |
| [`PROOFLINE_BUILD_PLAN.md`](PROOFLINE_BUILD_PLAN.md) | Product thesis, architecture, tech stack, data model, testing, rollout |
| [`docs/api-contract.md`](docs/api-contract.md) | Canonical endpoints, DTOs, enums, errors, pagination, implementation status |
| [`docs/architecture/index.md`](docs/architecture/index.md) | The interactive architecture collection |
| [`docs/architecture/demo-runbook.md`](docs/architecture/demo-runbook.md) | The three-minute demo walkthrough |
| [`docs/architecture-decisions.md`](docs/architecture-decisions.md) | Why the system is shaped this way |
| [`docs/database-design.md`](docs/database-design.md) | Tables, constraints, migrations |
| [`docs/authentication-security.md`](docs/authentication-security.md) | Identity, verification and the security model |
| [`docs/authorization-matrix.md`](docs/authorization-matrix.md) | Who may do what |
| [`docs/role-policy-hierarchy.md`](docs/role-policy-hierarchy.md) | Hierarchy, allowances and policy resolution |
| [`docs/policy-assumptions.md`](docs/policy-assumptions.md) | What cannot be invented, and the open policy questions |
| [`docs/testing-strategy.md`](docs/testing-strategy.md) | What is tested, and what deliberately is not |
| [`docs/development-setup.md`](docs/development-setup.md) | Get the database, backend and tests running |

## The one architectural rule

**One backend, one canonical contract, one deterministic policy engine, one audit history.** The
console, the employee portal and the mobile app are all clients of the same API. No client implements
a reimbursement rule.

- A language model may extract or normalise information. It never decides whether a claim is reimbursable.
- Policy results are `PASS`, `FAIL` or `UNKNOWN`. Missing evidence produces `UNKNOWN`, never a silent pass.
- A possible duplicate is a **candidate**, never a confirmed duplicate and never fraud.
- No policy threshold is implemented before it maps to a verified clause. The database refuses to store
  an unsourced allowance limit or an unvalidated active rule.

## Contributing

1. Read `AGENTS.md`, then the build plan, then `docs/api-contract.md`.
2. A change to an endpoint, field, enum or response shape is a **contract change**: update
   `docs/api-contract.md` and the tests in the same commit. The contract suite fails if an implemented
   route is undocumented.
3. Never invent a policy threshold. Record the ambiguity in `docs/policy-assumptions.md`.
4. Never commit secrets, real receipts or service-role keys.

## Team

Anurag (backend, extraction, policy) · Hrishabh (Android, integration) · Akash (finance dashboard).
Ownership detail is in `PROOFLINE_BUILD_PLAN.md` section 12.

## Licence

Apache 2.0 — see [`LICENSE`](LICENSE). The generated diagrams under `docs/architecture/` document this
repository and carry the same licence.
