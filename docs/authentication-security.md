# Authentication and Security Design

**Status:** the boundaries, interfaces and guards are implemented and tested. The
production identity provider is **not implemented** - see "Deliberate stubs" below.
Nothing in this document should be read as a claim that this system is production
ready or security certified.

## Identity is verified, then authority is loaded from the database

The separation is the whole design:

```
credential  ->  Identity (verified)  ->  Actor (authoritative)  ->  permission + scope check
```

`app/core/security.py` defines the `AuthProvider` protocol and the `Identity` and
`Actor` types. `app/services/actor_service.py` turns an `Identity` into an `Actor` by
reading the caller's memberships, non-revoked role grants and effective permissions
from Proofline's own database.

Consequences, all of them load-bearing:

- A client can never assert a role, employee id, department, grade, allowance or
  approval limit. Those fields are read from the database; a client-supplied copy is
  ignored rather than validated and trusted.
- Membership loss removes access. Only `active` and `on_leave`-status memberships
  resolve; `terminated`, `suspended` and `invited` do not.
- Deactivating a user (`users.is_active = false`, `deactivated_at`) removes access
  immediately, independent of the identity provider's token lifetime.

## Demo mode

`DemoAuthProvider` reads `X-Demo-Actor-Id`, which identifies a **user**, never a role.
It is guarded three ways:

1. `build_auth_provider` refuses to construct it unless demo mode is genuinely
   enabled, falling back to `NoAuthProvider` (which refuses everything).
2. `Settings` validation refuses to start at all when `DEMO_MODE=true` and `APP_ENV`
   is `staging` or `production`, and separately refuses `AUTH_PROVIDER=demo` in those
   environments. So a demo deployment is impossible rather than merely discouraged.
3. When demo mode is off, the demo router is not registered, so its paths answer
   `404` and do not disclose that a disabled demo surface exists.

`X-Demo-Organization-Id` is honoured only when the caller genuinely holds an active
membership in that organization; otherwise `403`. Silently answering from a different
organization is exactly what a cross-tenant leak looks like.

## Deliberate stubs (the honest gaps)

| Component | Behaviour today | Why that is the right kind of failure |
|---|---|---|
| `SupabaseAuthProvider` | raises `NotImplementedYet` for every request | A permissive stub is the single most likely way an authentication gap reaches production unnoticed. Refusing is visible; accepting an unverified token is not. |
| `NoAuthProvider` | refuses every request | The fail-closed default. |
| Supabase/S3 receipt storage | constructor raises | Prevents the application believing it stores receipts when it does not. |
| Extraction provider | returns `ExtractionStatus.UNAVAILABLE` with no fields | No plausible-looking receipt data can be fabricated. |

## Production authentication: what must be implemented

Supabase Auth is the chosen initial identity provider. The implementation must:

1. Read the bearer token from `Authorization`.
2. Fetch and cache the project JWKS from `SUPABASE_JWKS_URL`.
3. Verify the **signature**, and validate `iss` against `SUPABASE_JWT_ISSUER`, `aud`
   against `SUPABASE_JWT_AUDIENCE`, and `exp`/`nbf` with a small bounded clock skew.
4. Reject `alg: none` and any algorithm not in the project's expected set.
5. Map `sub` to `users.external_subject` / `users.auth_provider`.
6. Load memberships, roles and permissions from the Proofline database.

**It must not be implemented by decoding the token without verifying the signature.**
The interface is deliberately narrow (`resolve_identity(request) -> Identity`) so a
different provider can be introduced without touching the expense or policy services.

## Authorization

See `docs/authorization-matrix.md`. Two independent stages - permission and resource
scope - and both must pass.

## Receipt privacy

- Receipt bytes never appear in a DTO. `content_url` is a relative path to an
  authorized endpoint that re-checks ownership on every request.
- No permanent public URL exists anywhere in the storage interface: `ReceiptStorage`
  has no `public_url` member, so no implementation can hand one out.
- Object keys are server-generated (`{org}/{expense}/{uuid}{ext}`) so untrusted input
  never reaches a filesystem path or a bucket key. `app/storage/local.py` additionally
  refuses absolute keys and any key containing `..`.
- Upload validation sniffs the real type from the file's **magic bytes**. The declared
  content type is recorded but never trusted; a shell script claiming to be a JPEG is
  rejected with `UNRECOGNISED_FILE_TYPE`.
- A size cap is enforced before anything is persisted.
- `sha256` is stored and indexed for the exact-duplicate signal, deliberately **not**
  unique: two identical uploads are legitimate and are the case the detector must
  surface.

## Auditability

`audit_events` is append-only at the database level: a PostgreSQL trigger raises on
`UPDATE` and `DELETE`. It carries **no foreign keys**, because a cascading referential
action would make the database try to modify an append-only table - deleting an
organization previously failed because it attempted to null an audit column. Audit
rows therefore outlive the entities they reference, which is the correct behaviour for
an audit log.

This is application/database-level append-only behaviour. It is **not** cryptographic
immutability, is not tamper-evident against someone with database superuser rights,
and must not be described as either.

## Logging and error disclosure

- Structured JSON logs carry a correlation id on every line, tied to the request id
  and therefore to the audit event.
- Redaction is applied by a fixed key denylist (`app/core/logging.py`), not by the
  discipline of whoever writes a log line: tokens, cookies, `database_url`, API keys,
  `raw_text`/`ocr_text`, receipt bytes, email, phone, PAN and card numbers.
- Audit `before`/`after` snapshots are filtered on the way **in**, so a forbidden field
  cannot reach the table rather than being filtered when read.
- Clients never receive a stack trace, SQL fragment, driver message, DSN or provider
  payload. Unexpected errors return a generic message plus the request id, which is
  what lets a reviewer quote one identifier in a bug report.

## Before any real deployment

Not started, and required: real identity provider integration and security testing,
secrets management, encryption in transit and at rest, backup/restore rehearsal,
retention and deletion policy, incident handling, access logging, dependency scanning,
rate limiting, upload malware scanning, and legal/privacy review for the jurisdictions
and vendors involved. Listing these here is not a claim that any of them is done.

**External AI provider use is an open question.** Whether the supplied receipt data may
be sent to a third-party model, and under what retention terms, is recorded in
`docs/policy-assumptions.md` and must be answered before an extraction provider is
configured.
