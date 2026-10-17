# Demo Runbook

**Purpose:** reset, run and verify the current build honestly, and know exactly what
does and does not work before standing in front of anyone.

## 0. Read this first

The current build is a **scaffold**. What genuinely works end to end today:

- The API starts, reports health per dependency, and serves its OpenAPI document.
- An authenticated actor can read their own membership, role grants and audit trail.
- The synthetic dataset seeds and resets deterministically, with authorization enforced.
- The database schema, constraints, indexes and append-only audit trigger are real.
- The authorization model refuses cross-organization, cross-employee and
  unpermissioned access - with tests.

What does **not** work and must not be implied:

- Receipt upload, storage and extraction.
- Claim creation, submission, correction and reviewer decisions.
- Policy evaluation: the registry holds zero rules, so every claim would evaluate to
  `UNKNOWN`.
- Production authentication.

`GET /api/v1/meta` states this in machine-readable form. Do not present the scaffold as
a working auditor.

## 1. Pre-flight

```bash
# 1. Docker Desktop running, then:
docker compose up -d postgres

# 2. Backend configured (DEMO_MODE=true, non-production APP_ENV)
cd backend
./.venv/Scripts/alembic upgrade head
./.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

Verify before going further:

```bash
curl -s http://localhost:8000/api/v1/health
# status is "ok" or "degraded"; components.database.status must be "ok".
# "degraded" is expected: extraction and policy are declared missing on purpose.

curl -s http://localhost:8000/api/v1/meta
# Read unimplemented_capabilities out loud before demoing. It is the honest list.
```

## 2. Reset to a deterministic state

```bash
./.venv/Scripts/python scripts/dev_reset.py   # removes only demo data
./.venv/Scripts/python scripts/dev_seed.py    # reloads it, deterministically
```

The seed prints the `X-Demo-Actor-Id` value for every seeded person. Copy the ones you
need - these are the only credentials in demo mode.

Identifiers are derived with `uuid5` from a fixed namespace, so a reset followed by a
seed reproduces the same ids and the same state every time.

## 3. What to demonstrate

A short, truthful walkthrough of the foundation:

1. **Health and honesty.** `GET /api/v1/health` shows the database green and extraction
   and policy explicitly `not_configured`. Say plainly that they are not built.
2. **Identity resolution.** `GET /api/v1/me` with an employee's actor id returns that
   employee's membership. Swap to the finance admin's id and it returns theirs. Roles
   come from the database, not from the request.
3. **Authorization refusing cleanly.** `GET /api/v1/me` with no header is `401`. Seed as
   an employee and `POST /api/v1/demo/seed` is `403`. Set
   `X-Demo-Organization-Id` to another organization and it is `403`.
4. **Append-only audit.** `GET /api/v1/me/audit` shows the actor's own events with a
   correlation id. Show the trigger in `docs/database-design.md`: the database refuses
   `UPDATE` and `DELETE` on `audit_events`.
5. **The schema as the product's argument.** `docs/database-design.md` - the CHECK
   constraints that make an unsourced allowance limit and an unvalidated active rule
   *unstorable*. This is the strongest thing built so far, and it is not a slide.
6. **Demo reset determinism.** Reset and seed again; the same ids appear.

## 4. Fallback

If the database is unavailable, the honest fallback is to show the documentation rather
than a broken terminal: `docs/api-contract.md`, `docs/database-design.md` and the test
output (`pytest -q` with its pass count).

**There is no cached-extraction fallback yet**, because there is no extraction. When a
provider is implemented, the fallback must be labelled as a cached/verified result and
never presented as live inference.

If the demo cannot be shown, say so. A prepared explanation beats a fabricated screen.

## 5. Recording a run

For any recorded demo, note:

- the commit hash (`git rev-parse --short HEAD`);
- which components were real and which were declared missing;
- that no policy rule was evaluated, because none exists.

## 6. Deliberately not in this runbook

- A scripted 3-5 minute narrative with fake findings. The build plan's narrative needs
  extraction, rules and duplicates, none of which exist.
- Any claim of accuracy, fraud detection, calibrated confidence or production
  readiness.
- Screenshots presented as live operation.

## 7. When the real features land

Update this runbook with: the seed's expected rule results per fixture (once the policy
is encoded), a verification pass over the integration path, and a genuinely rehearsed
end-to-end narrative. Until then this document stays honest about a scaffold.
