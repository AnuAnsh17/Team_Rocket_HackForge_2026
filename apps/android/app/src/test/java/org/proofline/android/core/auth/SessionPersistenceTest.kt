package org.proofline.android.core.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionPersistenceTest {

    private val session = AuthSession(
        accessToken = "access-1",
        refreshToken = "refresh-1",
        expiresAtEpochSeconds = 1_700_000_000L,
        userId = "user-1",
        email = "asha@example.test"
    )

    @Test
    fun roundTripsEveryField() {
        val decoded = SessionPersistence.decode(SessionPersistence.encode(session))
        assertEquals(session, decoded)
    }

    @Test
    fun missingAccessTokenIsNotASession() {
        val stored = SessionPersistence.encode(session).toMutableMap()
        stored.remove(SessionPersistence.KEY_ACCESS_TOKEN)
        assertNull(SessionPersistence.decode(stored))
    }

    @Test
    fun blankRefreshTokenIsNotASession() {
        val stored = SessionPersistence.encode(session).toMutableMap()
        stored[SessionPersistence.KEY_REFRESH_TOKEN] = "   "
        assertNull(SessionPersistence.decode(stored))
    }

    @Test
    fun unparseableExpiryIsNotASession() {
        val stored = SessionPersistence.encode(session).toMutableMap()
        stored[SessionPersistence.KEY_EXPIRES_AT] = "not-a-number"
        assertNull(SessionPersistence.decode(stored))
    }

    @Test
    fun absentOptionalFieldsDecodeAsNull() {
        val stored = SessionPersistence.encode(session.copy(userId = null, email = null))
        val decoded = SessionPersistence.decode(stored)
        assertEquals("access-1", decoded?.accessToken)
        assertNull(decoded?.userId)
        assertNull(decoded?.email)
    }

    @Test
    fun storeKeepsAndClearsTheSession() {
        val store = InMemorySessionStore()
        assertNull(store.load())

        store.save(session)
        assertEquals(session, store.load())

        store.clear()
        assertNull(store.load())
    }

    @Test
    fun toStringSaysWhetherTokensArePresentWithoutShowingThem() {
        val text = session.toString()
        assertFalse("access token must not appear in toString", text.contains("access-1"))
        assertFalse("refresh token must not appear in toString", text.contains("refresh-1"))
        assertTrue(text.contains("accessToken=present"))
        assertTrue(text.contains("refreshToken=present"))
    }
}
