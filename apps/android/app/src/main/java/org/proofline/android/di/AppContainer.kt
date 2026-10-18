package org.proofline.android.di

import android.content.Context
import okhttp3.OkHttpClient
import org.proofline.android.BuildConfig
import org.proofline.android.core.auth.SessionManager
import org.proofline.android.core.auth.SessionStore
import org.proofline.android.core.auth.SharedPreferencesSessionStore
import org.proofline.android.core.auth.SupabaseAuthApi
import org.proofline.android.core.network.HttpClients
import org.proofline.android.core.network.ProoflineApiClient
import org.proofline.android.data.repository.ProoflineRepository

/**
 * Composition root.
 *
 * There is exactly one [SessionManager] and one authenticated OkHttp client per
 * process, because two of them would mean two refresh paths racing for the same
 * rotated refresh token.
 *
 * Configuration comes from `BuildConfig`, which is filled from Gradle properties
 * at build time; see apps/android/README.md. If SUPABASE_URL / SUPABASE_ANON_KEY
 * were not supplied the build still runs, [SessionManager.signIn] fails with
 * [org.proofline.android.core.auth.AuthError.NotConfigured], and the login screen
 * says so instead of pretending to try.
 */
class AppContainer(context: Context) {

    val sessionStore: SessionStore = SharedPreferencesSessionStore(context)

    val authApi: SupabaseAuthApi = SupabaseAuthApi(
        supabaseUrl = BuildConfig.SUPABASE_URL,
        anonKey = BuildConfig.SUPABASE_ANON_KEY,
        client = HttpClients.auth()
    )

    val sessionManager: SessionManager = SessionManager(
        store = sessionStore,
        authApi = authApi
    )

    /** The client every Proofline backend call goes through. */
    val backendClient: OkHttpClient = HttpClients.authenticated(sessionManager)

    val repository: ProoflineRepository = ProoflineRepository(client = backendClient)

    /** Full-lifecycle client (create, upload, update, submit, policy check). */
    val apiClient: ProoflineApiClient = ProoflineApiClient(client = backendClient)
}
