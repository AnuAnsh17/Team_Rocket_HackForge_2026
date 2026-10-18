package org.proofline.android.core.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.proofline.android.core.model.ApiErrorEnvelope
import org.proofline.android.core.model.CreateExpenseRequest
import org.proofline.android.core.model.Expense
import org.proofline.android.core.model.ExpenseListResponse
import org.proofline.android.core.model.PolicyCheckResponse
import org.proofline.android.core.model.ReceiptSummary
import org.proofline.android.core.model.UpdateExpenseRequest
import java.io.IOException
import java.util.UUID

/**
 * A structured failure from the Proofline backend.
 *
 * The code is the contract; the message is for the user; the request id is what
 * lets a reviewer find the matching server log line.
 */
class ProoflineApiException(
    val statusCode: Int,
    val errorCode: String,
    val errorMessage: String,
    val requestId: String? = null,
    val details: List<String> = emptyList()
) : Exception("API Error [$statusCode] $errorCode: $errorMessage")

/** One place that turns a transport failure into something an employee can act on. */
object NetworkErrors {
    fun describe(error: Throwable): String = when (error) {
        is IOException ->
            "No connection to Proofline. Nothing has been submitted - try again once you have signal."
        is ProoflineApiException ->
            error.errorMessage.ifBlank { "Proofline refused the request (${error.statusCode})." }
        else ->
            "Something went wrong talking to Proofline. Nothing has been submitted."
    }
}

/**
 * Full-lifecycle Proofline backend client: list, read, create, upload, update,
 * submit and policy-check expenses.
 *
 * Salvaged from the `mobile-app-prior` branch and adapted to this branch. Note
 * what is *not* here: no demo header logic. The `Authorization` header (and the
 * debug-only `X-Demo-Actor-Id` fallback) is attached by [AuthInterceptor] on the
 * injected client, so every call made from this class is authenticated by exactly
 * the same code path as every other backend call in the app.
 */
class ProoflineApiClient(
    private val client: OkHttpClient = HttpClients.base(),
    private val baseUrlProvider: () -> String = { NetworkConfig.baseUrl }
) {
    val json = ProoflineJson.instance

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private fun newRequestBuilder(path: String): Request.Builder {
        val base = baseUrlProvider().trimEnd('/')
        val url = if (path.startsWith("http")) path else "$base/${path.trimStart('/')}"
        return Request.Builder()
            .url(url)
            .addHeader("Accept", "application/json")
            .addHeader("X-Request-ID", UUID.randomUUID().toString())
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

    suspend fun getExpenses(limit: Int? = null): Result<ExpenseListResponse> =
        withContext(Dispatchers.IO) {
            runCatching {
                val suffix = limit?.let { "?limit=$it" } ?: ""
                val request = newRequestBuilder("expenses$suffix").get().build()
                executeRequest<ExpenseListResponse>(request)
            }
        }

    suspend fun getExpense(expenseId: String): Result<Expense> = withContext(Dispatchers.IO) {
        runCatching {
            val request = newRequestBuilder("expenses/$expenseId").get().build()
            executeRequest<Expense>(request)
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
            executeRequest<Expense>(request)
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
            executeRequest<ReceiptSummary>(request)
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
            executeRequest<Expense>(request)
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
            executeRequest<Expense>(request)
        }
    }

    suspend fun checkPolicy(expenseId: String): Result<PolicyCheckResponse> =
        withContext(Dispatchers.IO) {
            runCatching {
                // The contract pins this body: PolicyCheckRequest takes an optional
                // expense_id for an existing draft and the inline fields when it is
                // null. So the expense belongs in the body. A header would be ignored,
                // and an empty document would ask the backend to evaluate nothing and
                // report an unresolved result for a claim it never looked at.
                val payload = buildJsonObject { put("expense_id", expenseId) }
                val request = newRequestBuilder("policy/check")
                    .post(payload.toString().toRequestBody(jsonMediaType))
                    .build()
                executeRequest<PolicyCheckResponse>(request)
            }
        }
}
