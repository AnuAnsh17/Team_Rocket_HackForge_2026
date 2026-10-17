# Proofline Employee Android App (Android Studio + Jetpack Compose)

Native Android application for Proofline built with Kotlin and Jetpack Compose (Material 3).

## Prerequisites

- **JDK 17 requirement:** JDK 17 (or JDK 21) is strictly required to build and run the application. Configure this in Android Studio under **Settings -> Build, Execution, Deployment -> Build Tools -> Gradle -> Gradle JDK**.
- **Android Studio Ladybug (2024.2.1+)** or newer.
- **Android SDK:** `compileSdk 35`, `minSdk 26`, `targetSdk 35`.

## Backend Connection & Demo Identity

- **Backend Base URL:** Defaulted to `http://10.0.2.2:8000/api/v1` in `BuildConfig` for the standard Android Emulator accessing the host dev machine. For physical devices on the same Wi-Fi network, set `NetworkConfig.baseUrl` in `ProoflineApplication.kt` to your LAN IP (e.g. `http://192.168.1.50:8000/api/v1`).
- **Demo Identity (`X-Demo-Actor-Id`):** The app communicates with demo actor ID `00000000-0000-0000-0000-000000000001`. A persistent Demo Mode Banner is displayed on all screens showing this simulated identity.

## Authoritative Policy Rule

> **Important:** This app performs no policy calculations. All decisions come from the backend. The pre-flight policy guidance is advisory only and aggregate limits, cross-claim context, or finance reviewers make final reimbursement determinations.

## How to Build & Run

### 1. From Command Line:
```bash
cd apps/android
./gradlew :app:assembleDebug
./gradlew :app:testDebugUnitTest
./gradlew :app:installDebug
```
Then launch "Proofline" from your emulator's application launcher.

### 2. From Android Studio:
1. Open Android Studio, select **File -> Open** and select `apps/android`.
2. Allow Gradle sync to complete with JDK 17.
3. Select your emulator or connected device and click **Run 'app'**.

## Project Architecture

```
apps/android/
├── build.gradle.kts                      # Root Gradle configuration
├── settings.gradle.kts                   # Project settings
├── local.properties                      # Local SDK path
├── gradle/
│   ├── libs.versions.toml                # Gradle Version Catalog
│   └── wrapper/
│       ├── gradle-wrapper.jar            # Gradle Wrapper JAR
│       └── gradle-wrapper.properties     # Gradle 8.11.1
└── app/
    ├── build.gradle.kts                  # App module dependencies & SDK pins
    └── src/
        ├── main/
        │   ├── AndroidManifest.xml
        │   └── java/org/proofline/android/
        │       ├── ProoflineApplication.kt
        │       ├── MainActivity.kt
        │       ├── core/
        │       │   ├── model/            # Canonical Enums & DTOs (lean Money, SourceReference)
        │       │   ├── network/          # ProoflineApiClient, Idempotency-Key, ErrorEnvelope
        │       │   └── designsystem/     # Theme tokens, Colors, Typography, ProoflineScaffold, StatusPill
        │       ├── features/
        │       │   ├── home/             # Screen 1: Dashboard, monthly totals, recent claims, scan CTA
        │       │   ├── claims/           # ClaimsListScreen & ClaimsListViewModel (Pull-to-refresh & status tabs)
        │       │   ├── capture/          # Screen 2: Receipt photo picker, file validation, upload
        │       │   ├── review/           # Screen 3: Extracted fields review, uncertainty reasons, edit
        │       │   ├── preflight/        # Screen 4: Advisory policy guidance, rule findings breakdown
        │       │   ├── submit/           # Screen 5: SubmitScreen & SubmitViewModel (Idempotency key retained)
        │       │   ├── status/           # Screen 6: Claim status timeline ("Not reimbursed", "We could not confirm")
        │       │   └── correction/       # Screen 7: CorrectionScreen & CorrectionViewModel (PATCH with expected_version)
        │       └── navigation/           # Compose Navigation Graph
        └── test/                         # Unit tests (Serialization, Wording Compliance)
```
