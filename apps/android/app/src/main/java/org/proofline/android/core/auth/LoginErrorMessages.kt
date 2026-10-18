package org.proofline.android.core.auth

/**
 * Turns an [AuthError] into the sentence the login screen shows.
 *
 * A pure function, deliberately: the mapping is the part that determines whether
 * an employee is told "your password is wrong" (which they can act on) or "we
 * could not reach the server" (which they can also act on, differently). Getting
 * it backwards trains people to abandon correct passwords.
 */
object LoginErrorMessages {

    const val GENERIC_FAILURE = "Sign-in failed. Nothing was sent to the backend; try again."

    fun messageFor(error: Throwable): String = when (error) {
        is AuthError.NotConfigured ->
            "This build has no Supabase project configured. Set SUPABASE_URL and " +
                "SUPABASE_ANON_KEY and rebuild (see apps/android/README.md)."
        is AuthError.InvalidCredentials -> "Incorrect email or password."
        is AuthError.EmailNotConfirmed ->
            "That email address has not been confirmed yet. Confirm it, then sign in."
        is AuthError.RateLimited -> "Too many attempts. Wait a moment and try again."
        is AuthError.Network ->
            "Could not reach the identity provider. Check the connection and try again."
        is AuthError.MalformedResponse ->
            "The identity provider answered in a form this app could not read. Nothing was signed in."
        is AuthError.Server ->
            "Sign-in was refused by the identity provider (HTTP ${error.statusCode})."
        else -> GENERIC_FAILURE
    }
}
