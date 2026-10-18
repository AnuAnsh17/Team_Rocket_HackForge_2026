import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

/**
 * Configuration values that differ per machine or per deployment.
 *
 * They are read from Gradle properties (a `-P` flag, `gradle.properties`, or
 * `local.properties`) so that no real Supabase project value is ever committed.
 * The Supabase defaults are empty on purpose: a build that has not been given a
 * project URL and anon key still compiles and installs, and fails at login with
 * an explicit "not configured in this build" error instead of silently pointing
 * at somebody else's project.
 */
val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}

fun configValue(vararg keys: String, default: String = ""): String {
    for (key in keys) {
        val fromProject = providers.gradleProperty(key).orNull
        if (!fromProject.isNullOrBlank()) return fromProject.trim()
        val fromLocal = localProperties.getProperty(key)
        if (!fromLocal.isNullOrBlank()) return fromLocal.trim()
    }
    return default
}

fun kotlinStringLiteral(value: String): String =
    "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

val apiBaseUrl = configValue("API_BASE_URL", "apiBaseUrl", default = "http://10.0.2.2:8000/api/v1/")
val supabaseUrl = configValue("SUPABASE_URL", "supabaseUrl")
val supabaseAnonKey = configValue("SUPABASE_ANON_KEY", "supabaseAnonKey")
val demoActorId = configValue(
    "DEMO_ACTOR_ID",
    "demoActorId",
    default = "6dbc60b8-8577-56ec-806e-4201fa5993c4"
)
val demoActorFallback = configValue("DEMO_ACTOR_FALLBACK", default = "true").toBoolean()

android {
    namespace = "org.proofline.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.proofline.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        buildConfigField("String", "API_BASE_URL", kotlinStringLiteral(apiBaseUrl))
        buildConfigField("String", "SUPABASE_URL", kotlinStringLiteral(supabaseUrl))
        buildConfigField("String", "SUPABASE_ANON_KEY", kotlinStringLiteral(supabaseAnonKey))
        buildConfigField("String", "DEMO_ACTOR_ID", kotlinStringLiteral(demoActorId))
        buildConfigField("Boolean", "DEMO_ACTOR_FALLBACK", demoActorFallback.toString())
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            applicationIdSuffix = ".debug"
            isDebuggable = true
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.04.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("com.google.android.material:material:1.11.0")

    // Networking. The OkHttp logging interceptor is deliberately not a dependency:
    // HTTP logging is done by DebugHttpLoggerInterceptor, which never logs a body
    // and redacts credential headers.
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Image loading
    implementation("io.coil-kt:coil-compose:2.6.0")

    // Testing: JVM unit tests only. Nothing in this list needs a device.
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    testImplementation("com.squareup.okhttp3:okhttp:4.12.0")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
