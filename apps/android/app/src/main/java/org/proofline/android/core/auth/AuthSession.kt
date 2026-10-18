package org.proofline.android.core.auth

/**
 * A persisted Supabase Auth session.
 *
 * The refresh token is the durable credential: the access token is short-lived
 * and is expected to be renewed. [expiresAtEpochSeconds] is stored explicitly
 * rather than derived, so a wall-clock change or a process restart cannot make
 * an expired token look fresh.
 */
data class AuthSession(
    val accessToken: String,
    val refreshToken: String,
    val expiresAtEpochSeconds: Long,
    val userId: String? = null,
    val email: String? = null
) {
    /** Never include the tokens in a toString/log line. */
    override fun toString(): String =
        "AuthSession(userId=$userId, email=$email, expiresAtEpochSeconds=$expiresAtEpochSeconds, " +
            "accessToken=${if (accessToken.isEmpty()) "<empty>" else "present"}, " +
            "refreshToken=${if (refreshToken.isEmpty()) "<empty>" else "present"})"
}

/**
 * The refresh decision, kept as a pure function so it can be tested without a
 * device, a clock or a network.
 */
object SessionExpiry {

    /**
     * Refresh this many seconds before actual expiry. A token that is still valid
     * for 30 seconds when the request leaves the device is not a valid token by
     * the time it arrives.
     */
    const val DEFAULT_SKEW_SECONDS: Long = 60L

    fun shouldRefresh(
        expiresAtEpochSeconds: Long,
        nowEpochSeconds: Long,
        skewSeconds: Long = DEFAULT_SKEW_SECONDS
    ): Boolean = expiresAtEpochSeconds - skewSeconds <= nowEpochSeconds

    fun isExpired(expiresAtEpochSeconds: Long, nowEpochSeconds: Long): Boolean =
        shouldRefresh(expiresAtEpochSeconds, nowEpochSeconds, skewSeconds = 0L)
}

/**
 * Serialisation of a session to and from flat string key/value pairs.
 *
 * Kept separate from any Android storage API so the round trip, including the
 * "torn write produces no session" case, is unit-testable on the JVM.
 */
object SessionPersistence {

    const val KEY_ACCESS_TOKEN = "auth.access_token"
    const val KEY_REFRESH_TOKEN = "auth.refresh_token"
    const val KEY_EXPIRES_AT = "auth.expires_at"
    const val KEY_USER_ID = "auth.user_id"
    const val KEY_EMAIL = "auth.email"

    fun encode(session: AuthSession): Map<String, String> = mapOf(
        KEY_ACCESS_TOKEN to session.accessToken,
        KEY_REFRESH_TOKEN to session.refreshToken,
        KEY_EXPIRES_AT to session.expiresAtEpochSeconds.toString(),
        KEY_USER_ID to session.userId.orEmpty(),
        KEY_EMAIL to session.email.orEmpty()
    )

    /**
     * Decode stored values, returning `null` when the stored state is not a
     * usable session. A partially written or tampered store must read as "signed
     * out", never as a half-session that later fails an API call.
     */
    fun decode(values: Map<String, String?>): AuthSession? {
        val accessToken = values[KEY_ACCESS_TOKEN]?.takeIf { it.isNotBlank() } ?: return null
        val refreshToken = values[KEY_REFRESH_TOKEN]?.takeIf { it.isNotBlank() } ?: return null
        val expiresAt = values[KEY_EXPIRES_AT]?.toLongOrNull() ?: return null
        return AuthSession(
            accessToken = accessToken,
            refreshToken = refreshToken,
            expiresAtEpochSeconds = expiresAt,
            userId = values[KEY_USER_ID]?.takeIf { it.isNotBlank() },
            email = values[KEY_EMAIL]?.takeIf { it.isNotBlank() }
        )
    }
}
