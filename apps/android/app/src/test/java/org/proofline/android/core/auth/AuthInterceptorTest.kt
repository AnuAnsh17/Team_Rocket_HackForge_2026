package org.proofline.android.core.auth

import okhttp3.Request
import okhttp3.Response
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.proofline.android.testing.RecordingChain
import org.proofline.android.testing.cannedClient
import org.proofline.android.testing.respond
import java.io.IOException

/**
 * Bearer-header attachment.
 *
 * This is the test that would have caught the original defect: the app had no
 * Authorization header at all and relied entirely on `X-Demo-Actor-Id`, which a
 * backend running `AUTH_PROVIDER=supabase` ignores.
 */
class AuthInterceptorTest {

    private val now = 1_700_000_000L
    private val backendUrl = "https://backend.example.test/api/v1/me"

    private fun session(expiresAt: Long = now + 3600) = AuthSession(
        accessToken = "access-1",
        refreshToken = "refresh-1",
        expiresAtEpochSeconds = expiresAt,
        userId = "supabase-user-1",
        email = "asha@example.test"
    )

    private fun manager(
        initial: AuthSession?,
        handler: (Request) -> Response = { request -> respond(request, 200, "{}") }
    ): SessionManager {
        val api = SupabaseAuthApi(
            supabaseUrl = "https://project.example.test",
            anonKey = "anon",
            client = cannedClient(handler),
            clock = { now }
        )
        return SessionManager(
            store = InMemorySessionStore(initial),
            authApi = api,
            clock = { now },
            refreshSkewSeconds = 60L
        )
    }

    private fun outgoingRequest(interceptor: AuthInterceptor): Request {
        val chain = RecordingChain(
            Request.Builder().url(backendUrl).header("Accept", "application/json").build()
        )
        interceptor.intercept(chain)
        return chain.proceeded ?: error("the chain was never invoked")
    }

    @Test
    fun aSignedInRequestCarriesTheBearerToken() {
        val interceptor = AuthInterceptor(manager(session()))

        val request = outgoingRequest(interceptor)

        assertEquals("Bearer access-1", request.header("Authorization"))
        assertNull(request.header("X-Demo-Actor-Id"))
    }

    @Test
    fun anExpiredTokenIsRenewedBeforeTheRequestGoesOut() {
        val interceptor = AuthInterceptor(
            manager(
                initial = session(expiresAt = now - 1),
                handler = { request ->
                    respond(
                        request,
                        200,
                        """{"access_token":"access-2","refresh_token":"refresh-2","expires_in":3600}"""
                    )
                }
            )
        )

        val request = outgoingRequest(interceptor)

        assertEquals("Bearer access-2", request.header("Authorization"))
    }

    @Test
    fun aFailedRenewalMeansNoClaimOfIdentity() {
        val interceptor = AuthInterceptor(
            manager(initial = session(expiresAt = now - 1), handler = { throw IOException("offline") })
        )

        val request = outgoingRequest(interceptor)

        assertNull(request.header("Authorization"))
        assertNull(request.header("X-Demo-Actor-Id"))
    }

    @Test
    fun aSignedOutRequestCarriesNoIdentityHeaderByDefault() {
        val interceptor = AuthInterceptor(manager(initial = null))

        val request = outgoingRequest(interceptor)

        assertNull(request.header("Authorization"))
        assertNull(request.header("X-Demo-Actor-Id"))
    }

    @Test
    fun theDemoFallbackIsOnlySentWhenItIsExplicitlyEnabled() {
        val enabled = AuthInterceptor(
            manager(initial = null),
            demoFallbackEnabled = true,
            demoActorId = "6dbc60b8-8577-56ec-806e-4201fa5993c4"
        )
        val disabled = AuthInterceptor(
            manager(initial = null),
            demoFallbackEnabled = false,
            demoActorId = "6dbc60b8-8577-56ec-806e-4201fa5993c4"
        )

        assertEquals("6dbc60b8-8577-56ec-806e-4201fa5993c4", outgoingRequest(enabled).header("X-Demo-Actor-Id"))
        assertNull(outgoingRequest(disabled).header("X-Demo-Actor-Id"))
    }

    @Test
    fun aRealSessionAlwaysWinsOverTheDemoFallback() {
        val interceptor = AuthInterceptor(
            manager(session()),
            demoFallbackEnabled = true,
            demoActorId = "6dbc60b8-8577-56ec-806e-4201fa5993c4"
        )

        val request = outgoingRequest(interceptor)

        assertEquals("Bearer access-1", request.header("Authorization"))
        assertNull("the demo header must not accompany a real session", request.header("X-Demo-Actor-Id"))
    }

    @Test
    fun noDemoHeaderIsSentWhenTheActorIdIsBlank() {
        val interceptor = AuthInterceptor(manager(null), demoFallbackEnabled = true, demoActorId = "")

        assertNull(outgoingRequest(interceptor).header("X-Demo-Actor-Id"))
    }

    @Test
    fun anUnrelatedHeaderSurvivesTheInterceptor() {
        val interceptor = AuthInterceptor(manager(session()))

        val request = outgoingRequest(interceptor)

        assertEquals("application/json", request.header("Accept"))
    }
}
