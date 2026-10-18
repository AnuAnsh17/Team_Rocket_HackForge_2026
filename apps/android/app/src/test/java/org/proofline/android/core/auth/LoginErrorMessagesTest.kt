package org.proofline.android.core.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The login screen's error copy.
 *
 * The distinction being protected: "wrong password" and "cannot reach the
 * server" must not read the same, because the two call for different actions.
 */
class LoginErrorMessagesTest {

    @Test
    fun wrongCredentialsSaySo() {
        val message = LoginErrorMessages.messageFor(AuthError.InvalidCredentials)

        assertEquals("Incorrect email or password.", message)
    }

    @Test
    fun aNetworkFailureIsNotBlamedOnTheCredentials() {
        val message = LoginErrorMessages.messageFor(AuthError.Network)

        assertTrue(message.contains("reach"))
        assertFalse(message.contains("password", ignoreCase = true))
        assertFalse(message.contains("incorrect", ignoreCase = true))
    }

    @Test
    fun aMalformedResponseIsReportedAsAnAppLimitNotAsABadPassword() {
        val message = LoginErrorMessages.messageFor(AuthError.MalformedResponse)

        assertTrue(message.contains("could not read"))
        assertFalse(message.contains("password", ignoreCase = true))
        assertFalse(message.contains("Incorrect", ignoreCase = true))
    }

    @Test
    fun anUnconfiguredBuildTellsTheDeveloperWhatToSet() {
        val message = LoginErrorMessages.messageFor(AuthError.NotConfigured)

        assertTrue(message.contains("SUPABASE_URL"))
        assertTrue(message.contains("SUPABASE_ANON_KEY"))
    }

    @Test
    fun anUnconfirmedAddressIsItsOwnMessage() {
        val message = LoginErrorMessages.messageFor(AuthError.EmailNotConfirmed)

        assertTrue(message.contains("confirmed"))
        assertFalse(message.contains("Incorrect", ignoreCase = true))
    }

    @Test
    fun rateLimitingIsItsOwnMessage() {
        assertTrue(LoginErrorMessages.messageFor(AuthError.RateLimited).contains("Too many"))
    }

    @Test
    fun aServerErrorNamesTheStatus() {
        val message = LoginErrorMessages.messageFor(
            AuthError.Server(statusCode = 503, errorCode = "unavailable", message = "try later")
        )

        assertTrue(message.contains("503"))
    }

    @Test
    fun anUnexpectedThrowableDoesNotLeakItsOwnText() {
        val message = LoginErrorMessages.messageFor(IllegalStateException("internal detail"))

        assertEquals(LoginErrorMessages.GENERIC_FAILURE, message)
        assertFalse(message.contains("internal detail"))
    }

    @Test
    fun noMessageEverClaimsSuccessOrContainsATokenShapedValue() {
        val allErrors = listOf(
            AuthError.NotConfigured,
            AuthError.InvalidCredentials,
            AuthError.EmailNotConfirmed,
            AuthError.RateLimited,
            AuthError.Network,
            AuthError.MalformedResponse,
            AuthError.Server(500, "unexpected", "boom")
        )

        allErrors.forEach { error ->
            val message = LoginErrorMessages.messageFor(error)
            assertTrue("message must not be blank for $error", message.isNotBlank())
            assertFalse("no failure copy may claim the user is signed in", message.contains("you are signed in", ignoreCase = true))
            assertFalse("no failure copy may contain a token", message.contains("eyJ"))
        }
    }
}
