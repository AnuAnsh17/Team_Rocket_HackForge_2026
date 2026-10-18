package org.proofline.android.core.auth

/**
 * Every way a Supabase Auth call can fail, as a closed set.
 *
 * The distinction that matters: "the credentials are wrong" must never be
 * presented the same way as "we could not reach the server". A UI that says
 * "login failed" for a network timeout teaches the user their password is wrong.
 */
sealed class AuthError(message: String) : Exception(message) {

    /** The build has no Supabase project URL / anon key configured. */
    object NotConfigured : AuthError(
        "Supabase Auth is not configured in this build. Set SUPABASE_URL and SUPABASE_ANON_KEY."
    )

    /** GoTrue rejected the email/password pair. */
    object InvalidCredentials : AuthError("Incorrect email or password.")

    /** GoTrue accepted the credentials but the address is not confirmed. */
    object EmailNotConfirmed : AuthError(
        "This email address has not been confirmed yet. Confirm it and try again."
    )

    /** GoTrue is rate limiting this project or this address. */
    object RateLimited : AuthError("Too many attempts. Wait a moment and try again.")

    /** The device never reached GoTrue. */
    object Network : AuthError(
        "Could not reach the identity provider. Check the connection and try again."
    )

    /** A response arrived but was not the documented token document. */
    object MalformedResponse : AuthError(
        "The identity provider returned a response this app could not read."
    )

    /** Any other non-success status, with the provider's own code preserved. */
    class Server(
        val statusCode: Int,
        val errorCode: String?,
        message: String
    ) : AuthError(message)
}
