# Testing Strategy

**Current result:** `249 passed, 1 skipped` on the backend suite
(`cd backend && ./.venv/Scripts/python.exe -m pytest -q`). The skipped test is the
opt-in real IndicOCR runtime integration; it passed when run with the local model and
isolated Python paths configured. Frontend test totals are maintained by their own
workspace test commands. CI runs the repository checks on every branch push - see
`.github/workflows/ci.yml`.

## Principles

1. **A test that cannot fail is not a test.** Assertions target the specific refusal or
   guarantee, not merely a status code.
2. **Test the guarantees where they actually live.** CHECK constraints, partial unique
   indexes and the append-only trigger are tested against real PostgreSQL, because they
   have no meaningful SQLite equivalent.
3. **Never weaken a test to get green.** If an expectation is wrong, fix the
   expectation *and* record why it was wrong. Two such corrections were made during
   scaffolding and both are explained in the test docstrings.
4. **Never fabricate output.** If a check cannot run, the blocker is reported.

## Layers

### Unit tests - `tests/unit/` - no database

| File | Covers |
|---|---|
| `test_policy_engine.py` | Field usability (a value without usable provenance is not reliable), `FAIL`-without-evidence rejection, severity is never guilt, scope fingerprint stability, and a structural guard that scans the policy package for invented numeric thresholds near limit-like words. |
| `test_duplicate_signals.py` | Exact-hash matching, the deliberately unimplemented perceptual signal (no fabricated score), field agreement *never* confirming a duplicate, the documented hard-negative case (two different meals with identical totals), pair canonicalisation. |
| `test_storage.py` | MIME sniffing from magic bytes, declared-type-is-not-trusted, oversize and empty rejection, filename sanitisation, path-traversal refusal on read, scoped deletion. |
| `test_config.py` | Fail-closed configuration: demo mode refused in production and staging, local storage refused in production, demo auth refused in production, missing Supabase config refused, valid production config accepted. |
| `test_permissions.py` | The authorization matrix, mostly its negative space: no role holds every permission, an auditor holds no mutation, `org_admin` cannot decide expenses, `hr_reviewer` cannot resolve finance findings. |
| `test_indicocr_adapter.py` | Documented page validation, Unicode-safe worker protocol, timeout/unavailable/invalid-output/unsupported-media/failure statuses, and no structured fields. |

### Integration tests - `tests/integration/` - real PostgreSQL

| File | Covers |
|---|---|
| `test_health_and_meta.py` | Health status per component, no secrets in the payload, request-id echo, hostile request-id replacement, enum catalogue, declared unimplemented capabilities, OpenAPI served inside the versioned prefix. |
| `test_schema_integrity.py` | The 28 expected tables, the hand-written indexes, the trigger, `numeric` (not `float`) money columns, `UPDATE`/`DELETE` refused on `audit_events`, deletion of a referenced organization leaving audit rows intact, an unsourced allowance limit refused, an active rule without a validator refused. |
| `test_demo.py` | Seed counts, no rule activated, no grade or allowance created, no claim created, draft policy version, idempotent re-seed, fictional names only, no email addresses, reset scope, audit events surviving a reset, and route-level authorization. |
| `test_identity_api.py` | `/me`, `/me/roles`, `/me/audit` - authentication required, own-membership-only, unknown and malformed actor ids refused, no internal authorization data leaked. |
| `test_receipt_upload_api.py` | Draft creation, validated and size-limited multipart upload, duplicate bytes, OCR success/failure persistence, private authorized content retrieval and authorization boundaries. |
| `test_indicocr_runtime.py` | Opt-in real-model upload-to-OCR persistence test; set `RUN_INDICOCR_INTEGRATION=1`, `EXTRACTION_MODEL` and `EXTRACTION_PYTHON_EXECUTABLE` to run it. |

### Contract tests - `tests/contract/`

The contract tests are the drift detector between code and
`docs/api-contract.md`:

- every implemented route appears in the document;
- every served enum matches the documented enum table, and every served enum is
  documented;
- every documented error code exists in `app/core/errors.py`;
- money serialises as a decimal string, the JSON schema says `string`, and a JSON
  number is refused;
- `RecommendedAction` is documented as its own enum and differs from `ReviewAction`;
- every contract route is either implemented or declared unimplemented;
- the implemented endpoint count stays below 20; this small slice cannot be mistaken
  for a finished workflow or a complete auditor.

### Security tests - `tests/security/`

Fail-closed behaviour, tenant isolation, resource scope and vertical privilege
escalation. The list is in `docs/api-contract.md` section 8 and mirrors
`docs/authorization-matrix.md`. Notably:

- an employee cannot read a colleague's claim (and the refusal is the *same* error a
  missing record produces);
- a manager with no reporting edge cannot read a claim, while a manager with a live edge
  can - so the refusal is tested alongside its positive control rather than in isolation;
- a client cannot assert a role through a header;
- demo routes answer `404` when demo mode is off.

## Test fixture design

- **A separate database.** `TEST_DATABASE_URL`, or the configured database name with
  `_test` appended, so a run cannot damage development data. The host and port follow
  whatever the developer configured, including a non-default port.
- **The real migration.** The session fixture runs `alembic downgrade base` then
  `alembic upgrade head`. Every test run therefore exercises the migration, and a
  migration that cannot be applied fails the suite immediately.
- **Rollback per test.** Each test runs inside a transaction that is rolled back, so
  tests are order-independent and leak no state.
- **The HTTP client shares that transaction**, so requests and direct fixture work see
  the same uncommitted data.

## Policy-engine testing requirements

A rule may only be activated once all of the following exist as tests:

- `PASS`, `FAIL` and `UNKNOWN` cases;
- boundary cases at the exact limit, one unit below and one unit above;
- scope cases: office vs business trip, location, timezone/date boundary, missing context;
- decimal rounding behaviour for the specific currency;
- an aggregate case where a new claim changes a finding on an existing claim;
- a re-evaluation case proving a retry does not duplicate findings.

Today there are zero rules and therefore zero rule tests, which is stated rather than
implied. The `FAIL`-without-evidence and tri-state invariants *are* tested, because they
must hold before any rule can be added.

## Duplicate-detection testing requirements

- known positive pairs (byte-identical, rotated/cropped/recompressed);
- hard negatives, including two different meals with identical totals and dates;
- algorithm version recorded on every candidate;
- precision and recall reported **with the sample size**, and not claimed at all until
  a labelled set exists.

The manifest in `data/manifests/` defines the shape of each required demo case and
leaves the expected policy outcomes null, because those depend on the policy document.

## Frontend and contract testing

- Type-check and lint on every application, and a production build of both Next.js apps.
- **Contract drift is a build failure.** `npm run api:check` regenerates the OpenAPI
  document and the TypeScript schema from the backend and compares them byte for byte with
  what is committed. This was verified to actually fail: tampering with the committed
  `openapi.json` produced a line-level diff and exit code 1, with the working tree left
  unmodified. A guard that cannot fail is decoration.
- **Navigation tests** assert that every defined route is reachable by at least one role,
  that an auditor is not offered the review sections, and that no route claims to be
  implemented while it is not. That last assertion is the one that keeps a placeholder from
  quietly becoming a lie as the product is built.
- **Wording tests** read the employee-facing component source and assert that no accusatory
  term appears anywhere in it, that the four employee states stay distinct, and that the
  duplicate wording keeps saying "might" and "nothing is assumed".
- **Token tests** assert that every TypeScript design token also exists in the stylesheet,
  that `UNKNOWN` has a colour distinct from `PASS` and `FAIL`, and that no token mentions
  fraud or risk.

Component render tests are deliberately not set up yet. The assertions above target
properties that would actually regress; a render smoke test that asserts a `<div>` exists
would not.

API integration is exercised through the generated client, so a contract drift is a compile
error rather than a runtime surprise in one of three clients.

## What is not tested yet, and why

| Untested | Blocked on |
|---|---|
| Extraction accuracy | No provider selected; no labelled receipt set |
| Policy rule correctness | No authoritative policy document |
| Duplicate precision/recall | No labelled positive/negative pairs |
| End-to-end claim lifecycle | Routes not implemented |
| Production authentication | Provider not implemented |
| Signed-URL expiry, CSV injection | Those routes do not exist |

Every one of these is declared by `GET /api/v1/meta` as an unimplemented capability, so
the gap is machine-readable rather than only documented.
