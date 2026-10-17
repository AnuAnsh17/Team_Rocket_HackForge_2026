# @proofline/api-client

Generated TypeScript types for the Proofline API, plus the shared error handling,
pagination and formatting helpers.

**All three clients depend on this package.** The mobile app, the employee web portal and
the internal console import their types from here. None of them defines its own expense
model.

## Why the generated files are committed

`openapi.json` and `src/schema.d.ts` are generated from the backend and **are committed**:

- a client can type-check without booting the backend or provisioning a database;
- CI can detect contract drift without those dependencies;
- a reviewer can see a contract change in the diff of the pull request that caused it.

`npm run check` regenerates both and fails if they differ from what is committed. That is
the mechanism which stops the three clients from drifting apart.

## Commands

```bash
npm run api:generate     # from the repository root: regenerate openapi.json + schema.d.ts
npm run api:check        # fail if the committed artifacts are stale
npm run typecheck        # from this package directory
```

`generate` needs a working backend checkout: it runs
`backend/scripts/export_openapi.py` with the backend virtualenv's interpreter, preferring
`backend/.venv` so the contract matches the pinned dependencies rather than whatever
`python` resolves to on `PATH`.

## Usage

```ts
import { createApiClient, ApiError, unwrap, humanise } from "@proofline/api-client";

const client = createApiClient({
  baseUrl: "http://localhost:8000/api/v1",
  getToken: () => session?.access_token,
});

try {
  const me = await unwrap(client.GET("/me"));
  console.log(me.user.display_name, humanise(me.status));
} catch (error) {
  if (error instanceof ApiError) {
    // The envelope is already parsed: code, message, request_id and details.
    if (error.isStaleVersion) {
      // Someone changed the record since it was loaded; reload and retry.
    }
    console.error(error.code, error.message, error.requestId);
  }
}
```

## What it exports

| Export | Purpose |
|---|---|
| `createApiClient` | A typed client with `Authorization`, `X-Demo-Actor-Id` and `X-Request-ID` handling |
| `unwrap` | Turns an openapi-fetch response into data or a thrown `ApiError` |
| `ApiError` | Parsed error envelope with `isUnauthenticated`, `isForbidden`, `isStaleVersion`, `isNotImplemented` |
| `fetchAllPages` | Cursor pagination with loop protection |
| `formatMoney` | Formats a decimal-string amount. It never performs float arithmetic on it. |
| `humanise` | Enum label with product-specific wording |
| `describeResult` | Employee-facing wording for a `PASS`/`FAIL`/`UNKNOWN` result |
| `paths`, `components`, `Schemas` | The raw generated types |

### Notes that matter

- `ApiError.isForbidden` is distinct from `isUnauthenticated` on purpose. `403` means the
  identity is valid but lacks authority - no active membership, or no permission.
  Re-authenticating will not help, and treating it as "sign in again" hides an
  authorization refusal from the user.
- `humanise` uses an explicit map rather than a generic title-caser. `not_evaluated` must
  read as "Not yet checked" and never as "ineligible", and `email_simulated` must read as
  demo-only.
- `formatMoney` formats a decimal **string**. Amounts are strings on the wire precisely so
  that no float rounding happens before display.
- Demo mode identifies a user, never a role. The server loads roles from its own
  database, so there is deliberately no option to send a role.

## Regenerating after a backend contract change

1. Change the backend Pydantic model or route.
2. Run `npm run api:generate` from the repository root.
3. Commit `openapi.json` and `schema.d.ts` in the same commit as the backend change,
   because they are one contract change.
4. Update `docs/api-contract.md` too - a contract test fails if an implemented route is
   undocumented.
