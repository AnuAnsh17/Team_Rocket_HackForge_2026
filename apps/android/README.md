# Proofline Android app

The native Android client for Proofline, an evidence-first expense-audit system.
Single Gradle module (`:app`), Jetpack Compose, package `org.proofline.android`,
minSdk 26 / targetSdk 35.

This app **reads nothing from the network it did not ask the backend for**. There
is no bundled fixture data, no sample expense provider and no placeholder status:
if a claim cannot be loaded, the screen says so.

---

## 1. Requirements

| Tool | Version used here |
|---|---|
| JDK | 17 (Temurin 17.0.17) |
| Android SDK | platform 35, build-tools 35.0.0, platform-tools |
| Gradle | via the committed wrapper, 8.11.1 |

`ANDROID_HOME` is not required if `local.properties` exists, but exporting it is
harmless:

```bash
export JAVA_HOME="C:/Program Files/Eclipse Adoptium/jdk-17.0.17.10-hotspot"   # git-bash path style
export ANDROID_HOME="C:/Users/<you>/AppData/Local/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
```

## 2. Local setup

### 2.1 Point Gradle at the SDK

Create `apps/android/local.properties` (git-ignored, never commit it):

```properties
sdk.dir=C\:\\Users\\<you>\\AppData\\Local\\Android\\Sdk
```

### 2.2 Supply the Supabase project

The app needs a Supabase **project URL** and the **publishable anon key**. Both
are read at build time into `BuildConfig.SUPABASE_URL` / `BuildConfig.SUPABASE_ANON_KEY`.
**No real project value is committed anywhere in this repository**; if you build
without supplying them the app still installs and the login screen reports
"this build has no Supabase project configured".

Put them in `apps/android/local.properties` (preferred, already git-ignored) or in
`gradle.properties` on your machine, or pass them per build:

```properties
# apps/android/local.properties
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
SUPABASE_ANON_KEY=YOUR-PUBLISHABLE-ANON-KEY
API_BASE_URL=https://your-backend.example.com/api/v1/
DEMO_ACTOR_ID=6dbc60b8-8577-56ec-806e-4201fa5993c4
DEMO_ACTOR_FALLBACK=true
```

or:

```bash
./gradlew :app:assembleDebug \
  -PSUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co \
  -PSUPABASE_ANON_KEY=YOUR-PUBLISHABLE-ANON-KEY
```

The anon key is publishable by design (it only identifies the project to GoTrue);
the **service-role key must never** be put in this app, in `BuildConfig`, or in
this repository - it would grant full database access to anyone who unzips the APK.

`DEMO_ACTOR_FALLBACK` only has an effect in debug builds; see §4.

### 2.3 Backend

`API_BASE_URL` defaults to `http://10.0.2.2:8000/api/v1/` (the emulator's route to
a backend running on the host). Plain HTTP is permitted **only in the debug
build** - see §5.

## 3. Build and test commands

Run these from `apps/android`:

```bash
./gradlew :app:testDebugUnitTest        # JVM unit tests - no device needed
./gradlew :app:assembleDebug            # debug APK: app/build/outputs/apk/debug/
./gradlew :app:assembleRelease          # release APK (cleartext HTTP disabled)
./gradlew :app:lintDebug                # Android lint
```

The unit test HTML/XML report is written to
`app/build/reports/tests/testDebugUnitTest/` and
`app/build/test-results/testDebugUnitTest/`.

## 4. How authentication works

```
email + password ──POST /auth/v1/token?grant_type=password──▶ Supabase Auth (GoTrue)
                                                            │ access_token, refresh_token, expires_in
session stored in app-private SharedPreferences ◀───────────┘
        │
        │  every backend request: Authorization: Bearer <access_token>
        ▼
Proofline backend ── verifies JWT (JWKS, iss, aud, exp, alg allowlist)
                 └─ maps token `sub` → users.external_subject → membership + roles from its own DB
```

- **Login** (`ui/screens/LoginScreen.kt`, `ui/viewmodel/LoginViewModel.kt`):
  email + password, spinner while submitting, fields and button disabled during
  submission, one error message per failure class, password cleared after every
  attempt.
- **Session persistence** (`core/auth/SessionStore.kt`): access token, refresh
  token and absolute expiry in `SharedPreferences("proofline_auth", MODE_PRIVATE)`.
  The preference file is excluded from cloud backup and device transfer by
  `res/xml/backup_rules.xml` and `res/xml/data_extraction_rules.xml`.
- **Refresh** (`core/auth/SessionManager.kt`): a token is renewed when it is within
  60 seconds of expiry, before the request goes out. Renewal is single-flight, so
  eight concurrent calls produce one refresh - which matters because a rotated
  refresh token cannot be redeemed twice. A session that cannot be renewed is
  deleted rather than retried on every request.
- **Sign-out**: `POST /auth/v1/logout` with the access token (GoTrue revokes that
  session, which is what makes its refresh token unusable), then the local store is
  cleared **unconditionally** - a failed revocation cannot leave a usable session
  on the device.
- **Bearer header** (`core/auth/AuthInterceptor.kt`): installed on the client in
  `di/AppContainer.kt` that every backend call goes through (both the Retrofit
  list/detail client and the full-lifecycle `ProoflineApiClient`). A call site
  cannot forget the header or pass an identity of its own.
- **Start destination** (`ui/navigation/ProoflineNavGraph.kt`): the app opens on the
  login screen when no session is stored, and on the app when one is. An expired
  *access* token does not send you back to login - it is renewed; a missing
  refresh token does.

### The demo actor header is debug-only

`X-Demo-Actor-Id` is a development fallback, never an identity this app claims.
`AuthInterceptor` sends it only when **all** of these hold: the build is a debug
build, `DEMO_ACTOR_FALLBACK` was enabled, the actor id is non-blank, and there is
no session token. In a release build the flag is compiled to `false`. A backend
running `AUTH_PROVIDER=supabase` ignores the header entirely, so a debug build
with no session gets a 401 from such a backend - which is the correct behaviour and
is labelled on screen.

## 5. Security properties this module asserts

| Property | Where |
|---|---|
| No cleartext HTTP in release | `src/main/AndroidManifest.xml` does **not** set `usesCleartextTraffic`; `src/debug/AndroidManifest.xml` sets it to `true` for the debug build only |
| No HTTP bodies logged, ever | `core/network/DebugHttpLogger.kt` logs request/response lines and header names only |
| Credential headers redacted | `HttpLogRedactor` redacts `Authorization`, `apikey`, `Cookie`/`Set-Cookie`, `refresh_token`, `X-Demo-Actor-Id`; the query string is dropped from the logged URL |
| Logging is debug-only | `HttpClients` installs `DebugHttpLoggerInterceptor(enabled = BuildConfig.DEBUG)`; in release the interceptor is disabled |
| No fabricated claim data | `data/sample/` was deleted; the detail screen renders fetched fields or the message "could not be loaded" |
| No real project value in git | Supabase URL/key come from build properties with empty defaults |

## 6. Tests

`./gradlew :app:testDebugUnitTest` runs JVM tests only - **no emulator, no device,
no live project**. They cover:

- session persistence round-trip and the "torn write is not a session" cases
  (`core/auth/SessionPersistenceTest`)
- expiry/refresh decisions including the 60-second skew boundary
  (`core/auth/SessionExpiryTest`)
- the session lifecycle: sign-in persists, near-expiry renews and persists the
  renewal, failed renewal clears, single-flight refresh, sign-out revokes and
  clears (`core/auth/SessionManagerTest`)
- bearer-header attachment, renewal before the request, no identity header when
  signed out, demo fallback on/off
  (`core/auth/AuthInterceptorTest`)
- login failure classification: wrong credentials, expired refresh token,
  unconfirmed address, rate limit, network failure, malformed body, server error,
  unconfigured build (`core/auth/SupabaseAuthApiTest`)
- the error copy the login screen shows (`core/auth/LoginErrorMessagesTest`)
- token/API-key/demo-header/query-string redaction, and that bodies are never
  logged (`core/network/HttpLogRedactionTest`)
- ported contract model serialisation and wording-compliance tests
  (`core/model/ModelSerializationTest`, `core/model/WordingComplianceTest`)

## 7. Honest limits (what a green test run does **not** prove)

These are the things that are **not** verified by this repository's test suite:

1. **A passing JVM unit test suite is not proof that a live Supabase session
   works.** The tests exercise this client against a synthesised HTTP layer. They
   prove how the code classifies and persists things; they do not prove that a real
   project accepts the credentials, returns the documented document shape, rotates
   refresh tokens the way this code assumes, or that the JWKS the backend fetches
   matches the token it was given.
2. **No end-to-end run against a real Supabase project has been performed**, and
   no emulator/device run has been performed for this change. Login UI states,
   navigation on process restart, and interceptor behaviour on a real network stack
   are unverified.
3. **The backend in this repository cannot currently accept a Supabase token.**
   `backend/app/core/security.py` still has `SupabaseAuthProvider.resolve_identity`
   raising `NotImplementedYet` (its docstring in `docs/authentication-security.md`
   is explicit that it refuses every request until JWKS validation is implemented
   and security-tested). Until that lands, a real sign-in will succeed at GoTrue
   and then get a `501` from `/api/v1/me`.
4. **There is no just-in-time provisioning.** A Supabase user must already exist as
   a `users` row with `auth_provider='supabase'` and `external_subject=<supabase
   user id>` and hold an active membership, or the backend answers `401` (unknown
   subject) / `403` (no active membership). A successful GoTrue login is not by
   itself enough to use the app. Creating that row is an operational step, not
   something this client does.
5. **The expense endpoints are not implemented in this backend snapshot.**
   `packages/api-client/openapi.json` currently serves `/api/v1/me`, `/api/v1/meta`,
   `/api/v1/demo/*` and `/api/v1/health`; `/api/v1/expenses` and
   `/api/v1/expenses/{id}` are listed in `docs/api-contract.md` as unimplemented.
   Against that backend the list and detail screens will show a load failure, by
   design - they show the truth rather than a fixture.
6. **Tokens are stored in app-private but unencrypted `SharedPreferences`.** They
   are readable by this app's uid, and by anyone with root or a full filesystem
   image. They are excluded from cloud backup and device transfer. Storing them in
   `EncryptedSharedPreferences`/Keystore would be better and was not done, because
   that needs a new dependency this change did not prove.
7. **Token revocation is best-effort.** If `POST /auth/v1/logout` fails (no
   connection, server error), local state is destroyed but the refresh token may
   remain valid at the provider until it expires. There is no retry queue.
8. **No certificate pinning**, no `android:networkSecurityConfig`, and the debug
   build permits cleartext HTTP to any host.
9. **Instrumented tests are not part of this change**; the two
   `androidTestImplementation` dependencies are unused scaffolding.
10. **The ported full-lifecycle client (`core/network/ProoflineApiClient.kt`) is
    compiled but not wired into any screen.** Only the Retrofit list/detail path is
    used by the UI.

## 8. Provenance

`core/model/Enums.kt`, `core/model/Models.kt`, `core/model/ModelSerializationTest.kt`,
`core/model/WordingComplianceTest.kt`, `app/proguard-rules.pro`, `apps/android/.gitignore`
and (adapted) `core/network/ProoflineApiClient.kt` were ported from the
`mobile-app-prior` branch. `core/designsystem/Wording.kt` is the part of that
branch's design system the wording tests depend on; the rest of it was not ported
because it needs `material-icons-extended`, which this branch does not depend on.
