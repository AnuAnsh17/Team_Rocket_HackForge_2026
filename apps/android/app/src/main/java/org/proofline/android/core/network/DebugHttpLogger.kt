package org.proofline.android.core.network

import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response

/**
 * Redaction rules for anything this app is allowed to write to a log.
 *
 * Logging is not a debugging convenience here, it is a disclosure surface: the
 * Authorization header carries a bearer token that is a live credential, the
 * `apikey` header carries the project's publishable key, and a request body on
 * the auth endpoints carries a password. None of those may reach logcat, a
 * crash reporter or a bug report.
 *
 * Bodies are never logged at all, for any endpoint, in any build: receipt bytes
 * and auth payloads both live in request bodies.
 */
object HttpLogRedactor {

    const val REDACTED = "<redacted>"

    private val SENSITIVE_HEADERS = setOf(
        "authorization",
        "proxy-authorization",
        "apikey",
        "x-api-key",
        "cookie",
        "set-cookie",
        "refresh_token",
        "x-demo-actor-id"
    )

    fun isSensitiveHeader(name: String): Boolean =
        SENSITIVE_HEADERS.contains(name.trim().lowercase())

    fun redactHeaderValue(name: String, value: String): String =
        if (isSensitiveHeader(name)) REDACTED else value

    /**
     * The request line plus redacted header names and values.
     *
     * The query string is dropped rather than logged: GoTrue endpoints carry
     * `grant_type` there today, and a future endpoint may carry a token.
     */
    fun describeRequest(request: Request): String = buildString {
        append("--> ")
        append(request.method)
        append(' ')
        append(request.url.newBuilder().query(null).fragment(null).build())
        request.headers.forEach { (name, value) ->
            append('\n')
            append("    ")
            append(name)
            append(": ")
            append(redactHeaderValue(name, value))
        }
    }

    fun describeResponse(response: Response): String = buildString {
        append("<-- ")
        append(response.code)
        append(' ')
        append(response.message)
        response.headers.forEach { (name, value) ->
            append('\n')
            append("    ")
            append(name)
            append(": ")
            append(redactHeaderValue(name, value))
        }
    }
}

/**
 * Debug-only HTTP logger.
 *
 * Two independent switches must both be on before a single line is emitted:
 * the build must be a debug build (the caller passes `BuildConfig.DEBUG`) and
 * the interceptor must have been constructed with `enabled = true`. In a release
 * build this interceptor is not even installed.
 */
class DebugHttpLoggerInterceptor(
    private val enabled: Boolean,
    private val logger: (String) -> Unit
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        if (!enabled) {
            return chain.proceed(chain.request())
        }
        val request = chain.request()
        logger(HttpLogRedactor.describeRequest(request))
        val response = chain.proceed(request)
        logger(HttpLogRedactor.describeResponse(response))
        return response
    }
}
