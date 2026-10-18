# Authentication and Security Design

**Status:** the boundaries, interfaces and guards are implemented and tested. Supabase
access-token verification is **implemented** and covered by a security suite
(`tests/security/test_supabase_jwt.py`) that signs real tokens with a locally generated
RSA key pair; it has not been exercised against a live Supabase project, which is the one
step this repository cannot perform without project credentials. Nothing in this document
should be read as a claim that this system is production ready or security certified.

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
| `SupabaseAuthProvider` | verifies the token against the project JWKS, then the actor resolver loads authority from the database | The failure mode that matters is now the *other* one: a valid token for an unprovisioned subject is `401` and a valid token with no active membership is `403`, so a successful sign-in still grants nothing by itself. |
| `NoAuthProvider` | refuses every request | The fail-closed default. |
| Supabase/S3 receipt storage | constructor raises | Prevents the application believing it stores receipts when it does not. |
| Extraction provider | returns `ExtractionStatus.UNAVAILABLE` with no fields | No plausible-looking receipt data can be fabricated. |

## Production authentication: implemented behaviour

Supabase Auth is the chosen initial identity provider. `app/core/security.py` implements
all six of the requirements this section used to list as outstanding:

1. Read the bearer token from `Authorization`. ✓
2. Fetch and cache the project JWKS from `SUPABASE_JWKS_URL`. ✓
3. Verify the **signature**, and validate `iss` against `SUPABASE_JWT_ISSUER`, `aud`
   against `SUPABASE_JWT_AUDIENCE`, and `exp`/`nbf` with a small bounded clock skew
   (`SUPABASE_JWT_LEEWAY_SECONDS`, default 30s). ✓
4. Reject `alg: none` and any algorithm not in `SUPABASE_JWT_ALGORITHMS` (asymmetric
   only; configuration refuses an HMAC or empty allowlist at startup). ✓
5. Map `sub` to `users.external_subject` / `users.auth_provider`. ✓
6. Load memberships, roles and permissions from the Proofline database. ✓

**It must not be implemented by decoding the token without verifying the signature.** The
interface is deliberately narrow (`resolve_identity(request) -> Identity`) so a
different provider can be introduced without touching the expense or policy services.

## Provisioning: how a verified subject becomes an employee

Verifying a token is only half of authentication. The verified `sub` is an opaque
identifier from Supabase; it means nothing in Proofline until an operator has bound it
to a user that already exists. Until then that subject is `401`, and the reason is
deliberate: if an unknown subject were turned into a new user, anyone who could create
a Supabase account would have created a Proofline account.

The binding is `backend/scripts/provision_identity.py`, and it is a CLI rather than a
route because a self-service "link my account" endpoint is an account-takeover
primitive in either direction - unauthenticated, it lets an attacker claim a known
employee; authenticated, it lets any user claim any unbound identity. The script:

- binds `(provider, subject)` to a target the operator names by id (`--user`,
  `--demo-actor`, or `--membership`), and refuses to create a user or a membership;
- grants no role and revokes no role. Everything that user may do was already in the
  database, so provisioning cannot escalate privilege - a property the tests assert by
  comparing the grants before and after;
- refuses a blank, over-long or whitespace-bearing subject, and refuses a subject that
  is not the UUID shape a Supabase `sub` has - which is what catches a pasted access
  token or an email address before it becomes a permanently dead identity;
- refuses a target whose membership is not active, because that user could only ever
  be `403`;
- writes nothing without `--confirm`, and prints the exact before/after mapping first;
- records an `identity.bound`, `identity.rebound` or `identity.unbound` audit event in
  the same transaction as the change, naming the mapping it replaced;
- relies on `UNIQUE (auth_provider, external_subject)` as the actual guarantee. Moving
  a subject between users clears the previous holder in the same transaction.

### What demo mode can and cannot be made to do

`actor_service._find_user` matches `(auth_provider, external_subject)` and then falls
back to a primary-key lookup, because a seeded demo actor's subject *is* its user id.
So under `AUTH_PROVIDER=demo`, presenting a seeded user's id authenticates as that
user regardless of the stored mapping, and clearing a mapping does not revoke it. That
is demo mode working as documented - it is a development impersonation facility with an
actor picker in the console - and it is why demo mode is refused outside development
and why `DemoAuthProvider` cannot be constructed in production.

The property that matters is that the demo provider is not selected, not that it is
merely unused: with `AUTH_PROVIDER=supabase`, `build_auth_provider` returns
`SupabaseAuthProvider` and the header is never read, so it authenticates nothing. This
is asserted end to end in `tests/security/test_supabase_jwt.py`.

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
