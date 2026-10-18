package org.proofline.android.core.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The refresh decision is the difference between a request that works and a
 * request that is rejected as unauthenticated, so the boundaries are pinned here.
 */
class SessionExpiryTest {

    private val expiresAt = 1_700_000_000L
    private val skew = 60L

    @Test
    fun freshTokenIsNotRefreshed() {
        assertFalse(SessionExpiry.shouldRefresh(expiresAt, expiresAt - 600, skew))
    }

    @Test
    fun tokenInsideTheSkewWindowIsRefreshed() {
        assertTrue(SessionExpiry.shouldRefresh(expiresAt, expiresAt - skew + 1, skew))
    }

    @Test
    fun tokenExactlyAtTheSkewBoundaryIsRefreshed() {
        assertTrue(SessionExpiry.shouldRefresh(expiresAt, expiresAt - skew, skew))
    }

    @Test
    fun expiredTokenIsRefreshed() {
        assertTrue(SessionExpiry.shouldRefresh(expiresAt, expiresAt + 1, skew))
    }

    @Test
    fun isExpiredIgnoresTheSkew() {
        assertFalse(SessionExpiry.isExpired(expiresAt, expiresAt - 1))
        assertTrue(SessionExpiry.isExpired(expiresAt, expiresAt))
    }

    @Test
    fun defaultSkewIsSixtySeconds() {
        assertEquals(60L, SessionExpiry.DEFAULT_SKEW_SECONDS)
    }
}
