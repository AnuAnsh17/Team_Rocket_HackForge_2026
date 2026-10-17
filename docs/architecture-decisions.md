# Architecture Decisions

Recorded decisions with their reasons and trade-offs. Each entry states what was
decided, why, what it costs, and whether it is reversible cheaply. Entries marked
**OPEN** are not decided and are recorded so nobody silently decides them by accident.

## 1. One backend owns policy, workflow and audit

**Decided.** A single FastAPI service is the only authority for policy evaluation,
workflow transitions and audit history. The Android app, the employee web portal and
the internal console are clients that display what the backend returns.

**Why.** A reimbursement rule implemented twice will diverge. The divergence would be
invisible until an employee and a reviewer see different numbers for the same claim,
which is the worst possible failure for this product.

**Cost.** Every client needs a network round-trip for anything authoritative, and no
client can work fully offline. Accepted: the alternative is two disagreeing rule
engines.

**Enforcement.** No threshold, limit, city cap, time window or exchange rate exists
outside `app/policy`. A unit test scans the policy package for suspicious numeric
literals and fails if one appears without coming from a validated rule parameter.

## 2. Three clients, one contract

**Decided.** `apps/mobile` (Expo), `apps/portal` (employee web) and `apps/console`
(internal HR/Finance/Admin) all consume types generated from the backend's OpenAPI
document via `packages/api-client`. No client defines its own expense model.

**Why.** The brief explicitly forbids independent, conflicting expense models. A
generated client makes a contract drift a compile error rather than a runtime bug.

**Reversible?** Yes, cheaply - the client is a thin wrapper.

## 3. The employee portal and the internal console are separate applications

**Decided.** Two Next.js applications rather than one with role-gated areas.

**Why.** Employee-facing and internal-review surfaces have different audiences,
different deploy cadence and different failure modes. Separating them means an
authorization bug in the internal console cannot expose employee routes, and the
employee bundle does not ship internal review code. It also makes the deploy boundary
explicit.

**Cost.** Some shell, layout and design-token code is shared through `packages/`, and
two builds run in CI. Accepted.

**Note on interpretation.** The brief asks for "one internal console with
role-specific navigation, pages and actions rather than separate, duplicated
applications for HR, finance and administrators" - that is satisfied: all internal
roles live in one console with route groups, not three applications.

## 4. Deterministic policy engine, tri-state, no invented rules

**Decided.** `PASS` / `FAIL` / `UNKNOWN`. `UNKNOWN` is a legitimate answer and is
never converted to `PASS`. The registry ships **empty** and every claim currently
evaluates to `UNKNOWN`.

**Why.** No authoritative policy document has been supplied. Any threshold in the code
would be invented, and an invented rule that approves or rejects real claims is worse
than no rule at all.

**Enforcement is in the schema, not just in the code.** Two CHECK constraints make an
invented rule impossible to store:

- `ck_policy_rules_source_requires_validation` - a rule cannot be `is_active` without a
  source clause, a validator, a validation timestamp and an evaluator type.
- `ck_allowance_profile_items_limit_requires_source` - an allowance amount cannot be
  stored without a cited clause and a currency.

**Cost.** The product demonstrates no automated reimbursement decision today. That is
the honest state, and it is visible in the UI rather than hidden.

## 5. Policy resolution reports unresolved rather than guessing

**Decided.** Precedence is configuration, not specificity. If two approved assignments
at equal priority point at different policy versions, resolution returns *unresolved*
with a reason instead of picking one.

**Why.** "Most specific wins" and "higher grade means higher allowance" are policy
semantics. Assuming either would silently change who gets reimbursed. See
`docs/role-policy-hierarchy.md`.

## 6. Extraction is a replaceable adapter; IndicOCR provides OCR only

**Decided.** `ReceiptExtractor` is provider-neutral. The local IndicOCR adapter runs
in a separate configured Python environment, starts lazily, and keeps one model
loaded in an app-scoped subprocess. It returns provider status and hashes of raw
Markdown/page data; it does not populate structured expense fields. Unconfigured
runtime returns `UNAVAILABLE`; timeout, invalid output, and inference failure have
distinct stable error codes. Raw OCR text is not persisted until its retention
decision is documented.

**Why.** The verified IndicOCR interface produces page/block OCR evidence, not typed
merchant/date/amount fields. Converting OCR prose to canonical financial values is a
separate step and cannot be represented as verified extraction yet.

**Cost.** OCR success proves the engine returned a valid page, not field accuracy or
expense receipt quality. The OCR runtime is installed separately from the pinned
backend Python 3.14 environment. The local `parse(image_path)` interface accepts
image pages; PDF upload is stored but OCR reports failure. Only GPU inference has
been benchmarked in this environment. Each backend process owns one OCR subprocess;
until multi-process GPU memory is benchmarked on the 6 GB RTX 3050, run one backend
worker when local GPU OCR is enabled.

## 6.1 OpenCode Go is the structured receipt provider; deterministic checks stay separate

**Decided.** `EXTRACTION_PROVIDER=opencode_go` selects the backend-only vision adapter
using the OpenCode Go `deepseek-v4.1-flash` chat-completions API and JSON mode. The
server authenticates with `OPENCODE_GO_API_KEY`; no direct DeepSeek API key is used.
`local_ocr` retains the
existing IndicOCR adapter; it is not run alongside OpenCode Go. The adapter sends only
the private image bytes, validates the response against versioned Pydantic fields,
and returns no model-generated workflow state, confidence score or policy decision.
Structured values and server-owned validation metadata are persisted to each
`ExtractionRun`; provider message text and raw OCR Markdown remain memory-only.

**Why.** IndicOCR exposes OCR page text/layout, not structured receipt values. A
replaceable provider lets the existing local engine remain available while allowing
structured extraction without adding a second domain model or exposing credentials
to clients.

**Cost.** External provider use sends receipt images to the configured provider and
may incur cost. No labeled benchmark or accuracy claim is available. Jobs use a
bounded in-process database poller; multiple API replicas multiply configured
concurrency and need deployment coordination. Stale jobs fail rather than silently
retrying and charging again.

**OPEN.** Raw-text retention, a labeled benchmark, ISO currency membership validation,
distributed worker coordination and production hosted storage/authentication remain
unresolved.

## 7. Private object storage with no public URL anywhere in the interface

**Decided.** `ReceiptStorage` exposes only `save`, `read`, `delete`, `exists`. There is
deliberately no `public_url` or `signed_url` member.

**Why.** A storage abstraction that can mint a public URL eventually will. Content is
served only through an authorized endpoint that re-checks ownership.

**Cost.** Streaming every receipt through the API is more expensive than a CDN. If
short-lived signed URLs are added later, they are produced by the route after an
authorization check, not exposed as a general storage capability.

**Local development** uses a private filesystem adapter. Production requires Supabase
Storage or S3; `Settings` refuses `RECEIPT_STORAGE_BACKEND=local` outside local
development.

## 8. Database persistence is synchronous; extraction jobs are persisted and asynchronous

**Decided.** SQLAlchemy 2.x ORM over psycopg3, synchronous sessions, with routes
declared as `def` so FastAPI runs them in its threadpool. Approved by the product owner
during scaffolding.

**Why.** Alembic, SQLAlchemy sessions and test rollback fixtures remain synchronous.
Extraction runs are committed before provider I/O and polled by an app-scoped worker,
so the API never holds a transaction open while waiting on inference.

**Cost.** The poller is process-local and synchronous work runs in a thread pool. The
database state is durable, but this is not multi-replica queue coordination. The
deployment should use one API process per worker until that is implemented.

## 9. Money as NUMERIC/Decimal, serialised as a decimal string

**Decided.** `NUMERIC(20, 4)` in PostgreSQL; `Decimal` in Python; a JSON **string** on
the wire. A JSON number is rejected on input.

**Why.** Binary floating point cannot represent most currency amounts exactly. A client
that sends `0.1` has already lost information.

**Non-obvious detail.** Pydantic emits `{"type": "number"}` alongside `string` in the
JSON schema for a bare `Decimal`. A generated TypeScript client would then type every
amount as `number | string | null` and do float arithmetic. `MoneyString` in
`app/schemas/common.py` pins the schema to `string` and refuses a float at validation
time. A contract test asserts this, because it is exactly the kind of regression
nobody notices until amounts are wrong by a paisa.

## 10. Enum columns are `varchar` + CHECK, not native PostgreSQL enums

**Decided.** Adding a value later is an ordinary migration rather than `ALTER TYPE` on
a live table. **Cost:** no automatic type-level protection against an unlisted value at
the Python level; the CHECK constraint and the Pydantic enum cover that.

## 11. Claim fields and provenance are stored separately

**Decided.** `expenses` holds the current value of each claim field (denormalised for
cheap list and detail queries). `expense_field_evidence` holds immutable,
per-version, per-field provenance. A partial unique index
(`uq_expense_field_evidence_current`) guarantees at most one *current* row per
(claim, field), so the two representations cannot drift silently.

**Why.** "Show me why" needs the value, its source, whether a human reviewed it, the
extraction quality signal and the receipt region - for every field, at the version that
produced a given decision.

**Guard.** A CHECK constraint refuses `receipt_extraction` provenance without a receipt
id, so employee-entered text can never be presented as receipt evidence.

## 12. `audit_events` has no foreign keys

**Decided.** The organisation, actor and policy-version columns are plain indexed
UUIDs, deliberately unconstrained.

**Why, discovered by a failing test.** With `ON DELETE SET NULL`, deleting an
organization made PostgreSQL issue
`UPDATE audit_events SET organization_id = NULL`, which the append-only trigger
refused - so an unrelated operation failed with a confusing error. More importantly, an
audit record must **outlive** the entity it refers to. A historical event that
disappears when its subject is deleted is not an audit trail.

**Trade-off.** Referential integrity for these columns is guaranteed at write time by
`app/audit/writer.py` rather than by the database. Accepted, and documented in the
model docstring so it cannot be mistaken for an oversight. A regression test asserts
both that `audit_events` has zero foreign keys and that deleting a referenced
organization leaves the audit row intact.

## 13. Append-only is application/database-level, not cryptographic

**Decided.** A trigger refuses `UPDATE` and `DELETE` on `audit_events`.

**Explicitly not claimed:** immutability against someone with database superuser
rights, hash-chaining, or external notarisation. The honest description is
"append-only enforcement at the database level". Stated here because it is the kind of
thing that gets over-claimed in a pitch.

## 14. No materialized aggregate table

**Decided.** Aggregates are computed by query over the included claims.

**Why.** The build plan warns that nullable dimensions such as `trip_id` cause
duplicate aggregate rows. A materialized table would need reconciliation and rebuild
logic that does not exist yet. A correct query is better than premature aggregate
complexity.

**Consequence.** The scope fingerprint records an absent dimension as an explicit value
rather than omitting it, so "no trip" is distinct from "not consulted" and re-runs of
the same evaluation are provably identical.

## 15. Pagination is `limit` + opaque `next_cursor` + `total`

**Decided** during contract reconciliation, because the previous prose allowed "limit,
cursor or offset" and one shape is required for a shared client. The cursor is
HMAC-tagged so a hand-edited cursor cannot silently change which page a reviewer sees,
and is deliberately opaque so it can become a keyset cursor later without a contract
change.

## 16. Demo identity identifies a user, never a role

**Decided.** `X-Demo-Actor-Id` carries a user id; roles, permissions and scope are read
from the database. `X-Demo-Organization-Id` is honoured only for a genuine active
membership.

**Why.** A demo switcher that accepted a role claim would be a privilege-escalation
hole wearing a demo badge. Tested in `tests/security/test_authorization.py`.

## 17. Demo seeding activates nothing

**Decided.** The seed creates one fictional organization, fictional people,
memberships, role grants, reporting edges and one **draft, empty** policy version. It
creates no job grades, no allowance profiles, no allowance limits, no policy rules and
no expense claims.

**Why.** Grade levels and allowances are organizational data; a limit without a cited
clause cannot be stored anyway. Claims are created through the application so field
provenance is written by the same code path a real claim uses.

**Trade-off.** The demo has fewer moving parts than a scripted showcase would. It is
also true, which matters more.

## 18. npm workspaces instead of pnpm

**Decided.** pnpm is not installed; npm 11 supports workspaces natively. Adding a
second package manager would need corepack setup on all three machines for no
functional gain. Expo 58 and Next 16 both support npm workspaces monorepos.

**Cost.** Slower installs and weaker phantom-dependency detection than pnpm. Switching
later is mechanical.

## 19. TypeScript pinned to 5.9.3

**Decided.** npm's `latest` is TypeScript 7, the Go-native compiler rewrite.
`@typescript-eslint` 8.x and `eslint-config-next` 16 do not claim TS 7 support.
**Cost:** forgoes TS 7's speed. **Reversible:** yes, once the toolchain supports it.

## 20. Tailwind CSS v4, CSS-first configuration

**Decided.** v4 is the current release and pairs cleanly with Next 16. Design tokens are
declared in CSS rather than in `tailwind.config.js`. **Cost:** v3-era snippets do not
work verbatim; the token file is the single reference.

## Dependency verification

Pinned versions were verified by resolving the stack on the actual toolchain before
being written down, rather than copying current release numbers.

- **Python 3.14** - a full `pip install` resolution succeeded with cp314 wheels for
  every compiled dependency: fastapi 0.143.3, starlette 1.8.0, pydantic 2.14.1,
  pydantic-core 2.50.1, SQLAlchemy 2.1.5, alembic 1.20.0, psycopg 3.3.6,
  uvicorn 0.54.0, python-multipart 0.0.32, httpx 0.28.1, pytest 9.1.1,
  python-json-logger 4.2.0.
- **Node 26.7.0** - satisfies the published `engines` of next 16.4.2 (`>=20.9.0`),
  expo 58.0.14 (`^26.0.0`) and react-native 0.88.0 (`>=26.0.0`).
- **Expo/React Native pins** come from `expo-template-blank-typescript` 58.0.23
  (expo ~58.0.14 / react 19.3.0 / react-native 0.88.0) rather than an invented
  combination.
- **PostgreSQL 18** - `postgres:18-alpine`. Note the 18+ image expects a single mount
  at `/var/lib/postgresql`; the older `/var/lib/postgresql/data` mount point is refused
  by the entrypoint.

## 21. A policy scope carries one of two selectors, decided by the dimension

**Decided** during the scope-resolution follow-up, after a defect made the reason
concrete.

**What was wrong.** `policy_assignments.scope_id` is a UUID, and every scope dimension
used it. Three of the ten dimensions are not UUID-valued: `jurisdiction` and
`legal_entity` are text values recorded on the organization, and `expense_category` is
free text on the claim. The resolver compared `str(scope_id)` against those values, so an
expense-category assignment **could never match**, and legal entity and jurisdiction
returned `False` unconditionally. An assignment that can never apply is worse than a
missing one, because it looks configured.

**What is decided.** A scope carries exactly one selector. `scope_id` (UUID) addresses a
dimension that points at a row in this database; `scope_key` (text) carries a dimension
recorded as a code or name with no table of its own. Which dimensions are which lives in
one place, `app/core/enums.py::UUID_VALUED_SCOPE_TYPES` /
`TEXT_VALUED_SCOPE_TYPES`, and the database CHECK constraint, the resolver's dispatch and
the tests all derive from it.

**Why centralise it.** The original defect was not a typo; it was a dimension being
handled in three separate places (model, resolver, documentation) that disagreed. Making
the classification a single pair of sets means a new dimension cannot be half-supported,
and `scope_selector_kind` raises rather than returning "never matches" for an
unclassified one.

**Enforcement.** `ck_policy_assignments_scope_selector_consistent` refuses a mismatched
selector at the database level, so the defective shape cannot be stored even by a future
code path that forgets the rule. Uniqueness is a functional index over the coalesced,
lower-cased selectors, because a plain unique constraint cannot cover a table where one
of the two columns is always NULL.

**Text matching is normalised by one function, not two.** The canonical form is
`collapse_whitespace(raw).casefold()`, defined in `app/core/scope_keys.py`, with the
whitespace set pinned by a test to exactly Python's `str.isspace()`. Everything else
derives from it.

This paragraph previously claimed that a unique index applying `lower(...)` "applies the
same normalisation" as the resolver's `strip().casefold()`. **That was wrong**, and it was
wrong in the specific way that matters: the two are different functions, so `"in-mh"` and
`" in-mh "` could both be stored while the resolver treated them as one key, and Python's
case folding is not PostgreSQL's lowercasing (`"ß".casefold() == "ss"`). The claim had
been asserted rather than tested, and a review caught it.

The fix was structural, not a patch to either function: **`scope_key` now stores the
canonical form**, so the unique index and the resolver operate on the same string by
construction, and there is no second implementation to drift. A CHECK constraint makes the
database verify what it can compute exactly (trimmed, collapsed, lowercased, non-blank),
and the application verifies the rest. The documented residue is in
`app/core/scope_keys.py`: PostgreSQL cannot compute `casefold()`, so a row written by a
path bypassing the application could in principle be non-canonical; matching canonicalizes
both sides, so the outcome is a reported conflict rather than a silent duplicate.

Normalisation is still narrow. It does **not** declare two different keys equal, and it is
not precedence. Integration tests assert that `"IN"`, `"MH"`, `"IN MH"` and `"IN-MH-01"`
all fail to match `IN-MH`, and that `"in mh"` and `"in-mh"` are separate keys that may
both be stored.

**A lesson worth keeping:** the original defect and this one share a shape — a rule that
existed in two places, with the disagreement invisible because nobody tested the two
against each other. The guard against a repeat is
`tests/unit/test_scope_keys.py::TestMigrationParity`, which fails if the frozen SQL in the
migration stops matching the live expression, and
`test_no_two_keys_the_resolver_considers_identical_can_both_be_stored`, which asserts the
property directly instead of asserting that a particular constraint exists.

**What this deliberately does not do.** No precedence, no tie-breaking, no thresholds, no
reimbursement rule. Where two approved versions compete, resolution still reports a
conflict as *unresolved* rather than choosing, and integration tests assert that even a
higher-priority assignment does not silently win across versions.

**Cost.** One nullable column, one CHECK constraint, one functional index, and a
migration whose downgrade refuses (with a stated reason) rather than deleting rows it
cannot represent in the old shape.

**Reversible?** Yes - `alembic downgrade -1` restores the previous constraint and drops
`scope_key`, refusing only if text-dimension rows exist, since the old schema has nowhere
to put them.

## Open decisions

Recorded so they are not settled by accident. Full detail in
`docs/policy-assumptions.md`.

1. **The authoritative policy document.** Where is it, which version, which clauses?
2. **The receipt dataset** and what use is authorized.
3. **External AI provider use** and its retention/privacy terms.
4. **The organization's operating timezone** and day-boundary rule.
5. **Which claim states count** toward an aggregate cap.
6. **Cap semantics**: does an exceeded cap make only the excess ineligible, the whole
   claim, or require review?
7. **Exchange-rate source and rate date** if conversion is required.
8. **Which approval stages actually exist**, and at what thresholds.
9. **Whether a native APK is required**, or a physical-device Expo app suffices.
10. **Job grades and allowance profiles** - organizational data, not to be invented.
11. **Production auth implementation and security testing.**
12. **Audit retention period** and whether the trail must be exported off-site.
