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

There is deliberately **no default** for `SUPABASE_URL` or `SUPABASE_ANON_KEY`: both
fall back to the empty string, so a build that is not given them still compiles,
still installs, and reports "this build has no Supabase project configured" at
login instead of pointing at somebody else's project. Nothing under `apps/android/`
contains a real project URL, key or JWT: the committed `gradle.properties` holds no
credentials, and `local.properties` is git-ignored. The service-role key has no path
into this app at all - it is not a build property, not a `BuildConfig` field, and
nothing in the module reads it. The anon key, once you do supply it, *will* be baked
into the APK, which is correct and intended: it is a publishable key.

`DEMO_ACTOR_FALLBACK` only has an effect in debug builds; see §4.

### 2.3 Backend base URL (emulator vs. physical device)

There is exactly one runtime base URL - `NetworkConfig.baseUrl`, populated from
`BuildConfig.API_BASE_URL`. No call site hard-codes a host:
`data/repository/ProoflineRepository.kt` takes it as a defaulted parameter from
`NetworkConfig.baseUrl`, and `core/network/ProoflineApiClient.kt` reads it through a
`baseUrlProvider` that defaults to the same value. The only literal in the module is
the build-time default in `app/build.gradle.kts`.

| Where the app runs | Set `API_BASE_URL` to |
|---|---|
| Android emulator, backend on the same machine | `http://10.0.2.2:8000/api/v1/` - the **default**. `10.0.2.2` is the emulator's alias for the host's loopback interface |
| Physical device on the same LAN as your machine | `http://<your-machine-LAN-IP>:8000/api/v1/`, e.g. `http://192.168.1.20:8000/api/v1/`. The backend must bind `0.0.0.0`, not only `127.0.0.1` |
| A deployed backend | `https://your-backend.example.com/api/v1/` |

Override it in `apps/android/local.properties`, in `gradle.properties`, or per build
with `-PAPI_BASE_URL=...`; see §2.2 for the same mechanism.

The `10.0.2.2` default is a deliberate choice for the emulator, not an accident of a
call site. Both plain-HTTP cases above work **only in the debug build**: cleartext is
permitted by `src/debug/AndroidManifest.xml` and by nothing else, so a release build
pointed at a `http://` backend fails at the socket rather than quietly sending
credentials in the clear (see §5).

## 3. Build and test commands

Run these from `apps/android`. The toolchain must be reachable: if `ANDROID_HOME` is
not exported, `local.properties` supplies `sdk.dir`; `JAVA_HOME` must point at JDK 17.

```bash
./gradlew :app:testDebugUnitTest        # JVM unit tests - no device, no emulator
./gradlew :app:assembleDebug            # debug APK
./gradlew :app:assembleRelease          # release APK (cleartext HTTP disabled)
./gradlew :app:lintDebug                # Android lint
```

| Task | Output |
|---|---|
| `:app:testDebugUnitTest` | XML in `app/build/test-results/testDebugUnitTest/`, HTML in `app/build/reports/tests/testDebugUnitTest/` |
| `:app:assembleDebug` | `app/build/outputs/apk/debug/app-debug.apk` |
| `:app:assembleRelease` | `app/build/outputs/apk/release/app-release-unsigned.apk` (unsigned - see §7) |

The debug and release build types differ in exactly the two ways this module asserts:
`BuildConfig.DEBUG`, and therefore whether `HttpClients` enables the logging
interceptor and whether `NetworkConfig.demoHeaderEnabled` can be true (§5); and the
`src/debug/AndroidManifest.xml` overlay, which is the only place
`android:usesCleartextTraffic` is set (§5).

To force a real test run when Gradle reports `testDebugUnitTest UP-TO-DATE`:

```bash
./gradlew :app:cleanTestDebugUnitTest :app:testDebugUnitTest
```

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

### Why this module talks to GoTrue over REST instead of using the Supabase Kotlin SDK

Adding the documented Supabase Kotlin SDK (`io.github.jan-tennert.supabase`, the
`auth-kt` artefact) was attempted and **does not fit this project's toolchain**. The
evidence below was produced by adding the dependency to `app/build.gradle.kts` next to
a throwaway source file that calls the SDK's sign-in API, running
`:app:compileDebugKotlin`, and then restoring the build file byte-for-byte.

| Coordinates tried | Result |
|---|---|
| `auth-kt:3.8.0` + `io.ktor:ktor-client-android:3.5.1` | **Fails twice.** (a) `:app:checkDebugAarMetadata` - `androidx.browser:browser:1.10.0`, pulled in transitively by `auth-kt-android`, "requires libraries and applications that depend on it to compile against version 36 or later of the Android APIs" and "requires Android Gradle plugin 8.9.1 or higher"; this build is AGP 8.5.0 / compileSdk 35. (b) It also bumps `androidx.compose.*` 1.6.6 → 1.9.0 and `androidx.lifecycle` → 2.10.0, which "requires Android Gradle plugin 8.6.0 or higher". |
| `auth-kt:3.0.0` + `ktor-client-android:3.0.0-rc-1` | **Fails.** No AAR-metadata complaint, but it forces `kotlinx-serialization` 1.6.3 → 1.7.2, and the compiler then rejects this app's own `@Serializable` classes: `Your current Kotlin version is 1.9.24, while kotlinx.serialization core runtime 1.7.2 requires at least Kotlin 2.0.0-RC1.` |
| any `auth-kt` 3.1.x-3.8.0 | **Fails.** Built with Kotlin 2.1.10 or newer, so the compiler reports `Class 'io.github.jan.supabase.auth.Auth' was compiled with an incompatible version of Kotlin. The actual metadata version is 2.4.0, but the compiler version 1.9.0 can read versions up to 2.0.0.` |
| `gotrue-kt:2.6.1` + `ktor-client-android:2.3.12` | **Resolves and compiles.** `:app:compileDebugKotlin` succeeds, because Kotlin 2.0.10 metadata is inside the range a 1.9.24 compiler reads. |

`gotrue-kt` 2.x is the *superseded* name of the same SDK - it was renamed to `auth-kt`
at 3.0.0 - and 2.6.1 is the last release of that line. Adopting it would mean adding a
second HTTP stack (Ktor 2.x) beside OkHttp, a second session store (the SDK's own
`multiplatform-settings`-backed one) beside `SharedPreferencesSessionStore`, and a
Kermit-backed logger, in exchange for wrapping three documented REST calls that this
module already implements and tests. On a change that cannot be verified end-to-end
(there is no Supabase project to test against - see §7), that is a net loss, so the
hand-written GoTrue client is kept.

**No Supabase SDK dependency is present in the build, and no half-added dependency was
left behind.** `app/build.gradle.kts` is unchanged from the previous commit.

## 5. Security properties this module asserts

| Property | Where |
|---|---|
| No cleartext HTTP in release | `src/main/AndroidManifest.xml` does **not** set `usesCleartextTraffic`; `src/debug/AndroidManifest.xml` sets it to `true` for the debug build only. Checked in the *merged* manifests: the release one has no `usesCleartextTraffic` attribute at all (so the Android default - cleartext refused - applies), the debug one carries `"true"` |
| No HTTP bodies logged, ever | `core/network/DebugHttpLogger.kt` logs the request/response line and header names only, in any build |
| Credential headers redacted | `HttpLogRedactor` redacts `Authorization`, `apikey`, `Cookie`/`Set-Cookie`, `refresh_token`, `X-Demo-Actor-Id`; the query string is dropped from the logged URL |
| Logging is debug-only | Every caller in `HttpClients` defaults `debugLogging` to `BuildConfig.DEBUG`, so in release the interceptor is constructed `enabled = false` and emits nothing |
| No demo identity in release | `NetworkConfig.demoHeaderEnabled` requires `BuildConfig.DEBUG`, so a release build cannot send `X-Demo-Actor-Id` whatever the build properties say |
| No secret can reach the APK | `SUPABASE_URL` / `SUPABASE_ANON_KEY` come from build properties and **default to the empty string**; the service-role key is not a build property, is never read, and appears nowhere in the module. Checked: the generated `BuildConfig` for **both** build types has `SUPABASE_URL = ""` and `SUPABASE_ANON_KEY = ""` |
| TLS validation untouched | No `TrustManager`, `HostnameVerifier`, `sslSocketFactory` or `networkSecurityConfig` anywhere in the module - platform defaults apply |
| No bearer header on the auth calls themselves | The GoTrue client is built by `HttpClients.auth()`, which carries no `AuthInterceptor`, so a token-renewal call cannot recurse. The one direct `Authorization` header is on `POST /auth/v1/logout`, which is what GoTrue requires |
| No fabricated claim data | `data/sample/` was deleted; the detail screen renders fetched fields or the message "could not be loaded" |
| No silent sample-data substitution | The only synthetic-data path is the debug-only "Seed Backend" button, which calls the real `POST /demo/seed`; no load path falls back to fixtures when a request fails |
| No real project value in git | Supabase URL/key come from build properties with empty defaults; `gradle.properties` is committed and holds no credentials |

## 6. Tests

```bash
./gradlew :app:cleanTestDebugUnitTest :app:testDebugUnitTest
```

Observed on the commit that last touched this file: **76 tests, 0 failures,
0 errors, 0 skipped**, across 12 classes, from a `clean` build. Run JVM tests only -
**no emulator, no device, no live project**. They cover:

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

### 7.1 What *has* been verified

- `./gradlew clean :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease`
  completes with `BUILD SUCCESSFUL` from a clean tree, with 76/76 JVM tests passing.
- Both APKs are produced: `app/build/outputs/apk/debug/app-debug.apk` and
  `app/build/outputs/apk/release/app-release-unsigned.apk`.
- The **merged release manifest** contains no `usesCleartextTraffic` attribute, and the
  merged debug manifest contains `usesCleartextTraffic="true"`.
- The generated `BuildConfig` for both build types has `SUPABASE_URL = ""` and
  `SUPABASE_ANON_KEY = ""`, and `DEBUG = false` in release.
- The module contains no `TrustManager` / `HostnameVerifier` / `sslSocketFactory` /
  `networkSecurityConfig` code, and no service-role key, JWT or database URL.

### 7.2 What is **not** verified

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
   `androidTestImplementation` dependencies are unused scaffolding. The
   sign-out state clearing in `ProoflineViewModel.clearSessionState()` is therefore
   **not** covered by any test - it needs a device or an instrumented test.
10. **The ported full-lifecycle client (`core/network/ProoflineApiClient.kt`) is
    compiled but not wired into any screen.** Only the Retrofit list/detail path is
    used by the UI.
11. **The refresh decision compares wall-clock time to wall-clock time.** The
    provider's expiry is an absolute instant, so this is the correct comparison, but
    `System.currentTimeMillis()` is not monotonic: if the device clock is moved
    *backwards* by more than the remaining token lifetime, an expired access token
    will look fresh and be sent once. The impact is bounded - the backend validates
    `exp` and answers `401`, and a failed renewal clears the session - but there is
    no monotonic-time guard.
12. **A revoked refresh token does not send the user back to the login screen within
    the same process.** On launch, a stored session counts as restorable if both
    tokens are present; if the refresh token has since been revoked server-side, the
    app opens on the app shell and the first request fails, and the session is
    cleared at that point. The way out is the "Sign out" button on the Profile tab
    (or relaunching, since the store is cleared by then). Nothing is fabricated in
    the meantime - the screens show the load error - but the transition is not
    automatic.
13. **`assembleRelease` produces an unsigned APK** (`app-release-unsigned.apk`)
    because no signing config is configured. It is enough to verify the release
    manifest and resource packaging; it is not installable as-is, and no
    minification is applied (`isMinifyEnabled = false`), so R8 shrinking and
    obfuscation of this code are unverified.
14. **`DEMO_ACTOR_FALLBACK` is literally `true` in the release `BuildConfig`** when
    the property is unset, because that property has a default. It has no effect: the
    only consumer, `NetworkConfig.demoHeaderEnabled`, additionally requires
    `BuildConfig.DEBUG`, which is `false` in release.

## 8. Provenance

`core/model/Enums.kt`, `core/model/Models.kt`, `core/model/ModelSerializationTest.kt`,
`core/model/WordingComplianceTest.kt`, `app/proguard-rules.pro`, `apps/android/.gitignore`
and (adapted) `core/network/ProoflineApiClient.kt` were ported from the
`mobile-app-prior` branch. `core/designsystem/Wording.kt` is the part of that
branch's design system the wording tests depend on; the rest of it was not ported
because it needs `material-icons-extended`, which this branch does not depend on.
