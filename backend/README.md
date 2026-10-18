# Proofline Backend

FastAPI + Pydantic + SQLAlchemy 2 + Alembic over PostgreSQL 18. This service is the
**only** authority for policy evaluation, workflow transitions and audit history; every
client displays what it returns.

> **State:** a focused receipt OCR slice is implemented: an authorized employee can
> create, correct and submit claims, upload private receipts, and record scoped human
> review decisions with audit history. Configured IndicOCR can process receipts; OCR
> text is not retained and no structured expense fields or policy outcomes are inferred.
> Policy evaluation and production authentication remain **unimplemented**. See
> `GET /api/v1/meta` for the current capability list.

## Prerequisites

- Python >= 3.12 (validated on 3.14.7)
- A reachable PostgreSQL 18 - `docker compose up -d postgres` from the repository root
- Docker Desktop running, if you use the compose database

## Setup

```bash
cd backend
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev,benchmark]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev,benchmark]"    # POSIX

cp ../.env.example ../.env      # then edit; placeholders only
./.venv/Scripts/alembic upgrade head
```

`Settings` reads `.env` from both `backend/` and the repository root, so one file at the
root works from either directory. Real environment variables take precedence over both.

Minimum for local development:

```dotenv
APP_ENV=development
DEMO_MODE=true
DATABASE_URL=postgresql+psycopg://proofline:proofline@localhost:5432/proofline
AUTH_PROVIDER=demo
RECEIPT_STORAGE_BACKEND=local
EXTRACTION_PROVIDER=unavailable
```

To use the verified local IndicOCR runtime, configure `EXTRACTION_PROVIDER=local_ocr`,
`EXTRACTION_MODEL` with the existing cached model directory, and
`EXTRACTION_PYTHON_EXECUTABLE` with the isolated OCR environment's Python executable.
Keep those machine-specific paths in the ignored `.env`; see
[`docs/development-setup.md`](../docs/development-setup.md#local-indicocr-runtime).
The adapter serializes inference through one persistent OCR subprocess per backend
process. Run one backend worker while local GPU OCR is enabled; multiple backend
workers would each load a separate model into GPU memory.

## Run

```bash
./.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

| URL | What |
|---|---|
| `/docs` | Interactive documentation |
| `/api/v1/openapi.json` | The generated contract - the machine-readable source of truth |
| `/api/v1/health` | Health, with a real database probe. Unauthenticated by design. |
| `/api/v1/meta` | Contract version and the honest list of unimplemented capabilities |
| `/api/v1/meta/enums` | Canonical enum catalogue |
| `/api/v1/me`, `/api/v1/me/roles`, `/api/v1/me/audit` | The caller's own data (requires an actor) |
| `POST /api/v1/expenses` | Create an employee-owned draft |
| `GET /api/v1/expenses` | List claims in the caller's authorized scope |
| `GET /api/v1/expenses/{id}` | Read authorized claim details and provenance |
| `PATCH /api/v1/expenses/{id}` | Append a versioned owner correction or scoped reviewer correction |
| `POST /api/v1/expenses/{id}/submit` | Submit an owned claim after validation |
| `POST /api/v1/expenses/{id}/decisions` | Record a scoped human review decision |
| `GET /api/v1/expenses/{id}/audit` | Read authorized claim history |
| `POST /api/v1/expenses/{id}/receipts` | Upload and OCR a receipt synchronously |
| `GET /api/v1/receipts/{id}` | Read authorized receipt and extraction status |
| `GET /api/v1/receipts/{id}/content` | Retrieve private content after authorization |
| `GET /api/v1/analytics/overview` | Organization-scoped transaction-date dashboard aggregates |
| `GET /api/v1/analytics/spend` | Paginated spend grouped by month, department, location, category, employee or status |
| `POST /api/v1/demo/seed`, `POST /api/v1/demo/reset` | Seed/reset the synthetic lifecycle dataset in demo mode |

## Authentication in development

Demo mode uses `X-Demo-Actor-Id` carrying a seeded **user** id - never a role. Obtain ids
from the seed:

```bash
./.venv/Scripts/python scripts/dev_seed.py
curl -s http://localhost:8000/api/v1/me -H "X-Demo-Actor-Id: <id from the seed output>"
```

Demo mode is refused when `APP_ENV` is `staging` or `production`; the process will not
start with that combination. Production authentication is deliberately unimplemented and
refuses every request rather than accepting an unverified token - see
`docs/authentication-security.md`.

Analytics requires both `expense:read_org_scoped` and an analytics permission.
Finance reviewers receive aggregate views; `analytics:read_org` also enables
employee-level drilldown for finance administrators and auditors. Employee grouping
and filtering is not available to other roles. See `docs/api-contract.md` for date,
currency and missing-data semantics. The internal console overview remains a
placeholder and does not consume these endpoints yet.

## Tests and checks

```bash
./.venv/Scripts/python -m pytest -q                     # full suite (needs PostgreSQL)
./.venv/Scripts/python -m pytest -m unit -q             # no database required
./.venv/Scripts/python -m ruff check .
./.venv/Scripts/python -m mypy app
```

The suite creates `<database>_test` if absent and runs the real migration
(`alembic downgrade base` then `upgrade head`) once per session, so every run exercises
the migration. Override with `TEST_DATABASE_URL`.

## Layout

```
app/main.py            application factory, middleware, router mounting
app/core/              config, logging, errors, middleware, security, permissions,
                       pagination, canonical enums
app/api/               HTTP layer: dependency wiring and the v1 routes
app/schemas/           Pydantic DTOs - the source of the generated OpenAPI document
app/models/            SQLAlchemy persistable models
app/db/                declarative base, naming convention, session factory
app/services/          transactional boundaries and authorization resolution
app/policy/            rule protocol, registry, evaluator, resolution  (zero rules)
app/extraction/        ReceiptExtractor protocol, unavailable fallback, IndicOCR adapter/worker
app/storage/           private receipt storage abstraction
app/context/           evaluation scope, fingerprint, re-evaluation planning
app/duplicates/        candidate signal generation
app/audit/             append-only audit writer (no update or delete path exists)
migrations/            Alembic; 0001_initial_schema is the baseline
tests/                 unit / integration / contract / security
scripts/               dev_seed, dev_reset, export_openapi
```

## Architectural rules that bite

- **No policy threshold in code.** Limits come from validated rule parameters and a cited
  clause. A unit test scans `app/policy/` for suspicious literals; the database refuses an
  unsourced allowance limit and an unvalidated active rule.
- **Never trust a client for authority.** Identity is verified, then membership, roles
  and permissions are loaded from the database. A client-sent role is ignored.
- **Two authorization gates.** Permission *and* resource scope must both pass.
- **Money is `Decimal` end to end**, serialised as a JSON string, and a JSON number is
  refused.
- **`audit_events` is append-only** via a database trigger, and deliberately has no
  foreign keys - a cascade would try to rewrite history.
- **Unimplemented means 501, not a plausible stub.** Extraction, Supabase auth and
  hosted storage all raise rather than pretend.

## Docker

```bash
docker build -t proofline-backend ./backend
docker run --rm -p 8000:8000 --env-file .env proofline-backend
```

The image runs as a non-root user and contains no `.env`. It is a build definition for
development and a demo deploy; it has **not** been through a production hardening review.
