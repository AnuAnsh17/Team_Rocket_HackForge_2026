# Proofline architecture diagrams — shared authoring brief

Read this FIRST, then the Archify skill. Every diagram in this set must be consistent with it.

## Canonical identity (use verbatim in `meta.repository`)

```json
"repository": {
  "url": "https://github.com/AnuAnsh17/Team_Rocket_HackForge_2026",
  "provider": "github",
  "revision": "a779782f3fa093c31eb84aabdad11ee7e937ccb3"
}
```

Repo root for `--repo-root`: the repository root (a clean worktree at exactly that
revision). All `sources[].path` values are repository-relative, e.g.
`backend/app/api/v1/router.py`.

## Output contract

- Working directory for every command: the repository root
- Candidate JSON: `docs/architecture/<slug>.json`
- Rendered HTML: `docs/architecture/<slug>.html`
- `meta.output` must be exactly `docs/architecture/<slug>.html`
- `meta.locale`: `"en"` on every diagram.
- `meta.quality_profile`: `"showcase"` on every diagram.
- `meta.visual_preset`: `"signal-flow"` on every diagram (the requested restrained visual direction).
- Omit `meta.animation` (motion is on by default and reader-controlled).
- Omit `meta.viewBox` for architecture/workflow/sequence/dataflow so the renderer measures height.
- `meta.legend.mode`: `"auto"` unless a diagram must name a custom meaning.

Finalize command shape:

```bash
node "<archify-skill>/bin/archify.mjs" finalize \
  <type> docs/architecture/<slug>.json docs/architecture/<slug>.html \
  --repo-root <repository root> --quality showcase --json
```

A non-zero exit is NOT success. Repair and rerun until it passes. Report the receipt.

## Semantic colour language (use these `type` values consistently)

The renderer colours by component `type`. Keep this mapping identical in all six diagrams:

| `type` | Used for |
|---|---|
| `external` | human actors (employee, reviewer, finance admin), and third-party services |
| `frontend` | the three clients: employee portal (Next.js), internal console (Next.js), Android app (Expo/RN) |
| `security` | Supabase Auth / JWT verification, authorization + scope enforcement, permission gates. Use for identity and security concepts only. |
| `backend` | FastAPI routers, services, domain logic, extraction worker |
| `database` | PostgreSQL tables/stores, object storage |
| `cloud` | deployment-level or managed infrastructure only when evidenced |
| `messagebus` | only if a real queue/broker exists — it does NOT exist here; do not use it |

Relationship `variant`: `emphasis` for the primary end-to-end path, `security` for
authentication/authorization/policy-enforcement edges, `dashed` for optional, deferred, or
not-implemented paths, `default` for everything else. Never use `dashed` for a working path, and
never present a `dashed` edge as if it were live.

## Honesty rules — these override completeness

Every diagram must separate three classes. Encode the class in node `sublabel`, `tag`, or a card,
and use `dashed` edges for anything not verified working:

- **Implemented** — reachable in current source, route registered, service executes, tests cover it.
- **Partial** — real code exists but the full behaviour is not wired or not verified end to end.
- **Planned / not verified** — no code path establishes it. Draw with a dashed edge or leave out.

Specific traps you must NOT fall into:

1. **OCR extraction is NOT proven working.** `EXTRACTION_PROVIDER` defaults to `unavailable`;
   non-default providers fail closed. Uploads and retry endpoints exist and persist an
   extraction *run*; that is not evidence that text was extracted. Model "extraction run pending /
   provider unavailable" honestly.
2. **The policy pre-flight (`POST /api/v1/policy/check`) writes nothing.** It is advisory. It does
   NOT persist findings, decisions, status changes, or audit events. Never draw it as persisting.
3. **A review decision is not payment.** No payment or reimbursement execution exists.
4. **The audit table is append-only via a database trigger** (`trg_audit_events_append_only`).
   That is not cryptographic immutability, not WORM storage, and not a legal-admissibility claim.
   Describe the real guarantee only.
5. **Duplicate candidates are signals, not fraud determinations.** A reviewer confirms or dismisses.
6. **The demo policy is fictional** (`docs/demo-company-expense-policy.md`), seeded only under
   local demo flags. It is not an authoritative company policy.
7. **Analytics aggregates are read-only projections** over persisted claims. They are not a work queue.
8. Do not claim the system is fully connected just because a route is registered.

## Evidence rules

- Only primary elements carry `sources`: architecture components, dataflow nodes, workflow nodes,
  lifecycle states, sequence participants, ERD entities. Relationships carry none.
- `sources` is an array of at most 3 items, each `{ "path", "line", "end_line", "label"? }`.
- Verify every path and line range against the worktree with `nl -ba <file> | sed -n 'A,Bp'`.
  Copy the line numbers you actually saw. Never invent a line number; if you cannot confirm one,
  cite the path with no `line`.
- Keep citations to the file that owns the fact: the caller for a call, the writer for a write,
  the table for a column.

## Shared component vocabulary

Use these exact ids/labels wherever a diagram shows the same component, so a reader can move
between diagrams. Extend with new ids for material detail — never rename these.

| id | type | label | sublabel |
|---|---|---|---|
| `employee` | external | Employee | Expense owner |
| `reviewer` | external | Finance reviewer | Human decision maker |
| `console` | frontend | Internal console | Next.js · review & analytics |
| `portal` | frontend | Employee portal | Next.js · self-service |
| `mobile` | frontend | Android app | Expo / React Native |
| `auth` | security | Supabase Auth | JWT issuer · ES256/RS256 |
| `jwks` | security | JWKS verification | Cached project keys |
| `api` | backend | FastAPI API | /api/v1 · 8 routers |
| `authorize` | security | Authorization & scope | Permissions + org scoping |
| `workflow` | backend | Expense workflow service | Claim lifecycle |
| `exproutes` | backend | Expense & receipt routes | /expenses, /receipts |
| `storage` | database | Receipt object storage | private · local \| Supabase \| S3 |
| `extract` | backend | Extraction worker | provider-dependent |
| `policy` | backend | Policy engine | registry · evaluator · resolution |
| `preflight` | backend | Policy pre-flight | advisory, writes nothing |
| `audit` | backend | Audit service | append-only events |
| `postgres` | database | PostgreSQL | 28 tables · 4 migrations |
| `analytics` | backend | Analytics service | overview · spend · matrix |
| `redis` | — | not present | do not invent |

## Deliverable per diagram

Each author produces exactly: `docs/architecture/<slug>.json`,
`docs/architecture/<slug>.html`, and a passing `finalize` receipt. Then report: slug, the exact
finalize command, its exit code, the receipt's gate summary, every source citation you used with
the line numbers you verified, and anything you could not verify.

Do NOT modify anything under `backend/`, `apps/`, or `packages/`. Documentation and diagram
artifacts only.
