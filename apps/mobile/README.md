# Proofline Employee Android App

React Native + Expo + TypeScript. Capture a receipt, check what was read from it, submit a
claim and follow its status.

> **Receipt capture is implemented; claim submission is not.** This screen uses Expo Image
> Picker for camera/gallery images, creates an employee draft, uploads a batch through the
> shared API client, shows per-receipt extraction status/fields and loads the original
> through the authorized content endpoint. It does not call DeepSeek directly. Extraction
> values are review evidence and do not submit or approve a claim. See
> [`docs/receipt-extraction.md`](../../docs/receipt-extraction.md).

## Prerequisites

- Node.js >= 26 (Expo 58 declares `^26.0.0`; validated on 26.7.0)
- The backend reachable from the device - see "Physical device testing" below
- `npm install` at the repository root (this app is an npm workspace member)
- For a device or emulator: Expo Go, or a development build

## Run

```bash
npm run mobile:start          # from the repository root
npm run mobile:typecheck
npm run mobile:lint
npm run mobile:test
```

`npm run mobile:android` opens it on a connected device or emulator. Expo will report the
SDK/React Native version combination it expects; the pins in `package.json` come from
`expo-template-blank-typescript` 58.0.23 rather than an invented combination.

## Physical device testing

A phone cannot reach `localhost` on your development machine, so the default
`EXPO_PUBLIC_API_BASE_URL` will not work from a physical device.

1. Find your machine's LAN address: `ipconfig` on Windows, `ipconfig getifaddr en0` on
   macOS, `hostname -I` on Linux.
2. Set it in `.env.local`:

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.42:8000/api/v1
```

3. Start the backend bound to all interfaces, not only loopback:

```bash
cd backend
./.venv/Scripts/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. The device must be on the same network. If a request fails, it is almost always one of:
   the backend bound to `127.0.0.1`, a host firewall blocking the port, or the device on a
   different network or a guest SSID with client isolation.

`app.json` carries `http://localhost:8000/api/v1` as a fallback so a simulator works out of
the box.

## Configuration and secrets

Only `EXPO_PUBLIC_*` values reach the bundle, and **an app bundle is trivially
extractable**. No service-role key, extraction API key, database URL or other server
credential belongs in this application. The app talks to the backend API and to nothing
else.

## Ownership is enforced by the backend

The app does not filter claims by employee, and must never start. The backend scopes every
claim, receipt and audit read to the authenticated actor, and returns the same response for
a record that does not exist as for one the caller may not see, so another employee's claim
is never revealed. Client-side filtering is not a security control. The rule is documented
at the top of `src/api.ts`.

The demo actor id identifies a **user**; the backend resolves that user's memberships, roles
and permissions from its own database. There is no way to send a role.

## Screens

| Route | Screen |
|---|---|
| `app/index.tsx` | Home: what you submitted, what is pending, what needs you |
| `app/capture.tsx` | Receipt capture: photograph or choose, then check |
| `app/review.tsx` | Extraction review: confirm or correct each value |
| `app/status.tsx` | Claim status, in plain language |
| `app/expenses/[expenseId].tsx` | One claim: evidence and history |

## Why the camera permission is not requested

The capture screen does not request `CAMERA` and its buttons are disabled. Asking for a
sensitive permission in exchange for a button that cannot work would be trading a real
privacy cost for nothing. The permission is declared in `app.json` so that enabling it
later is a one-line change once upload works.

## Wording rules

The palette and the vocabulary match the employee web portal, so a status means the same
thing on a phone and in a browser. Two rules are enforced by tests:

- `rejected` reads as **"Not reimbursed"** — a rejected claim means the expense was not
  reimbursed, not that the employee did anything wrong.
- `UNKNOWN` is a first-class result with its own colour and the wording "We could not
  confirm this yet". It is never rendered as a muted or disabled state, and never as a pass.

`tests/wording.test.ts` asserts that no accusatory term appears in the employee-facing copy.
There is deliberately no colour for fraud or risk anywhere in `src/theme.ts`.

## Architecture

```
app/                 expo-router screens
src/components/ui.tsx  Screen, Card, PlaceholderNotice, StatusPill, state banners
src/api.ts           the one place the base URL, demo actor and network wording live
src/theme.ts         colours, spacing, typography, radius and status/result vocabulary
metro.config.js      watches the workspace root so @proofline/api-client resolves
tests/               theme vocabulary and wording assertions
```

## What is not implemented

Camera capture and upload, extraction, claim creation and submission, the status timeline,
corrections and the personal allowance view. Each screen names the route it is waiting for.
The backend reports the same list in machine-readable form at `GET /api/v1/meta`.

## Not validated here

No Android build, emulator run or device test was performed during scaffolding. The
validated checks are TypeScript, lint and the unit tests above; a real device run is a
separate milestone and is listed as such in `docs/problem-statement-coverage.md`.
