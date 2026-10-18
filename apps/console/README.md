# Proofline Internal Console

One Next.js application for **HR, managers, finance and organization/policy
administration**, with role-specific navigation. It is the internal review surface: the
employee-facing experience lives in `apps/portal` and `apps/mobile`, and the two are
deliberately separate applications.

> **Receipt review is implemented; the broader auditing workflow is not.** The review
> surface loads receipts by an authorized expense UUID, polls active extraction runs,
> displays normalized fields and backend validation signals, and opens originals through
> the private-content API. An expense/review queue is still absent, so the operator must
> already know the expense ID. Extraction warnings are not policy findings or fraud claims.

## Prerequisites

- Node.js >= 22.13 (validated on 26.7.0)
- The backend running on <http://localhost:8000> - see `docs/development-setup.md`
- `npm install` at the repository root (this app is an npm workspace member)

## Run

```bash
npm run console:dev        # from the repository root; http://localhost:3001
npm run console:build
npm run console:typecheck
npm run console:lint
npm run console:test
```

Port 3001 is used so the employee portal can hold 3000.

## Configuration

Copy `.env.example` to `.env.local`. Only `NEXT_PUBLIC_*` values reach the browser, so
they must hold nothing sensitive: the console talks to the backend API and to nothing
else. No database URL, service-role key, JWT secret or extraction credential belongs in
this app.

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

# Supabase Auth. Both are PUBLIC by design and authorize nothing on their own.
# Leave both empty for demo-only local development; set both for a real sign-in.
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=

# Demo identity. Honoured only when no Supabase project is configured.
NEXT_PUBLIC_DEMO_MODE=true
```

### Two local arrangements, chosen by the environment

| | Demo only | Real Supabase sign-in |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` / `..._ANON_KEY` | empty | set |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | ignored once a project is set |
| Header the console sends | `X-Demo-Actor-Id` | `Authorization: Bearer <access token>` |
| Backend settings | `AUTH_PROVIDER=demo`, `DEMO_MODE=true` | `AUTH_PROVIDER=supabase`, plus `SUPABASE_JWT_ISSUER` and `SUPABASE_JWKS_URL` |
| Sign-in screen | explains that demo mode is active | email/password |

A demo session is labelled **"Demo session — not a real sign-in"** in the header, so it can
never be mistaken for a real one. When Supabase *is* configured the demo header is not sent
at all — not as a fallback, not on error.

## Authentication

The console signs in with `@supabase/ssr`, using the documented cookie-based App Router
pattern: a browser client, a server client and the proxy (`proxy.ts`, Next 16's renamed
middleware). The session lives in cookies, never in `localStorage`, so a reload restores it
and a server-rendered decision never disagrees with the client.

The token is attached through the one existing seam in `src/lib/api.ts`:

```ts
getToken: () => readAccessToken(),   // reads the current session per request
```

`getToken` may be asynchronous; `packages/api-client` awaits it before sending. A token is
read per request, never captured at client construction, so a refresh or an account switch
takes effect immediately and a stale credential cannot be reused.

**What the console does not do.** It never decodes a token to learn who the caller is, never
sends a role, and never treats the presence of a token as proof of identity. Identity comes
from `GET /api/v1/me`, resolved by the backend from the verified token's `sub` and its own
database. Access is therefore the backend's answer, and its three refusals are three
different screens:

| Response | Meaning | What the console does |
|---|---|---|
| **401** | No valid identity (absent or expired token, unprovisioned subject) | Returns to sign-in. No retry. |
| **403** | Valid identity, no active membership or permission | Shows a forbidden state. No retry, no "sign in again" — re-authenticating cannot change a membership. |
| **5xx / network** | The backend did not answer | Shows the error and the request id. Never renders fabricated zeros. |

`GET /api/v1/me` is also what the shell displays: the resolved member's name, employee code,
membership id and status. The console content is keyed on that identity, so switching account
unmounts the previous account's subtree and every page re-fetches — one account's figures
cannot survive into another's.

## The demo role selector is not a security boundary

The header lets you preview navigation as different roles, and enter a demo actor id.
Two things are true about it:

1. **The role dropdown only changes what is displayed.** It is a preview of the intended
   information architecture. The backend knows nothing about it.
2. **The actor id is a user id, never a role.** The backend resolves that user's
   memberships, roles, permissions and resource scope from its own database on every
   request. There is deliberately no way to send a role, because the API client does not
   offer one.

When the backend has demo mode disabled it does not register the demo routes at all and
refuses to construct the demo identity provider, so a build with
`NEXT_PUBLIC_DEMO_MODE=true` pointed at a non-demo backend simply receives 401 and 404. It
cannot grant anything. See `docs/authentication-security.md`.

## Routes

Each route is a real page with a fixed layout and an explicit statement of what is
missing. The `stub` marker in the sidebar comes from `src/lib/navigation.ts`, and a test
fails if any route claims to be implemented while it is not.

| Route | Intended purpose |
|---|---|
| `/` | Overview: review queue, open findings, duplicate candidates, recent activity |
| `/review` | Expense review workbench: receipt evidence, corrected fields, findings |
| `/review/[expenseId]` | One claim in full, with the audit trail |
| `/exceptions` | Missing context, uncertain fields, arithmetic and rule findings |
| `/duplicates` | Duplicate candidates with their independent signals, side by side |
| `/approvals` | Approvals required by reporting line, grade, amount or policy |
| `/hr` | HR review: employment status, profile context, missing HR information |
| `/policy` | Policy registry: versions, clauses, effective assignments |
| `/audit` | Append-only audit history with before/after values |
| `/admin/organization` | Memberships, roles, departments, cost centres, locations, grades |
| `/admin/policy` | Policy and allowance assignments with effective dates |

## Why the overview shows no numbers

Every KPI must come from backend data. `GET /api/v1/analytics/overview` is now implemented,
but the overview page does not consume it in this milestone. The page continues to render
dashes until its separate UI integration is completed. `Metric` requires an explicit
`basis` prop for the same reason: a count without a stated basis is a claim.

## Architecture

```
app/                 routes (App Router); login sits outside the (console) route group
src/components/      AppShell, the auth providers, and the shared UI foundations
src/lib/api.ts       the single place the backend base URL, bearer token and demo actor are resolved
src/lib/auth/        session rules, sign-in actions and error mapping (pure, tested)
src/lib/supabase/    config, browser client, server client and the proxy's session refresh
src/lib/navigation.ts  section/nav definition, including the `implemented` flag
src/lib/tokens.ts    TypeScript mirror of the CSS custom properties in app/globals.css
proxy.ts             session refresh + the sign-in gate (Next 16's middleware)
tests/               route, design-token, auth and analytics assertions
```

### Design tokens

Declared once in `app/globals.css` with Tailwind v4's `@theme`, so each becomes a real
utility class. `src/lib/tokens.ts` mirrors the names for TypeScript, and
`tests/tokens.test.ts` fails if the two lists disagree - including a check that a colour
exists for `UNKNOWN`, because that state must be visually distinct rather than muted.

There is deliberately **no** colour or label implying fraud or risk. The product does not
assert fraud, so it has no visual language for it.

### Status and severity vocabulary

`SeverityBadge` renders `info` as "Informational", `warning` as "Needs attention" and
`blocking` as "Blocks approval" - impact and routing, never conduct. `StatusPill` renders
`rejected` as "Not reimbursed", not "Rejected claim", because a rejected claim means the
expense was not reimbursed, not that the employee did something wrong.

## What is not implemented

Everything the console is ultimately for: listing claims, the review workbench, findings,
duplicate resolution, approvals, policy administration and the audit view. Each page says
which route it is waiting for. The backend reports the same list in machine-readable form
at `GET /api/v1/meta`, and `docs/problem-statement-coverage.md` assesses it honestly.
