package org.proofline.android.core.auth

import kotlinx.serialization.SerializationException
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.proofline.android.core.network.ProoflineJson
import java.io.IOException

/**
 * Supabase Auth (GoTrue) REST client.
 *
 * Deliberately built on OkHttp and kotlinx-serialization rather than a Supabase
 * SDK: the endpoints used here are three documented REST calls, and adding an SDK
 * would mean a new dependency, a new lifecycle and a new transitive tree for no
 * capability this app needs.
 *
 * Every method is blocking. Callers on the UI path wrap them in
 * `Dispatchers.IO`; [SessionManager] calls them from the OkHttp interceptor
 * thread, where blocking is normal.
 *
 * Nothing in this class writes a token or a password anywhere. The only failure
 * detail that escapes is the provider's own error code and message.
 */
class SupabaseAuthApi(
    private val supabaseUrl: String,
    private val anonKey: String,
    private val client: OkHttpClient,
    private val clock: () -> Long = { System.currentTimeMillis() / 1000L },
    private val json: Json = ProoflineJson.instance
) {

    val isConfigured: Boolean
        get() = supabaseUrl.isNotBlank() && anonKey.isNotBlank() &&
            supabaseUrl.startsWith("http")

    private val authBase: String
        get() = "${supabaseUrl.trimEnd('/')}/auth/v1"

    /**
     * `POST /auth/v1/token?grant_type=password`.
     *
     * @throws AuthError on every failure path.
     */
    fun signInWithPassword(email: String, password: String): AuthSession {
        requireConfigured()
        val payload = json.encodeToString(SignInRequest(email = email, password = password))
        val request = baseRequest("$authBase/token?grant_type=password")
            .post(payload.toRequestBody(JSON_MEDIA_TYPE))
            .build()
        return execute(request).toSession(clock())
    }

    /**
     * `POST /auth/v1/token?grant_type=refresh_token`.
     *
     * @throws AuthError on every failure path.
     */
    fun refresh(refreshToken: String): AuthSession {
        requireConfigured()
        val payload = json.encodeToString(RefreshRequest(refreshToken = refreshToken))
        val request = baseRequest("$authBase/token?grant_type=refresh_token")
            .post(payload.toRequestBody(JSON_MEDIA_TYPE))
            .build()
        return execute(request).toSession(clock())
    }

    /**
     * Best-effort revocation of the session the access token belongs to.
     *
     * GoTrue invalidates the session row, which is what makes the refresh token
     * unusable. Failures are swallowed on purpose: local sign-out must not depend
     * on the network, and the alternative - keeping a usable session on the device
     * because a request failed - is worse. The caller clears local state either
     * way; see `AuthSessionSupport` notes in the README for the honest limit.
     */
    fun signOut(accessToken: String) {
        if (!isConfigured || accessToken.isBlank()) return
        val request = baseRequest("$authBase/logout")
            .header("Authorization", "Bearer $accessToken")
            .post(EMPTY_JSON.toRequestBody(JSON_MEDIA_TYPE))
            .build()
        try {
            client.newCall(request).execute().use { /* response body not read */ }
        } catch (_: IOException) {
            // Best effort only.
        }
    }

    private fun requireConfigured() {
        if (!isConfigured) throw AuthError.NotConfigured
    }

    private fun baseRequest(url: String): Request.Builder = Request.Builder()
        .url(url)
        .header("Accept", "application/json")
        .header("apikey", anonKey)
        .header("Content-Type", "application/json")

    private fun execute(request: Request): GoTrueTokenResponse {
        val response = try {
            client.newCall(request).execute()
        } catch (e: IOException) {
            throw AuthError.Network
        }
        response.use {
            val body = it.body?.string().orEmpty()
            if (!it.isSuccessful) {
                throw mapFailure(it.code, body)
            }
            return try {
                json.decodeFromString(GoTrueTokenResponse.serializer(), body)
            } catch (_: SerializationException) {
                throw AuthError.MalformedResponse
            } catch (_: IllegalArgumentException) {
                throw AuthError.MalformedResponse
            }
        }
    }

    private fun mapFailure(statusCode: Int, body: String): AuthError {
        val parsed = try {
            json.decodeFromString(GoTrueErrorResponse.serializer(), body)
        } catch (_: Exception) {
            null
        }
        val code = (parsed?.errorCode ?: parsed?.code ?: parsed?.error)?.lowercase()

        if (code != null && code.contains("email_not_confirmed")) {
            return AuthError.EmailNotConfirmed
        }
        if (statusCode == 429 || code == "over_email_send_rate_limit" ||
            code == "over_request_rate_limit"
        ) {
            return AuthError.RateLimited
        }
        if (statusCode == 400 || statusCode == 401 || statusCode == 403) {
            // GoTrue answers 400 with invalid_credentials for a bad password and
            // 401/403 for a bad or expired grant. All of them mean "not signed in".
            return AuthError.InvalidCredentials
        }
        val message = parsed?.bestMessage()
            ?: "The identity provider refused the request (HTTP $statusCode)."
        return AuthError.Server(statusCode = statusCode, errorCode = code, message = message)
    }

    @kotlinx.serialization.Serializable
    private data class SignInRequest(
        @kotlinx.serialization.SerialName("email") val email: String,
        @kotlinx.serialization.SerialName("password") val password: String
    )

    @kotlinx.serialization.Serializable
    private data class RefreshRequest(
        @kotlinx.serialization.SerialName("refresh_token") val refreshToken: String
    )

    private companion object {
        val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
        const val EMPTY_JSON = "{}"
    }
}
