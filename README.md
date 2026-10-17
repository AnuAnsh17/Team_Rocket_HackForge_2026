# Proofline

**An evidence-first expense auditor** for the Receipt Graveyard problem: turn messy
receipts and a layered expense policy into accurate, explainable, reviewable
reimbursement decisions - including duplicates and month-wide patterns.

> **Current state: receipt-intelligence milestone in progress, not a complete auditor.**
> The `backend` branch now has authorized draft creation, private single/batch receipt
> uploads, persisted extraction jobs, a configurable OpenCode Go vision extractor and
> the existing IndicOCR adapter. The employee portal/mobile capture flows and finance
> receipt review surface consume the canonical API. A real OpenCode Go call remains opt-in;
> extraction accuracy has not been benchmarked. Policy rules, claim submission/review,
> production Supabase authentication and hosted private storage remain incomplete.
> `GET /api/v1/meta` reports the remaining capabilities.

## Start here

| Document | Why you need it |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | Mandatory rules for coding agents and humans working here |
| [`PROOFLINE_BUILD_PLAN.md`](./PROOFLINE_BUILD_PLAN.md) | Product thesis, architecture, tech stack, data model, testing, rollout |
| [`docs/api-contract.md`](./docs/api-contract.md) | Canonical endpoints, DTOs, enums, errors, pagination, implementation status |
| [`docs/policy-assumptions.md`](./docs/policy-assumptions.md) | What cannot be invented, and the open policy questions |
| [`docs/problem-statement-coverage.md`](./docs/problem-statement-coverage.md) | Honest assessment of what the design covers and what the code does |
| [`docs/development-setup.md`](./docs/development-setup.md) | Get the database, backend and tests running |

## The one architectural rule

**One backend, one canonical contract, one deterministic policy engine, one audit
history.** The Android app, the employee web portal and the internal HR/Finance/Admin
console are all clients of the same API. Neither client implements a reimbursement rule.

Consequences worth stating explicitly:

- A language model may extract or normalise information. It never decides whether a
  claim is reimbursable.
- Policy results are `PASS`, `FAIL` or `UNKNOWN`. Missing evidence produces `UNKNOWN`,
  never a silent pass.
- A possible duplicate is a **candidate**, never a confirmed duplicate and never fraud.
- No policy threshold may be implemented before it maps to a verified policy clause. The
  database refuses to store an unsourced allowance limit or an unvalidated active rule.

## Components

| Path | Component | State | Checks |
|---|---|---|---|
| `backend/` | FastAPI + Pydantic + SQLAlchemy + Alembic | Authorized draft and private receipt API; persisted asynchronous extraction runs; OpenCode Go/IndicOCR adapters; deterministic receipt consistency review | See `docs/receipt-extraction.md`; offline tests do not establish provider accuracy |
| `apps/console/` | Next.js internal HR/Finance/Admin console | Authorized receipt lookup, structured extraction review and private original access by expense ID | `npm run console:typecheck`, `npm run console:build`, `npm run console:test` |
| `apps/portal/` | Next.js employee web portal | Multi-image upload, per-receipt status/result display and authorized original access | `npm run portal:typecheck`, `npm run portal:build`, `npm run portal:test` |
| `apps/mobile/` | Expo + React Native employee app | Camera/gallery capture, multi-image upload, status/result display and authorized original access | `npm run mobile:typecheck`, `npm run mobile:test`; device run still needed |
| `packages/api-client/` | Generated TypeScript contract + fetch wrapper | OpenAPI-generated receipt, extraction and upload contracts consumed by all apps | `npm run api:generate`, `npm run api:check` |
| `docs/` | Contract, architecture, database, security, testing, runbooks | Written | - |

Receipt extraction is evidence capture only. It does not populate authoritative claim
fields, run policy rules or approve/reject a claim. Read `docs/receipt-extraction.md` for
provider configuration, privacy, job status, supported formats and known limitations.

## Development commands

```bash
npm install            # once, at the root
npm run api:generate   # regenerate contract types after a backend change
npm run typecheck      # every workspace
npm run lint           # every workspace
npm run test           # every workspace
npm run build          # both Next.js apps

npm run console:dev    # http://localhost:3001  (internal console)
npm run portal:dev     # http://localhost:3000  (employee portal)
npm run mobile:start   # Expo dev server
```

## Documentation map

- **Architecture and decisions** - `docs/architecture-decisions.md`
- **Data model, constraints, migrations** - `docs/database-design.md`
- **Authentication and security** - `docs/authentication-security.md`
- **Who may do what** - `docs/authorization-matrix.md`
- **Hierarchy, allowances, policy resolution** - `docs/role-policy-hierarchy.md`
- **Testing approach and what is untested** - `docs/testing-strategy.md`
- **Evaluation methodology (no results yet)** - `docs/evaluation.md`
- **Demo runbook** - `docs/demo-runbook.md`

## Quick start

```bash
# 1. Database (Docker Desktop must be running)
npm run db:up

# 2. Backend
cd backend
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/alembic upgrade head
cp ../.env.example ../.env          # then set DEMO_MODE=true for a demo
./.venv/Scripts/uvicorn app.main:app --reload --port 8000

# 3. Tests
./.venv/Scripts/python -m pytest -q
```

- API docs: <http://localhost:8000/docs>
- OpenAPI: <http://localhost:8000/api/v1/openapi.json>
- Honest capability list: <http://localhost:8000/api/v1/meta>

Full prerequisites, the port-conflict fix and troubleshooting are in
`docs/development-setup.md`.

## Contributing

1. Read `AGENTS.md`, then the build plan, then `docs/api-contract.md`.
2. A change to an endpoint, field, enum or response shape is a **contract change**:
   update `docs/api-contract.md` and the tests in the same commit. The contract test suite
   fails if an implemented route is undocumented.
3. Never invent a policy threshold. Record the ambiguity in `docs/policy-assumptions.md`.
4. Never commit secrets, real receipts or service-role keys.

## Team

Anurag (backend, extraction, policy) · Hrishabh (Android, integration) · Akash (finance
dashboard). Ownership detail is in `PROOFLINE_BUILD_PLAN.md` section 12.

## Licence

Apache 2.0 - see [`LICENSE`](./LICENSE).
