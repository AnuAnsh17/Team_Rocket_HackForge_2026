# Proofline — judges' demo runbook

Everything below runs against the **seeded demo database** (296 claims, 10 departments, 295
receipts, 40 duplicate-review candidates). No figure on the dashboard is hard-coded: every
number is returned by a PostgreSQL aggregate over that data.

## 1. Start it

```bash
docker compose --profile demo up -d --build
```

Then open **http://localhost:3000**.

| What | URL |
| --- | --- |
| **Console dashboard** (show this) | **http://localhost:3000** |
| API documentation (Swagger) | http://localhost:8011/docs |
| API health | http://localhost:8011/api/v1/health |
| Machine-readable contract | http://localhost:8011/api/v1/openapi.json |
| PostgreSQL (seeded demo data) | `localhost:55432`, database/user/password all `proofline` |

```bash
docker compose --profile demo ps       # service state
docker compose --profile demo logs -f console
docker compose --profile demo down     # stop, keep the data volume
```

`POSTGRES_PORT` (see `.env`) pins the database's host port to 55432. The compose default is
5432, which a native PostgreSQL install commonly holds on this machine; leaving it at the
default recreates the database container on 5432 and the API then cannot reach the seeded
data.

## 2. Why the containers reach the host database

The `api` service connects to the demo database through `host.docker.internal:55432` rather
than starting a second PostgreSQL. The dataset already lives in the `proofline-postgres-data`
volume, and seeding a second copy for the same demonstration would create a second source of
truth that can drift from the one the analytics were verified against. The consequence to
know: **the demo database must be running** (`docker compose up -d postgres`).

`NEXT_PUBLIC_API_BASE_URL` is a **build argument**, not a runtime variable, because the
browser resolves that URL and Next.js inlines it at build time. It is set to the API's
published host port (`8011`); pointing it at the compose service name would resolve inside
the container network and fail in the browser. Changing it requires `--build`.

## 3. What to show, in order

1. **Executive KPIs** — claims and requested expenditure for the period, approved
   distinguished from requested, awaiting review, rejected.
2. **Department expenditure** — the table is the strongest section: per department and
   **per currency**, claims, requested, approved, awaiting review, rejected, and the
   department's share. The comparison bars put requested against approved.
3. **Change the period** (filters) and watch every figure, including the department table,
   re-fetch from the database.
4. **Spend matrix** — department × category two-dimensional view.
5. **Claims list → a claim** — the evidence trail, its extraction result and its audit
   history.
6. **Duplicate review** — the 40 seeded duplicate candidates.

## 4. Definitions the dashboard uses

- **Requested** — the sum of persisted claim amounts in the period. Not approved, not paid.
- **Approved** — the subset whose status is approved. Always ≤ requested for the same group.
- **Awaiting review** — the count in `submitted`, `needs_info` or `in_review`; the same
  definition the overview endpoint uses, so the two cannot disagree.
- **Share** — the department's requested amount in its own currency as a fraction of the
  organization total **in that currency**.
- **Nothing is called "paid"** — payment execution is not implemented in this system, so no
  figure anywhere claims to be a payment.
- **Currencies are never combined.** The seeded dataset is multi-currency (GBP, INR, EUR,
  USD, AED, SGD and more), so the dashboard shows a block per currency. There is deliberately
  no single "total expenditure" that adds them together.
- Claims with no transaction date are excluded from the period's figures and counted
  separately rather than being silently dropped or dated to today.

## 5. What this demo is not

State these plainly if asked; they are the honest boundaries.

- **Authentication is the isolated local demo mode**, not Supabase sign-in. The console runs
  with `NEXT_PUBLIC_DEMO_MODE=true` and the API with `DEMO_MODE=true AUTH_PROVIDER=demo`
  (which the API refuses to start with in production). Identity is resolved from seeded
  database rows via an `X-Demo-Actor-Id` header. The real path — server-side JWT verification
  against Supabase JWKS, with roles loaded from the database — is implemented and tested
  (37 security tests, plus a live harness that minted tokens from a generated key pair), but
  no Supabase project is configured here, so sign-in was never exercised end to end.
- **The demo actor is preselected.** In demo mode the console impersonates the seeded finance
  administrator on first load instead of prompting; the actor switcher still works.
- **The data is synthetic** and clearly labelled as such in department names.
- **The images are local demonstration images**, not hardened production builds: the console
  runtime stage carries the full workspace because this project does not use Next's
  `standalone` output.
- **`main` is untouched.** This work is on `feat/judges-live-dashboard` (PR #15).
