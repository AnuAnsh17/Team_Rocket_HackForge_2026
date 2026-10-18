package org.proofline.android.testing

import okhttp3.Call
import okhttp3.Connection
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Test doubles for OkHttp.
 *
 * These exist so the interceptors, the auth client and the session manager can be
 * exercised as real objects on the JVM: a response is synthesised in front of the
 * network, so no device, emulator, DNS or socket is involved.
 */

/** An [Interceptor.Chain] that records the request it is asked to execute. */
class RecordingChain(
    private val request: Request,
    private val responder: (Request) -> Response = { respond(it, 200, "{}") }
) : Interceptor.Chain {

    /** The request that reached the far end of the chain. */
    var proceeded: Request? = null
        private set

    override fun request(): Request = request

    override fun proceed(request: Request): Response {
        proceeded = request
        return responder(request)
    }

    override fun connection(): Connection? = null

    override fun call(): Call = throw UnsupportedOperationException("no call in a unit test")

    override fun connectTimeoutMillis(): Int = 0

    override fun withConnectTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this

    override fun readTimeoutMillis(): Int = 0

    override fun withReadTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this

    override fun writeTimeoutMillis(): Int = 0

    override fun withWriteTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this
}

/** Build a response for [request] without touching the network. */
fun respond(
    request: Request,
    code: Int,
    body: String,
    contentType: String = "application/json; charset=utf-8"
): Response = Response.Builder()
    .request(request)
    .protocol(Protocol.HTTP_1_1)
    .code(code)
    .message(if (code in 200..299) "OK" else "Error")
    .body(body.toResponseBody(contentType.toMediaType()))
    .build()

/** An OkHttp client whose only interceptor synthesises a response or throws. */
fun cannedClient(handler: (Request) -> Response): OkHttpClient =
    OkHttpClient.Builder()
        .addInterceptor { chain -> handler(chain.request()) }
        .build()

/** A client that always fails the way an unreachable host does. */
fun offlineClient(): OkHttpClient = cannedClient { throw IOException("offline (test double)") }

/** Read a request body as text, without consuming anything the app needs. */
fun Request.bodyText(): String {
    val body = body ?: return ""
    val buffer = okio.Buffer()
    body.writeTo(buffer)
    return buffer.readUtf8()
}
