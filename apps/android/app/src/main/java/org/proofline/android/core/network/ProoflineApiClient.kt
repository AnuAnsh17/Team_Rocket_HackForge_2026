package org.proofline.android.core.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.logging.HttpLoggingInterceptor
import org.proofline.android.BuildConfig
import org.proofline.android.core.model.ApiErrorEnvelope
import org.proofline.android.core.model.CreateExpenseRequest
import org.proofline.android.core.model.Expense
import org.proofline.android.core.model.ExpenseListResponse
import org.proofline.android.core.model.PolicyCheckResponse
import org.proofline.android.core.model.ReceiptSummary
import org.proofline.android.core.model.UpdateExpenseRequest
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit

class ProoflineApiException(
    val statusCode: Int,
    val errorCode: String,
    val errorMessage: String,
    val requestId: String? = null,
    val details: List<String> = emptyList()
) : Exception("API Error [$statusCode] $errorCode: $errorMessage")

object NetworkConfig {
    var baseUrl: String = BuildConfig.DEFAULT_API_BASE_URL
    var isDemoMode: Boolean = BuildConfig.DEFAULT_DEMO_MODE
    var demoActorId: String = BuildConfig.DEFAULT_DEMO_ACTOR_ID

    fun describeConnectionProblem(error: Throwable): String {
        return if (error is IOException) {
            "No connection to Proofline. Your receipt is still on this device - try again once you have signal."
        } else {
            error.message ?: "Something went wrong talking to Proofline. Nothing has been submitted."
        }
    }
}

class ProoflineApiClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .build()
) {
    val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private fun newRequestBuilder(path: String): Request.Builder {
        val url = if (path.startsWith("http")) path else "${NetworkConfig.baseUrl.trimEnd('/')}/${path.trimStart('/')}"
        val builder = Request.Builder()
            .url(url)
            .addHeader("Accept", "application/json")
            .addHeader("X-Request-ID", UUID.randomUUID().toString())

        if (NetworkConfig.isDemoMode && NetworkConfig.demoActorId.isNotBlank()) {
            builder.addHeader("X-Demo-Actor-Id", NetworkConfig.demoActorId)
        }
        return builder
    }

    private inline fun <reified T> executeRequest(request: Request): T {
        client.newCall(request).execute().use { response ->
            val responseBody = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                try {
                    val errorEnvelope = json.decodeFromString<ApiErrorEnvelope>(responseBody)
                    throw ProoflineApiException(
                        statusCode = response.code,
                        errorCode = errorEnvelope.error.code,
                        errorMessage = errorEnvelope.error.message,
                        requestId = errorEnvelope.error.requestId,
                        details = errorEnvelope.error.details.map { it.message }
                    )
                } catch (e: ProoflineApiException) {
                    throw e
                } catch (_: Exception) {
                    throw ProoflineApiException(
                        statusCode = response.code,
                        errorCode = "HTTP_${response.code}",
                        errorMessage = responseBody.ifBlank { response.message }
                    )
                }
            }
            return json.decodeFromString(responseBody)
        }
    }

    suspend fun getExpenses(): Result<ExpenseListResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val request = newRequestBuilder("expenses").get().build()
            executeRequest(request)
        }
    }

    suspend fun getExpense(expenseId: String): Result<Expense> = withContext(Dispatchers.IO) {
        runCatching {
            val request = newRequestBuilder("expenses/$expenseId").get().build()
            executeRequest(request)
        }
    }

    suspend fun createExpense(
        createRequest: CreateExpenseRequest,
        idempotencyKey: String = UUID.randomUUID().toString()
    ): Result<Expense> = withContext(Dispatchers.IO) {
        runCatching {
            val body = json.encodeToString(createRequest).toRequestBody(jsonMediaType)
            val request = newRequestBuilder("expenses")
                .addHeader("Idempotency-Key", idempotencyKey)
                .post(body)
                .build()
            executeRequest(request)
        }
    }

    suspend fun uploadReceipt(
        expenseId: String,
        filename: String,
        mimeType: String,
        fileBytes: ByteArray
    ): Result<ReceiptSummary> = withContext(Dispatchers.IO) {
        runCatching {
            val mediaType = mimeType.toMediaType()
            val filePart = fileBytes.toRequestBody(mediaType)
            val multipartBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", filename, filePart)
                .build()

            val request = newRequestBuilder("expenses/$expenseId/receipts")
                .post(multipartBody)
                .build()
            executeRequest(request)
        }
    }

    suspend fun updateExpense(
        expenseId: String,
        updateRequest: UpdateExpenseRequest
    ): Result<Expense> = withContext(Dispatchers.IO) {
        runCatching {
            val body = json.encodeToString(updateRequest).toRequestBody(jsonMediaType)
            val request = newRequestBuilder("expenses/$expenseId")
                .patch(body)
                .build()
            executeRequest(request)
        }
    }

    suspend fun submitExpense(
        expenseId: String,
        idempotencyKey: String
    ): Result<Expense> = withContext(Dispatchers.IO) {
        runCatching {
            val emptyBody = "".toRequestBody(jsonMediaType)
            val request = newRequestBuilder("expenses/$expenseId/submit")
                .addHeader("Idempotency-Key", idempotencyKey)
                .post(emptyBody)
                .build()
            executeRequest(request)
        }
    }

    suspend fun checkPolicy(expenseId: String): Result<PolicyCheckResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val emptyBody = "".toRequestBody(jsonMediaType)
            val request = newRequestBuilder("policy/check")
                .post(emptyBody)
                .build()
            executeRequest(request)
        }
    }
}
