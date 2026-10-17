# Proofline Employee Portal

The employee web experience: submit a receipt, check what was read from it, follow the
status of a claim, and see which limits apply to you.

> **State: scaffold.** Routes, layout, design tokens, shared UI and the API integration
> layer exist. **Receipt upload, extraction and claim submission are not implemented.**
> Every page says what is missing and what it is waiting for. Checked in this commit:
> `next build`, `tsc --noEmit`, `eslint`, and 7 tests.

This is a first-class employee experience, not a mobile screen copied into the internal
console. The internal HR/Finance/Admin console is a **separate application**
(`apps/console`), so an authorization defect in one cannot expose the other and the
employee bundle ships no internal review code.

## Prerequisites

- Node.js >= 22.13 (validated on 26.7.0)
- The backend on <http://localhost:8000> - see `docs/development-setup.md`
- `npm install` at the repository root (this app is an npm workspace member)

## Run

```bash
npm run portal:dev         # from the repository root; http://localhost:3000
npm run portal:build
npm run portal:typecheck
npm run portal:lint
npm run portal:test
```

## Configuration

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_DEMO_MODE=true
```

Only `NEXT_PUBLIC_*` values reach the browser, so nothing sensitive may live here. The
portal holds no database URL, no service-role key and no extraction credential: it talks
to the backend API and to nothing else.

## Ownership is enforced by the backend, not by this application

This is the most important thing to know about this app.

There is deliberately **no "my expenses" filter applied in the portal**, and none should
be added. The backend scopes every claim, receipt and audit read to the authenticated
actor, and returns the *same* response for a record that does not exist as for one the
caller may not see, so a claim's existence is never disclosed to someone who should not
know it.

Client-side filtering is not a security control: anyone can call the API directly. If this
application ever appears to hide data by filtering, that is a bug rather than a control.

The demo employee field in the header exists to show this working. It identifies a **user**;
the backend resolves that user's memberships, roles and scope from its own database on
every request, and there is no way to send a role.

## Routes

| Route | Purpose |
|---|---|
| `/` | Home: what you submitted, what is pending, what needs you |
| `/upload` | Add a receipt: photograph or choose an image, then check what was read |
| `/review` | Confirm or correct the extracted merchant, date, total and business context |
| `/expenses` | Everything you have submitted, with its status |
| `/expenses/[expenseId]` | One claim: status, evidence and history |
| `/corrections` | Claims where finance has asked you for something |
| `/allowance` | The limits that apply to you, and the clause each comes from |

## Wording rules

An employee reading a status is in a slightly anxious position. Copy that implies
suspicion changes how people respond to a correction request, and the product does not
assert wrongdoing, so it does not have the vocabulary for it either.

Four states, four distinct meanings, defined once in `src/components/ui.tsx`:

| State | Reads as |
|---|---|
| `needs_info` | "We need something from you" |
| `policy_issue` | "This claim does not meet the policy" — about the claim, not the person |
| `possible_duplicate` | "This might have been submitted twice" — a maybe, and a person will check |
| `in_review` | "A person is reviewing this" |

`tests/wording.test.ts` asserts that no accusatory term appears in the employee-facing
copy, that the four states stay distinct, and that the duplicate wording keeps saying
"might" and "nothing is assumed".

## Why no totals are shown

Every figure on the home screen must come from backend data. The expense and analytics
endpoints are not implemented, so a plausible-looking number would be invented and
indistinguishable from a real one. The pages render empty states and say why.

## Architecture

```
app/                   routes; one directory per task
src/components/ui.tsx  PageHeader, Card, the four employee state banners, notices
src/components/PortalShell.tsx  header, navigation, demo actor field
src/lib/api.ts         the one place the base URL and demo actor are resolved
src/lib/navigation.ts  route definition, including the `implemented` flag
tests/                 route and wording assertions
```

## What is not implemented

Receipt upload and storage, extraction, claim creation and submission, the status
timeline, corrections and the personal allowance view. Each page names the route it is
waiting for. The backend reports the same list in machine-readable form at
`GET /api/v1/meta`.
