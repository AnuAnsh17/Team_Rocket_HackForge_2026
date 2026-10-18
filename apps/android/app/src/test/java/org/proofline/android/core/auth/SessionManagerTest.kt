package org.proofline.android.core.auth

import okhttp3.Request
import okhttp3.Response
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.proofline.android.testing.cannedClient
import org.proofline.android.testing.respond
import java.io.IOException

/**
 * The session lifecycle: sign in, renew, sign out.
 *
 * The Supabase client underneath is a real [SupabaseAuthApi] talking to a
 * synthesised HTTP layer, so a refresh here exercises the same code an interceptor
 * would run on a device.
 */
class SessionManagerTest {

    private val now = 1_700_000_000L

    private fun session(
        access: String = "access-1",
        refresh: String = "refresh-1",
        expiresAt: Long = now + 3600
    ) = AuthSession(
        accessToken = access,
        refreshToken = refresh,
        expiresAtEpochSeconds = expiresAt,
        userId = "supabase-user-1",
        email = "asha@example.test"
    )

    private fun tokenBody(access: String, refresh: String): String = """
        {"access_token":"$access","refresh_token":"$refresh","expires_in":3600,
         "user":{"id":"supabase-user-1","email":"asha@example.test"}}
    """.trimIndent()

    private class Harness(
        val store: InMemorySessionStore,
        val manager: SessionManager
    )

    private fun harness(
        handler: (Request) -> Response,
        initial: AuthSession? = null,
        onSessionChanged: (AuthSession?) -> Unit = {}
    ): Harness {
        val store = InMemorySessionStore(initial)
        val api = SupabaseAuthApi(
            supabaseUrl = "https://project.example.test",
            anonKey = "anon",
            client = cannedClient(handler),
            clock = { now }
        )
        val manager = SessionManager(
            store = store,
            authApi = api,
            clock = { now },
            refreshSkewSeconds = 60L,
            onSessionChanged = onSessionChanged
        )
        return Harness(store, manager)
    }

    @Test
    fun aSignedOutDeviceHasNoSessionAndNoToken() {
        val harness = harness({ throw AssertionError("no request may be made while signed out") })

        assertFalse(harness.manager.hasRestorableSession())
        assertNull(harness.manager.currentSession())
        assertNull(harness.manager.accessTokenForRequest())
    }

    @Test
    fun signInPersistsTheSessionAndReportsIt() {
        val seen = mutableListOf<AuthSession?>()
        val harness = harness(
            handler = { request -> respond(request, 200, tokenBody("access-1", "refresh-1")) },
            onSessionChanged = { seen.add(it) }
        )

        val session = harness.manager.signIn("asha@example.test", "correct-horse")

        assertEquals("access-1", session.accessToken)
        assertEquals(session, harness.store.load())
        assertTrue(harness.manager.hasRestorableSession())
        assertEquals(listOf<AuthSession?>(session), seen)
    }

    @Test
    fun aFreshTokenIsUsedWithoutTouchingTheNetwork() {
        val harness = harness(
            handler = { throw AssertionError("a fresh token must not trigger a refresh") },
            initial = session(expiresAt = now + 600)
        )

        assertEquals("access-1", harness.manager.accessTokenForRequest())
    }

    @Test
    fun aTokenInsideTheSkewWindowIsRenewedAndTheRenewalIsPersisted() {
        var refreshCalls = 0
        val harness = harness(
            handler = { request ->
                assertTrue(request.url.toString().contains("grant_type=refresh_token"))
                refreshCalls++
                respond(request, 200, tokenBody("access-2", "refresh-2"))
            },
            initial = session(expiresAt = now + 10)
        )

        assertEquals("access-2", harness.manager.accessTokenForRequest())
        assertEquals(1, refreshCalls)
        assertEquals("access-2", harness.store.load()?.accessToken)
        assertEquals("refresh-2", harness.store.load()?.refreshToken)
    }

    @Test
    fun anExpiredTokenIsRenewed() {
        val harness = harness(
            handler = { request -> respond(request, 200, tokenBody("access-9", "refresh-9")) },
            initial = session(expiresAt = now - 5)
        )

        assertEquals("access-9", harness.manager.accessTokenForRequest())
    }

    @Test
    fun aFailedRenewalClearsTheSessionInsteadOfRetryingForever() {
        val seen = mutableListOf<AuthSession?>()
        val harness = harness(
            handler = { throw IOException("offline") },
            initial = session(expiresAt = now - 1),
            onSessionChanged = { seen.add(it) }
        )

        assertNull(harness.manager.accessTokenForRequest())
        assertNull(harness.store.load())
        assertFalse(harness.manager.hasRestorableSession())
        assertEquals(listOf<AuthSession?>(null), seen)
    }

    @Test
    fun renewingIsSingleFlightSoARotatedRefreshTokenIsNotConsumedTwice() {
        var refreshCalls = 0
        val harness = harness(
            handler = { request ->
                refreshCalls++
                respond(request, 200, tokenBody("access-2", "refresh-2"))
            },
            initial = session(expiresAt = now - 1)
        )

        val threads = (1..8).map {
            Thread { harness.manager.accessTokenForRequest() }
        }
        threads.forEach { it.start() }
        threads.forEach { it.join() }

        assertEquals("one refresh for eight concurrent callers", 1, refreshCalls)
        assertEquals("access-2", harness.store.load()?.accessToken)
    }

    @Test
    fun signOutRevokesTheSessionAndDestroysLocalState() {
        var logoutRequest: Request? = null
        val seen = mutableListOf<AuthSession?>()
        val harness = harness(
            handler = { request ->
                if (request.url.encodedPath.endsWith("/logout")) {
                    logoutRequest = request
                }
                respond(request, 200, "{}")
            },
            initial = session(expiresAt = now + 600),
            onSessionChanged = { seen.add(it) }
        )

        harness.manager.signOut()

        assertNotNull("the session must be revoked server-side", logoutRequest)
        assertEquals("Bearer access-1", logoutRequest!!.header("Authorization"))
        assertNull("local state must be gone", harness.store.load())
        assertFalse(harness.manager.hasRestorableSession())
        assertEquals(listOf<AuthSession?>(null), seen)
    }

    @Test
    fun signOutClearsLocalStateEvenWhenRevocationFails() {
        val harness = harness(
            handler = { request ->
                if (request.url.encodedPath.endsWith("/logout")) throw IOException("offline")
                respond(request, 200, "{}")
            },
            initial = session(expiresAt = now + 600)
        )

        harness.manager.signOut()

        assertNull(harness.store.load())
    }

    @Test
    fun signOutOnASignedOutDeviceIsHarmless() {
        val harness = harness({ request -> respond(request, 200, "{}") })

        harness.manager.signOut()

        assertNull(harness.store.load())
    }

    @Test
    fun aStoredSessionWithoutBothTokensIsNotRestorable() {
        val harness = harness(
            handler = { request -> respond(request, 200, tokenBody("a", "r")) },
            initial = session(access = "", refresh = "")
        )

        // An empty access token cannot be decoded from storage at all.
        assertFalse(harness.manager.hasRestorableSession())
    }

    @Test
    fun signInFailureLeavesAnExistingSessionAlone() {
        val existing = session(expiresAt = now + 600)
        val harness = harness(
            handler = { request -> respond(request, 400, """{"error_code":"invalid_credentials"}""") },
            initial = existing
        )

        try {
            harness.manager.signIn("asha@example.test", "wrong")
            fail("expected the sign-in to fail")
        } catch (error: AuthError) {
            assertSame(AuthError.InvalidCredentials, error)
        }

        assertEquals(existing, harness.store.load())
    }
}
