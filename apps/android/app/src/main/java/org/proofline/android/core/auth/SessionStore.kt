package org.proofline.android.core.auth

import android.content.Context

/**
 * Persistence boundary for the auth session.
 *
 * The interface exists so the session lifecycle (sign in, refresh, sign out) can
 * be tested on the JVM against an in-memory implementation rather than only on a
 * device.
 */
interface SessionStore {
    fun load(): AuthSession?
    fun save(session: AuthSession)
    fun clear()
}

/** Test double; also the fallback store when no Android context is available. */
class InMemorySessionStore(initial: AuthSession? = null) : SessionStore {
    private var session: AuthSession? = initial

    override fun load(): AuthSession? = session

    override fun save(session: AuthSession) {
        this.session = session
    }

    override fun clear() {
        session = null
    }
}

/**
 * App-private storage for the session.
 *
 * `MODE_PRIVATE` means the file is readable only by this app's uid on a normal
 * device. It is deliberately **not** described as encrypted: the values are
 * held in a plain XML preferences file, so a rooted device or a device-level
 * backup can read them. `res/xml/backup_rules.xml` and
 * `res/xml/data_extraction_rules.xml` exclude shared preferences from cloud
 * backup and device transfer, so the tokens are not copied off the device.
 */
class SharedPreferencesSessionStore(context: Context) : SessionStore {

    private val prefs = context.applicationContext
        .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    override fun load(): AuthSession? = SessionPersistence.decode(
        prefs.all.mapValues { (_, value) -> value as? String }
    )

    override fun save(session: AuthSession) {
        val editor = prefs.edit()
        SessionPersistence.encode(session).forEach { (key, value) -> editor.putString(key, value) }
        editor.commit()
    }

    override fun clear() {
        prefs.edit().clear().commit()
    }

    companion object {
        const val PREFS_NAME = "proofline_auth"
    }
}
