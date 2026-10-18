package org.proofline.android.core.auth

import okhttp3.Interceptor
import okhttp3.Response

/**
 * Attaches the Supabase access token to every backend request.
 *
 * Two rules, both load-bearing:
 *
 *  1. A signed-in device always sends `Authorization: Bearer <access token>`,
 *     renewing first when the token is expired or close to expiry. The backend
 *     verifies the token and then loads membership and roles from its own
 *     database, so nothing about identity is asserted by this app.
 *  2. `X-Demo-Actor-Id` is a development fallback that is only ever sent when
 *     [demoFallbackEnabled] is true - which is wired to `BuildConfig.DEBUG` at
 *     construction - and only when there is no session token. With the backend
 *     running `AUTH_PROVIDER=supabase` the header is ignored, so it changes
 *     nothing there; it exists so a debug build can still talk to a local
 *     `AUTH_PROVIDER=demo` backend.
 */
class AuthInterceptor(
    private val sessionManager: SessionManager,
    private val demoFallbackEnabled: Boolean = false,
    private val demoActorId: String = ""
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val token = sessionManager.accessTokenForRequest()
        val builder = request.newBuilder()

        if (token != null) {
            builder.header(HEADER_AUTHORIZATION, "Bearer $token")
        } else if (demoFallbackEnabled && demoActorId.isNotBlank()) {
            builder.header(HEADER_DEMO_ACTOR, demoActorId)
        }

        return chain.proceed(builder.build())
    }

    companion object {
        const val HEADER_AUTHORIZATION = "Authorization"
        const val HEADER_DEMO_ACTOR = "X-Demo-Actor-Id"
    }
}
