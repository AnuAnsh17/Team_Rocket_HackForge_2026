package org.proofline.android.core.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.proofline.android.testing.RecordingChain

/**
 * "No token reaches a log" is a property this app asserts, not a habit.
 *
 * The logging interceptor is configured so it sees the request *after* the auth
 * interceptor has added the bearer token, which means redaction here is the only
 * thing standing between a live credential and logcat.
 */
class HttpLogRedactionTest {

    private val accessToken = "super-secret-access-token"
    private val anonKey = "publishable-anon-key"
    private val demoActorId = "6dbc60b8-8577-56ec-806e-4201fa5993c4"

    private fun loggedLines(request: Request, enabled: Boolean = true): String {
        val lines = mutableListOf<String>()
        val interceptor = DebugHttpLoggerInterceptor(enabled = enabled) { lines.add(it) }
        interceptor.intercept(RecordingChain(request))
        return lines.joinToString("\n")
    }

    private fun backendRequest(): Request = Request.Builder()
        .url("https://backend.example.test/api/v1/expenses?cursor=opaque-cursor-value")
        .header("Authorization", "Bearer $accessToken")
        .header("X-Request-ID", "request-id-1")
        .header("Accept", "application/json")
        .build()

    @Test
    fun theBearerTokenNeverAppears() {
        val log = loggedLines(backendRequest())

        assertFalse("the access token must never be logged", log.contains(accessToken))
        assertTrue("the header must still be visible, redacted", log.contains("<redacted>"))
        assertTrue(log.contains("Authorization"))
    }

    @Test
    fun theApiKeyAndDemoActorHeaderNeverAppear() {
        val request = Request.Builder()
            .url("https://project.example.test/auth/v1/token?grant_type=password")
            .header("apikey", anonKey)
            .header("X-Demo-Actor-Id", demoActorId)
            .build()

        val log = loggedLines(request)

        assertFalse(log.contains(anonKey))
        assertFalse(log.contains(demoActorId))
    }

    @Test
    fun theQueryStringIsNotLogged() {
        val log = loggedLines(backendRequest())

        assertFalse("a query string is a place a token can hide", log.contains("opaque-cursor-value"))
        assertTrue(log.contains("https://backend.example.test/api/v1/expenses"))
    }

    @Test
    fun requestBodiesAreNeverLoggedAtAll() {
        val request = Request.Builder()
            .url("https://project.example.test/auth/v1/token?grant_type=password")
            .post("""{"email":"asha@example.test","password":"hunter2-should-never-be-logged"}"""
                .toRequestBody("application/json".toMediaType()))
            .build()

        val log = loggedLines(request)

        assertFalse(log.contains("hunter2-should-never-be-logged"))
        assertFalse(log.contains("asha@example.test"))
    }

    @Test
    fun aDisabledLoggerEmitsNothingAtAll() {
        val log = loggedLines(backendRequest(), enabled = false)

        assertEquals("", log)
    }

    @Test
    fun theResponseLineIsLoggedWithItsStatus() {
        val log = loggedLines(backendRequest())

        assertTrue(log.contains("<-- 200"))
    }

    @Test
    fun theRedactorTreatsEveryCredentialHeaderCaseInsensitively() {
        assertEquals("<redacted>", HttpLogRedactor.redactHeaderValue("authorization", accessToken))
        assertEquals("<redacted>", HttpLogRedactor.redactHeaderValue("AUTHORIZATION", accessToken))
        assertEquals("<redacted>", HttpLogRedactor.redactHeaderValue("Authorization", accessToken))
        assertEquals("<redacted>", HttpLogRedactor.redactHeaderValue("apikey", anonKey))
        assertEquals("<redacted>", HttpLogRedactor.redactHeaderValue("Set-Cookie", "session=abc"))
        assertEquals("application/json", HttpLogRedactor.redactHeaderValue("Accept", "application/json"))
    }
}
