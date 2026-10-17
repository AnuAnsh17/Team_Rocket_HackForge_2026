# Proofline Employee Android App

Native Android application for Proofline built with Kotlin and Jetpack Compose (Material 3).

> **This app performs no policy calculations. All decisions come from the backend.**

---

## Verified Toolchain Setup

The app build and test suite have been verified end-to-end on Linux with the following toolchain:

- **JDK 17 Path:** `/home/soni/.jdks/jdk-17` (Eclipse Adoptium OpenJDK 17.0.20.1+1)
- **Android SDK Path:** `/home/soni/Android/Sdk`
  - Platform: `android-35`
  - Build-Tools: `35.0.0`
- **Gradle Wrapper:** Gradle `8.11.1` (`apps/android/gradle/wrapper/gradle-wrapper.jar` and `gradle-wrapper.properties`)

### Environment Variables
Export the toolchain paths before building:
```bash
export JAVA_HOME=/home/soni/.jdks/jdk-17
export PATH=$JAVA_HOME/bin:$PATH
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
```

---

## Backend Connection & Demo Identity

- **Backend Base URL Configuration:** `http://10.0.2.2:8000/api/v1` (configured for Android emulator connecting to host backend)
- **Demo Actor ID:** Passed in `X-Demo-Actor-Id` header with value `00000000-0000-0000-0000-000000000001`
- **Persistent Demo Mode Banner:** Renders at root level above `NavHost` across all screens when demo mode is active.

---

## Verified Build & Test Commands

Run the following commands from `apps/android/`:

### 1. Compile Debug APK (Verified)
```bash
cd apps/android
./gradlew :app:assembleDebug
```
Output: `BUILD SUCCESSFUL`

### 2. Run Unit Tests (Verified)
```bash
./gradlew :app:testDebugUnitTest --info
```
Output: `BUILD SUCCESSFUL` (7 tests passed: `ModelSerializationTest` 4/4, `WordingComplianceTest` 3/3)

### 3. Install & Launch on Emulator or Device
```bash
./gradlew :app:installDebug
```
Then open **"Proofline"** from the Android application launcher.

---

## Project Structure

```
apps/android/
├── build.gradle.kts                      # Root Gradle build configuration
├── settings.gradle.kts                   # Project settings & plugin repositories
├── local.properties                      # sdk.dir=/home/soni/Android/Sdk (git-ignored)
├── gradle/
│   ├── libs.versions.toml                # Dependency version catalog
│   └── wrapper/
│       ├── gradle-wrapper.jar            # Gradle 8.11.1 wrapper JAR
│       └── gradle-wrapper.properties     # Wrapper properties
└── app/
    ├── build.gradle.kts                  # App module dependencies & SDK pins (compileSdk 35)
    └── src/
        ├── main/
        │   ├── AndroidManifest.xml
        │   └── java/org/proofline/android/
        │       ├── ProoflineApplication.kt # Application container & ProoflineApiClient singleton
        │       ├── MainActivity.kt         # Edge-to-edge Compose root with persistent DemoModeBanner
        │       ├── core/
        │       │   ├── model/              # Canonical Enums & DTOs (lean Money, SourceReference)
        │       │   ├── network/            # ProoflineApiClient, Idempotency-Key handling, error decoding
        │       │   └── designsystem/       # Material 3 tokens, Theme, ProoflineScaffold, StatusPill
        │       ├── features/
        │       │   ├── home/               # Screen 1: Dashboard, totals, recent claims, scan CTA
        │       │   ├── claims/             # ClaimsListScreen: Grouped claims list with pull-to-refresh
        │       │   ├── capture/            # Screen 2: Receipt photo capture & upload
        │       │   ├── review/             # Screen 3: Extracted fields review & editing
        │       │   ├── preflight/          # Screen 4: Advisory policy guidance
        │       │   ├── submit/             # Screen 5: SubmitScreen with retained Idempotency-Key
        │       │   ├── status/             # Screen 6: Claim status timeline & details
        │       │   └── correction/         # Screen 7: CorrectionScreen (PATCH with expected_version)
        │       └── navigation/             # ProoflineNavGraph with routes
        └── test/                           # Unit tests (Serialization, Wording Compliance)
```
