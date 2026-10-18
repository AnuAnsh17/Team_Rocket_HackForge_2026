package org.proofline.android.core.auth

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Owns the session lifecycle: sign in, renew, sign out.
 *
 * All public entry points are safe to call from a UI coroutine; the blocking
 * variants ([accessTokenForRequest]) exist because an OkHttp interceptor
 * runs on a network thread and must not suspend.
 *
 * A single lock makes refresh single-flight: two concurrent API calls that both
 * notice an expiring token produce one refresh, not two, so a rotation-based
 * refresh token cannot be consumed twice and invalidate the session.
 */
class SessionManager(
    private val store: SessionStore,
    private val authApi: SupabaseAuthApi,
    private val clock: () -> Long = { System.currentTimeMillis() / 1000L },
    private val refreshSkewSeconds: Long = SessionExpiry.DEFAULT_SKEW_SECONDS,
    private val onSessionChanged: (AuthSession?) -> Unit = {}
) {

    private val lock = Any()

    /** The stored session, or null when this device is signed out. */
    fun currentSession(): AuthSession? = synchronized(lock) { store.load() }

    /**
     * Whether the app should start signed in.
     *
     * A stored session counts as restorable if it has both tokens; an expired
     * access token is fine because it can be renewed. A session whose refresh
     * token is missing is not a session at all.
     */
    fun hasRestorableSession(): Boolean {
        val session = currentSession() ?: return false
        return session.refreshToken.isNotBlank() && session.accessToken.isNotBlank()
    }

    /**
     * Sign in and persist the resulting session.
     *
     * @throws AuthError when GoTrue refuses the credentials or cannot be reached.
     *         The previously stored session, if any, is left untouched.
     */
    fun signIn(email: String, password: String): AuthSession = synchronized(lock) {
        val session = authApi.signInWithPassword(email, password)
        store.save(session)
        onSessionChanged(session)
        session
    }

    /**
     * Sign out: revoke server-side (best effort) and destroy local state.
     *
     * Local state is cleared first and unconditionally, so a failed revocation
     * cannot leave a usable session on the device.
     */
    fun signOut() = synchronized(lock) {
        val session = store.load()
        store.clear()
        onSessionChanged(null)
        if (session != null) {
            authApi.signOut(session.accessToken)
        }
        Unit
    }

    /**
     * The token to put on the next backend request.
     *
     * Returns null when the device is signed out or when renewal failed - in
     * which case the caller must not send a request that pretends to be
     * authenticated.
     */
    fun accessTokenForRequest(): String? = synchronized(lock) {
        val session = store.load() ?: return null
        if (session.accessToken.isBlank() || session.refreshToken.isBlank()) {
            // A half-written session cannot be renewed and must not be used.
            store.clear()
            onSessionChanged(null)
            return null
        }
        if (!SessionExpiry.shouldRefresh(session.expiresAtEpochSeconds, clock(), refreshSkewSeconds)) {
            return session.accessToken
        }
        return try {
            val renewed = authApi.refresh(session.refreshToken)
            store.save(renewed)
            onSessionChanged(renewed)
            renewed.accessToken
        } catch (_: AuthError) {
            // A session that cannot be renewed is not a session. Clearing it here
            // is what stops a stale token being retried on every request.
            store.clear()
            onSessionChanged(null)
            null
        }
    }

    suspend fun signInAsync(email: String, password: String): AuthSession =
        withContext(Dispatchers.IO) { signIn(email, password) }

    suspend fun signOutAsync(): Unit = withContext(Dispatchers.IO) { signOut() }
}
