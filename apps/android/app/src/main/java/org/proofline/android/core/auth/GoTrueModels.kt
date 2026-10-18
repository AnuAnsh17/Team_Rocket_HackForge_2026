package org.proofline.android.core.auth

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Wire documents for Supabase Auth (GoTrue).
 *
 * Field names come from the documented REST responses; everything this client
 * does not model is ignored rather than rejected.
 */
@Serializable
data class GoTrueUser(
    @SerialName("id") val id: String = "",
    @SerialName("email") val email: String? = null
)

@Serializable
data class GoTrueTokenResponse(
    @SerialName("access_token") val accessToken: String = "",
    @SerialName("refresh_token") val refreshToken: String = "",
    @SerialName("expires_in") val expiresIn: Long = 0L,
    @SerialName("expires_at") val expiresAt: Long? = null,
    @SerialName("token_type") val tokenType: String? = null,
    @SerialName("user") val user: GoTrueUser? = null
) {
    /**
     * Convert to a storable session.
     *
     * `expires_at` is preferred when the provider supplies it because it is an
     * absolute instant. Otherwise the relative `expires_in` is applied to the
     * caller's clock. A token document without tokens is not a session.
     */
    fun toSession(nowEpochSeconds: Long): AuthSession {
        if (accessToken.isBlank() || refreshToken.isBlank()) {
            throw AuthError.MalformedResponse
        }
        val absoluteExpiry = expiresAt
            ?: (nowEpochSeconds + expiresIn.coerceAtLeast(0L))
        return AuthSession(
            accessToken = accessToken,
            refreshToken = refreshToken,
            expiresAtEpochSeconds = absoluteExpiry,
            userId = user?.id?.takeIf { it.isNotBlank() },
            email = user?.email?.takeIf { it.isNotBlank() }
        )
    }
}

@Serializable
data class GoTrueErrorResponse(
    @SerialName("error_code") val errorCode: String? = null,
    @SerialName("error") val error: String? = null,
    @SerialName("error_description") val errorDescription: String? = null,
    @SerialName("msg") val msg: String? = null,
    @SerialName("message") val message: String? = null,
    @SerialName("code") val code: String? = null
) {
    fun bestMessage(): String? =
        listOf(msg, errorDescription, message, error, code).firstOrNull { !it.isNullOrBlank() }
}
