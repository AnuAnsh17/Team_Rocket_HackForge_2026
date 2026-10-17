# Development Setup

**Scope of this document:** everything that exists today - the database, the backend
and its test suite. Frontend setup commands are added by the commits that create the
frontends, so this document never documents a command for something that is not there.

## Prerequisites

| Requirement | Validated version | Notes |
|---|---|---|
| Python | 3.14.7 (project requires `>=3.12`) | Windows: `py -3.14`. The full dependency stack resolves with cp314 wheels. |
| Node.js | 26.7.0 (project requires `>=22.13`) | Satisfies `next` (`>=20.9.0`), `expo` (`^26.0.0`) and `react-native` (`>=26.0.0`). |
| npm | 11.19.0 | Workspaces are used. **pnpm is deliberately not required** - see `docs/architecture-decisions.md` §18. |
| Docker Desktop | 29.1.3 | For the development PostgreSQL. Must be running. |
| PostgreSQL client | optional | `psql` 18 is convenient for inspecting the database. |

## 1. Database

```bash
npm run db:up          # docker compose up -d postgres
npm run db:log         # follow container logs
npm run db:down        # stop (keeps the volume)
docker compose down -v # stop and delete the volume (full reset)
```

Default connection: `postgresql+psycopg://proofline:proofline@localhost:5432/proofline`.

### If port 5432 is already in use

A locally installed PostgreSQL service commonly occupies 5432 on Windows. The port is
configurable:

```dotenv
# .env at the repository root
POSTGRES_PORT=55432
DATABASE_URL=postgresql+psycopg://proofline:proofline@localhost:55432/proofline
```

Then `docker compose up -d postgres` publishes on 55432 and the backend reads the same
`DATABASE_URL`. `Settings` reads `.env` from both `backend/` and the repository root, so
one file works from either directory, and real environment variables always win over
either file.

### PostgreSQL 18 mount point

The `postgres:18` images expect a single mount at `/var/lib/postgresql`. The older
`/var/lib/postgresql/data` mount point is **refused by the entrypoint** (it breaks
`pg_upgrade --link`), which shows up as a container that starts and immediately exits.
`docker-compose.yml` uses the correct path; do not "fix" it back.

## 2. Backend

```bash
cd backend
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev]"    # POSIX
```

### Configuration

```bash
cp ../.env.example ../.env      # then edit; .env is gitignored
```

`.env.example` contains placeholders only. Never commit a real value. Environment
variables are validated at startup and the process refuses to boot on a contradictory
combination - for example `DEMO_MODE=true` with `APP_ENV=production`.

### Migrations

```bash
./.venv/Scripts/alembic upgrade head     # apply
./.venv/Scripts/alembic current          # show revision
./.venv/Scripts/alembic downgrade base   # roll all the way back
```

`alembic.ini` deliberately contains no URL; `migrations/env.py` reads `DATABASE_URL`
from application settings so there is one source of database configuration.

### Run the API

```bash
./.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

- Interactive docs: <http://localhost:8000/docs>
- OpenAPI document: <http://localhost:8000/api/v1/openapi.json>
- Health: <http://localhost:8000/api/v1/health>
- What is *not* implemented: <http://localhost:8000/api/v1/meta>

### Seed demo data

Demo mode must be enabled (`DEMO_MODE=true`, non-production). Then either:

```bash
./.venv/Scripts/python scripts/dev_seed.py
# or, over HTTP (an actor id is required and is printed by the seed)
curl -X POST http://localhost:8000/api/v1/demo/seed      -H "X-Demo-Actor-Id: <seeded admin user id>"
```

### Reset

```bash
./.venv/Scripts/python scripts/dev_reset.py
```

Removes only the synthetic organization and demo-provider users, and refuses to run
outside a development environment.

## 3. Tests and checks

```bash
cd backend
./.venv/Scripts/python -m pytest -q                 # full suite
./.venv/Scripts/python -m pytest -m unit -q         # no database needed
./.venv/Scripts/python -m pytest -m "not integration" -q
./.venv/Scripts/python -m ruff check .
./.venv/Scripts/python -m ruff format --check .
./.venv/Scripts/python -m mypy app
```

The suite needs a reachable PostgreSQL. It creates `<database>_test` if it does not
exist, then runs `alembic downgrade base` and `alembic upgrade head` once per session -
so every run exercises the migration itself.

Override the test database with `TEST_DATABASE_URL` if needed.

### Markers

`unit`, `integration`, `contract`, `security`, `demo`.

## 4. Environment variables

`_PUBLIC_` values may be shipped to a client bundle. `_SERVER_` values and anything
ending `_SECRET`/`SERVICE_ROLE_KEY` must never reach a client or a log line.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` / `test` / `staging` / `production` |
| `DEMO_MODE` | Enables demo routes and the demo identity switcher. Refused outside development. |
| `DATABASE_URL` | SQLAlchemy URL. Required explicitly outside development. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins. |
| `AUTH_PROVIDER` | `demo` / `supabase` / `disabled` |
| `SUPABASE_*` | Identity provider configuration. `SERVER_SERVICE_ROLE_KEY` is server-only. |
| `RECEIPT_STORAGE_BACKEND` | `local` / `supabase` / `s3`. `local` refused outside development. |
| `RECEIPT_LOCAL_ROOT` | Private directory for the local adapter. Must be outside any web root. |
| `RECEIPT_MAX_UPLOAD_BYTES` | Upload cap, default 10 MiB. |
| `EXTRACTION_PROVIDER` | `unavailable` by default. Any other value raises until implemented. |

## 5. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Container starts then exits immediately | Wrong PostgreSQL 18 mount point. Use `/var/lib/postgresql`. |
| `port is already allocated` | A local PostgreSQL already holds 5432. Set `POSTGRES_PORT`. |
| `ValueError: DEMO_MODE must be false when APP_ENV is 'production'` | Working as intended. Set `DEMO_MODE=false` or change `APP_ENV`. |
| `ValueError: RECEIPT_STORAGE_BACKEND=local is not permitted` | Working as intended. Configure Supabase/S3 or use a development `APP_ENV`. |
| `401` on every request | Demo mode requires `X-Demo-Actor-Id`. Seed first to obtain an id. |
| `403` "no active organization membership" | The user exists but has no active membership. Re-seed. |
| Tests fail connecting to `<db>_test` | The PostgreSQL role needs `CREATEDB`, or pre-create the database. |
| `alembic` cannot find `app` | Run from `backend/`. `prepend_sys_path` is set to `.`. |
| Line-ending churn on Windows | `.gitattributes` normalises text to LF. Do not disable it. |

## 6. Repository layout

```
backend/        FastAPI application, models, migrations, tests, scripts
docs/           contract, architecture, database, security, testing, runbooks
data/           synthetic fixture manifests only; never real receipts
scripts/        root-level workspace helpers

apps/mobile/    Expo employee Android app          (added by its own commit)
apps/portal/    Next.js employee web portal        (added by its own commit)
apps/console/   Next.js internal HR/Finance/Admin  (added by its own commit)
packages/api-client/  generated TypeScript types + fetch wrapper  (added with apps)
```

This document describes only what exists. The frontend sections of this guide -
prerequisites, environment variables and run commands for `apps/*` - are added by the
commits that create those applications, so no command here ever refers to a directory
that is not yet present.

## 7. Nothing here is production-ready

Development setup runs against a local database, a private filesystem receipt adapter,
a demo identity provider and no extraction provider. `GET /api/v1/meta` lists every
unimplemented capability in machine-readable form, and `docs/authentication-security.md`
lists what must be implemented before any real deployment.
