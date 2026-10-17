# Proofline

**An evidence-first expense auditor** for the Receipt Graveyard problem: turn messy
receipts and a layered expense policy into accurate, explainable, reviewable
reimbursement decisions - including duplicates and month-wide patterns.

> **Current state: scaffold, not a product.** The architecture, data model, API contract
> and authorization model are built and tested. Receipt extraction, policy rules and the
> claim workflow are **not implemented**. `GET /api/v1/meta` lists every unimplemented
> capability in machine-readable form, and `docs/problem-statement-coverage.md` assesses
> coverage honestly. No receipt has ever been processed by this system.

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
| `backend/` | FastAPI + Pydantic + SQLAlchemy + Alembic | Foundation. Health, metadata and three authenticated identity endpoints work. `GET /api/v1/meta` lists every unimplemented capability. | 159 tests, ruff, ruff format, mypy, migration up/down, real server boot |
| `apps/console/` | Next.js internal HR/Finance/Admin console | 11 placeholder routes with role-specific navigation and design tokens | build (12 routes), tsc, eslint, 9 tests |
| `apps/portal/` | Next.js employee web portal | 7 placeholder routes, employee-facing wording rules | build (8 routes), tsc, eslint, 7 tests |
| `apps/mobile/` | Expo + React Native employee app | 5 placeholder screens, theme vocabulary | tsc, eslint, 7 tests, `expo config` resolves. **No device run yet.** |
| `packages/api-client/` | Generated TypeScript contract + fetch wrapper | Consumed by all three clients | `npm run api:check` (drift guard, verified to fail) |
| `docs/` | Contract, architecture, database, security, testing, runbooks | Written | - |

Every frontend screen is a labelled placeholder. Nothing in them uploads, reads, evaluates
or submits anything, and each page names the endpoint it is waiting for.

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
