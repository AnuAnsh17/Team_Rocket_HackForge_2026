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
./.venv/Scripts/python.exe -m pip install -e ".[dev,benchmark]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev,benchmark]"    # POSIX
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

### Local IndicOCR runtime

IndicOCR runs in a dedicated Python environment separate from the backend venv.
The backend starts one warm subprocess per API worker. Set `EXTRACTION_PROVIDER=local_ocr`,
`EXTRACTION_MODEL` to the existing local model snapshot directory, and
`EXTRACTION_PYTHON_EXECUTABLE` to that isolated environment's Python executable in the
ignored local `.env`. The committed `.env.example` contains placeholders only. Use the
model's own installation instructions for the OCR environment; do not install its
Torch stack into `backend/.venv`.

The runtime verified for this milestone used Python 3.12.10, Torch 2.14.1+cu130,
torchvision 0.29.1+cu130, Transformers 5.20.1, Accelerate 1.15.0, Pillow 12.3.0,
NumPy 2.5.2, and huggingface_hub 2.2.0. This environment ran inference on an NVIDIA
RTX 3050 Laptop GPU. Without CUDA, the worker selects CPU; CPU performance has not
been benchmarked. See `docs/architecture-decisions.md` for the runtime boundary and
limitations.

The model README documents printed recognition for English and 22 Indian languages,
and handwriting recognition for English and 12 Indian languages. This is model
documentation, not a Proofline receipt-accuracy benchmark.

### Structured receipt extraction

For structured receipt extraction through OpenCode Go, keep `OPENCODE_GO_API_KEY`
in the ignored root `.env` or deployment secret store, set
`EXTRACTION_PROVIDER=opencode_go`, and leave the key out of every client environment.
The default model is `deepseek-v4.1-flash` at
`https://opencode.ai/zen/go/v1/chat/completions`.
Uploads are persisted as individual pending jobs and processed by the bounded
in-process worker. See [`receipt-extraction.md`](./receipt-extraction.md) for the
batch endpoint, retry flow, live smoke test and operational limitations.

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

### Signing in with a real identity (Supabase)

A verified Supabase token is not enough on its own: the backend maps the token's
`sub` to a user that must already exist, and then loads that user's memberships and
roles from its own database. A subject with no mapping is `401`; a mapped user with
no active membership is `403`. Nothing is provisioned automatically at login, so a
new subject has to be bound deliberately.

That binding is deliberately a CLI and not an endpoint - "link my account" over HTTP
is an account-takeover primitive - and it never creates a user, a membership or a
role:

```bash
cd backend

# 1. See what would be bound. Print-only; writes nothing without --confirm.
./.venv/Scripts/python -m scripts.provision_identity show \
    --demo-actor 6dbc60b8-8577-56ec-806e-4201fa5993c4

# 2. Bind a Supabase subject to the seeded demo actor. No manual row edits.
./.venv/Scripts/python -m scripts.provision_identity link \
    --subject <the token's sub claim> \
    --demo-actor 6dbc60b8-8577-56ec-806e-4201fa5993c4 \
    --confirm

# 3. Reverse it, leaving the user and their history intact.
./.venv/Scripts/python -m scripts.provision_identity unlink \
    --user 6dbc60b8-8577-56ec-806e-4201fa5993c4 --confirm
```

`--subject`, `--user`, `--demo-actor`, `--membership` are all validated: a subject
that is not the UUID shape a Supabase `sub` has - a pasted access token, an email
address - is refused rather than bound, a user with no active membership is refused
because every request would be `403`, and moving a subject away from another user
requires `--rebind`. Every write appends an audit event in the same transaction.

Two limits are worth knowing before you rely on this. Replacing a *demo* mapping does
not require `--rebind`, because moving from demo mode to real authentication is the
intended path. And clearing a mapping does not revoke demo-mode access: under
`AUTH_PROVIDER=demo` the header carries a seeded user's id and the resolver falls back
to a primary-key lookup, which is exactly what makes seeded demo identities work.
Demo mode exists to be impersonated and is refused outside development; with
`AUTH_PROVIDER=supabase` selected, the demo header authenticates nothing at all.

### Local frontends with real authentication

The supported local arrangement is a hybrid: PostgreSQL, the API and receipt storage
run on this machine, while Supabase Auth (and therefore sign-in and token issuance)
is a hosted service. It is not an offline system - a network outage means nobody can
sign in, though already-issued tokens keep working until they expire.

The console talks to the backend at `NEXT_PUBLIC_API_BASE_URL`
(`http://localhost:8000/api/v1` by default). When it is configured with a Supabase
project it sends `Authorization: Bearer`; when it is not, it can fall back to the
development actor switcher, which is labelled as demo in the UI. See
`apps/console/README.md`.

For the browser to be allowed to call the API at all, the console's origin has to be
in `CORS_ALLOWED_ORIGINS`. Set it as a JSON array:

```bash
CORS_ALLOWED_ORIGINS='["http://localhost:3000","http://localhost:3001"]'
```

The comma-separated form that `_split_origins` also understands is rejected before
that helper runs, because `pydantic-settings` tries to JSON-decode a list field first.
The JSON form is the one that works from the environment.

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
| `CORS_ALLOWED_ORIGINS` | Origins allowed to call the API. Set as a JSON array (see above). |
| `AUTH_PROVIDER` | `demo` / `supabase` / `disabled` |
| `SUPABASE_*` | Identity provider configuration. `SERVER_SERVICE_ROLE_KEY` is server-only. |
| `SUPABASE_JWT_ALGORITHMS` | Asymmetric allowlist, default `RS256,ES256`. An HMAC or `none` entry is refused at startup. |
| `SUPABASE_JWT_LEEWAY_SECONDS` | Bounded clock skew for `exp`/`nbf`/`iat`, default 30. |
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
| `401` with a valid Supabase token | The token's `sub` is not bound to a user yet. Run `scripts/provision_identity link`. |
| `403` with a valid Supabase token | The mapped user has no active membership, or lacks the permission for that route. |
| `403` "no active organization membership" | The user exists but has no active membership. Re-seed, or fix the membership. |
| Console shows a CORS error, backend log says origin rejected | Add the console's exact origin (including port) to `CORS_ALLOWED_ORIGINS` as a JSON array. |
| `SettingsError: error parsing value for field "cors_allowed_origins"` | The comma-separated form is JSON-decoded before the splitter runs. Use the JSON array form. |
| Tests fail connecting to `<db>_test` | The PostgreSQL role needs `CREATEDB`, or pre-create the database. |
| `alembic` cannot find `app` | Run from `backend/`. `prepend_sys_path` is set to `.`. |
| Line-ending churn on Windows | `.gitattributes` normalises text to LF. Do not disable it. |

## 6. Frontend and shared-package setup

Three clients share one contract, generated into `packages/api-client`:

| Package | What | Dev port |
|---|---|---|
| `apps/console` | Next.js internal HR/Finance/Admin console | 3001 |
| `apps/portal` | Next.js employee web portal | 3000 |
| `apps/mobile` | Expo employee Android app | Expo dev server |
| `packages/api-client` | Generated TypeScript types + fetch wrapper | n/a |

```bash
npm install                 # from the repository root; installs every workspace
npm run api:generate        # regenerate the contract types from the backend
npm run api:check           # fail if the committed contract is stale
```

| Command | Purpose |
|---|---|
| `npm run console:dev` / `portal:dev` / `mobile:start` | Run one client |
| `npm run console:build` / `portal:build` | Production build |
| `npm run console:typecheck` / `portal:typecheck` / `mobile:typecheck` | Type check |
| `npm run console:lint` / `portal:lint` / `mobile:lint` | Lint |
| `npm run console:test` / `portal:test` / `mobile:test` | Unit tests |
| `npm run typecheck` / `lint` / `test` / `build` | Every workspace |

Per-client environment files are `apps/<client>/.env.example`. Only `NEXT_PUBLIC_*` and
`EXPO_PUBLIC_*` values reach a client bundle, so no service-role key, extraction API key or
database URL may appear in any of them.

### Client configuration

```dotenv
# apps/console/.env.local and apps/portal/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_DEMO_MODE=true

# apps/mobile/.env.local  (localhost will NOT work from a physical phone)
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.42:8000/api/v1
EXPO_PUBLIC_DEMO_MODE=true
```

For a physical device, bind the backend to all interfaces
(`uvicorn app.main:app --host 0.0.0.0 --port 8000`) and use your machine's LAN address.
Details and the usual failure causes are in `apps/mobile/README.md`.

### Regenerating the contract after a backend change

1. Change the backend Pydantic model or route.
2. `npm run api:generate`
3. Commit `packages/api-client/openapi.json`, `packages/api-client/src/schema.d.ts` and
   `docs/api-contract.md` **in the same commit** as the backend change.
4. CI fails if the artifacts are stale, so this cannot be forgotten.

## 7. Repository layout

```
backend/        FastAPI application, models, migrations, tests, scripts
apps/console/   Next.js internal HR/Finance/Admin console
apps/portal/    Next.js employee web portal
apps/mobile/    Expo employee Android app
packages/api-client/  generated TypeScript types + fetch wrapper
docs/           contract, architecture, database, security, testing, runbooks
data/           synthetic fixture manifests only; never real receipts
.github/        CI
scripts/        root-level workspace helpers
```

## 7. Nothing here is production-ready

Development setup runs against a local database, a private filesystem receipt adapter,
and a demo identity provider. IndicOCR runs only when its isolated interpreter and
cached model paths are configured; otherwise the API records an honest unavailable OCR
status. `GET /api/v1/meta` lists every unimplemented capability in machine-readable
form, and `docs/authentication-security.md` lists what must be implemented before any
real deployment.
