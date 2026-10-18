package org.proofline.android.core.auth

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.proofline.android.testing.bodyText
import org.proofline.android.testing.cannedClient
import org.proofline.android.testing.respond
import java.io.IOException

/**
 * The GoTrue REST calls, exercised against a synthesised HTTP layer.
 *
 * These tests prove how this client *classifies* each failure. They do not prove
 * that a live Supabase project returns these documents - that needs a real
 * project and is called out in apps/android/README.md.
 */
class SupabaseAuthApiTest {

    private val projectUrl = "https://project.example.test"
    private val anonKey = "publishable-anon-key"
    private val now = 1_700_000_000L

    private fun apiWith(handler: (Request) -> Response): SupabaseAuthApi = SupabaseAuthApi(
        supabaseUrl = projectUrl,
        anonKey = anonKey,
        client = cannedClient(handler),
        clock = { now }
    )

    private fun tokenBody(
        access: String = "access-1",
        refresh: String = "refresh-1"
    ): String = """
        {
          "access_token": "$access",
          "token_type": "bearer",
          "expires_in": 3600,
          "refresh_token": "$refresh",
          "user": { "id": "supabase-user-1", "email": "asha@example.test" }
        }
    """.trimIndent()

    private fun expectAuthError(block: () -> Unit): AuthError {
        try {
            block()
        } catch (error: AuthError) {
            return error
        }
        fail("expected an AuthError")
        throw IllegalStateException("unreachable")
    }

    // --- success paths -----------------------------------------------------

    @Test
    fun signInReturnsASessionBuiltFromTheTokenDocument() {
        val api = apiWith { request -> respond(request, 200, tokenBody()) }

        val session = api.signInWithPassword("asha@example.test", "correct-horse")

        assertEquals("access-1", session.accessToken)
        assertEquals("refresh-1", session.refreshToken)
        assertEquals("supabase-user-1", session.userId)
        assertEquals("asha@example.test", session.email)
        assertEquals(now + 3600, session.expiresAtEpochSeconds)
    }

    @Test
    fun signInPostsThePasswordGrantToTheProjectsAuthEndpoint() {
        var seen: Request? = null
        val api = apiWith { request ->
            seen = request
            respond(request, 200, tokenBody())
        }

        api.signInWithPassword("asha@example.test", "correct-horse")

        val request = seen!!
        assertEquals("POST", request.method)
        assertEquals(
            "https://project.example.test/auth/v1/token?grant_type=password",
            request.url.toString()
        )
        assertEquals(anonKey, request.header("apikey"))
        val body = request.bodyText()
        assertTrue(body.contains("\"email\":\"asha@example.test\""))
        assertTrue(body.contains("\"password\":\"correct-horse\""))
    }

    @Test
    fun absoluteExpiresAtWinsOverRelativeExpiresIn() {
        val document = GoTrueTokenResponse(
            accessToken = "a",
            refreshToken = "r",
            expiresIn = 3600,
            expiresAt = now + 99
        )

        assertEquals(now + 99, document.toSession(now).expiresAtEpochSeconds)
    }

    @Test
    fun refreshPostsTheRefreshTokenGrant() {
        var seen: Request? = null
        val api = apiWith { request ->
            seen = request
            respond(request, 200, tokenBody(access = "access-2", refresh = "refresh-2"))
        }

        val session = api.refresh("refresh-1")

        assertEquals("access-2", session.accessToken)
        assertEquals(
            "https://project.example.test/auth/v1/token?grant_type=refresh_token",
            seen!!.url.toString()
        )
        assertTrue(seen!!.bodyText().contains("\"refresh_token\":\"refresh-1\""))
    }

    @Test
    fun signOutSendsTheAccessTokenAsABearerToLogout() {
        var seen: Request? = null
        val api = apiWith { request ->
            seen = request
            respond(request, 200, "{}")
        }

        api.signOut("access-1")

        assertEquals("https://project.example.test/auth/v1/logout", seen!!.url.toString())
        assertEquals("Bearer access-1", seen!!.header("Authorization"))
        assertEquals(anonKey, seen!!.header("apikey"))
    }

    @Test
    fun signOutSwallowsAFailedRevocation() {
        val api = apiWith { throw IOException("offline") }

        // Must not throw: local sign-out cannot depend on the network.
        api.signOut("access-1")
    }

    // --- failure classification -------------------------------------------

    @Test
    fun wrongCredentialsBecomeInvalidCredentials() {
        val api = apiWith { request ->
            respond(
                request,
                400,
                """{"error_code":"invalid_credentials","msg":"Invalid login credentials"}"""
            )
        }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "wrong") }

        assertSame(AuthError.InvalidCredentials, error)
    }

    @Test
    fun anExpiredRefreshTokenIsAlsoInvalidCredentials() {
        val api = apiWith { request ->
            respond(
                request,
                400,
                """{"error_code":"refresh_token_not_found","msg":"Invalid Refresh Token"}"""
            )
        }

        val error = expectAuthError { api.refresh("stale") }

        assertSame(AuthError.InvalidCredentials, error)
    }

    @Test
    fun anUnconfirmedAddressIsReportedAsSuch() {
        val api = apiWith { request ->
            respond(request, 400, """{"error_code":"email_not_confirmed","msg":"Email not confirmed"}""")
        }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.EmailNotConfirmed, error)
    }

    @Test
    fun rateLimitingIsReportedAsSuch() {
        val api = apiWith { request ->
            respond(request, 429, """{"error_code":"over_request_rate_limit","msg":"Too many"}""")
        }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.RateLimited, error)
    }

    @Test
    fun aNetworkFailureBecomesNetwork() {
        val api = apiWith { throw IOException("no route to host") }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.Network, error)
    }

    @Test
    fun aSuccessfulButUnreadableBodyBecomesMalformedResponse() {
        val api = apiWith { request -> respond(request, 200, "<html>gateway</html>") }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.MalformedResponse, error)
    }

    @Test
    fun aTokenDocumentWithoutATokenIsMalformed() {
        val api = apiWith { request -> respond(request, 200, """{"token_type":"bearer"}""") }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.MalformedResponse, error)
    }

    @Test
    fun aServerErrorKeepsTheProviderCodeAndStatus() {
        val api = apiWith { request ->
            respond(request, 503, """{"error_code":"unavailable","msg":"try later"}""")
        }

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertTrue(error is AuthError.Server)
        val server = error as AuthError.Server
        assertEquals(503, server.statusCode)
        assertEquals("unavailable", server.errorCode)
        assertEquals("try later", server.message)
    }

    @Test
    fun anUnconfiguredBuildRefusesBeforeAnyRequest() {
        val api = SupabaseAuthApi(supabaseUrl = "", anonKey = "", client = OkHttpClient())

        val error = expectAuthError { api.signInWithPassword("asha@example.test", "correct-horse") }

        assertSame(AuthError.NotConfigured, error)
    }
}
