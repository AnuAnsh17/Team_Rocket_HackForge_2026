package org.proofline.android.core.network

import android.util.Log
import okhttp3.OkHttpClient
import org.proofline.android.BuildConfig
import org.proofline.android.core.auth.AuthInterceptor
import org.proofline.android.core.auth.SessionManager
import java.util.concurrent.TimeUnit

/**
 * The only place OkHttp clients are constructed.
 *
 * Centralising it is what makes the two security properties checkable: the
 * logging interceptor is installed only in debug builds and always redacts, and
 * the auth interceptor is installed on the backend client but never on the auth
 * client (an interceptor that renews a token by calling the auth endpoint must
 * not be able to recurse into itself).
 */
object HttpClients {

    private const val LOG_TAG = "ProoflineHttp"
    private const val CONNECT_TIMEOUT_SECONDS = 30L
    private const val READ_TIMEOUT_SECONDS = 30L
    private const val WRITE_TIMEOUT_SECONDS = 30L

    /**
     * Client for talking to Supabase Auth. No auth interceptor, no bearer token:
     * the requests this client makes are the ones that obtain the token.
     * Debug logging only, and the logger redacts the `apikey` header.
     */
    fun auth(debugLogging: Boolean = BuildConfig.DEBUG): OkHttpClient =
        builder().addInterceptor(debugLogger(debugLogging)).build()

    /**
     * Client for talking to the Proofline backend.
     *
     * The auth interceptor is added *before* the logger so the logger sees the
     * final request, headers and all. That is the harder configuration on
     * purpose: it means redaction is genuinely load-bearing rather than
     * accidentally bypassed by interceptor ordering.
     */
    fun authenticated(
        sessionManager: SessionManager,
        debugLogging: Boolean = BuildConfig.DEBUG
    ): OkHttpClient = builder()
        .addInterceptor(
            AuthInterceptor(
                sessionManager = sessionManager,
                demoFallbackEnabled = NetworkConfig.demoHeaderEnabled,
                demoActorId = NetworkConfig.demoActorId
            )
        )
        .addInterceptor(debugLogger(debugLogging))
        .build()

    /** Plain client. Used by tests and by the salvaged full-lifecycle API client. */
    fun base(debugLogging: Boolean = BuildConfig.DEBUG): OkHttpClient =
        builder().addInterceptor(debugLogger(debugLogging)).build()

    private fun builder(): OkHttpClient.Builder = OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)

    private fun debugLogger(debugLogging: Boolean): DebugHttpLoggerInterceptor =
        DebugHttpLoggerInterceptor(enabled = debugLogging) { line -> Log.d(LOG_TAG, line) }
}
