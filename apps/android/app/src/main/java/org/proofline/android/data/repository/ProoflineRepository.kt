package org.proofline.android.data.repository

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import org.proofline.android.core.network.HttpClients
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.data.api.ProoflineApi
import org.proofline.android.data.model.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * Read/write access to the Proofline backend for the list and detail screens.
 *
 * The OkHttp client is injected rather than built here. The client passed in is
 * the authenticated one (`HttpClients.authenticated`), which is what attaches the
 * Supabase bearer token - and only in a debug build, the demo actor fallback.
 */
class ProoflineRepository(
    baseUrl: String = NetworkConfig.baseUrl,
    client: OkHttpClient = HttpClients.base()
) {
    private val customGson: Gson = GsonBuilder()
        .registerTypeAdapter(Money::class.java, MoneyDeserializer())
        .create()

    private val api: ProoflineApi = Retrofit.Builder()
        .baseUrl(baseUrl.trimEnd('/') + "/")
        .client(client)
        .addConverterFactory(GsonConverterFactory.create(customGson))
        .build()
        .create(ProoflineApi::class.java)

    suspend fun getMe(): Result<MembershipSummary> {
        return try {
            val response = api.getMe()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(describeFailure("load employee membership", response)))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.localizedMessage ?: e.message}"))
        }
    }

    suspend fun getExpenses(status: String? = null): Result<ExpenseListResponse> {
        return try {
            val response = api.getExpenses(status = status)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(describeFailure("load expenses", response)))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.localizedMessage ?: e.message}"))
        }
    }

    /**
     * One expense by id.
     *
     * Returns a failure rather than a placeholder when the backend cannot supply
     * the record: a detail screen that invents a status is worse than one that
     * says it could not load it.
     */
    suspend fun getExpense(expenseId: String): Result<Expense> {
        return try {
            val response = api.getExpense(expenseId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(describeFailure("load this claim", response)))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.localizedMessage ?: e.message}"))
        }
    }

    suspend fun seedDemo(): Result<Unit> = runCatching {
        api.seedDemo()
        Unit
    }

    private fun describeFailure(action: String, response: retrofit2.Response<*>): String {
        val message = parseErrorMessage(response.errorBody()?.string())
            ?: "Failed to $action (HTTP ${response.code()})"
        return message
    }

    private fun parseErrorMessage(errorBody: String?): String? {
        if (errorBody.isNullOrBlank()) return null
        return try {
            val envelope = customGson.fromJson(errorBody, ApiErrorEnvelope::class.java)
            envelope?.error?.message
        } catch (e: Exception) {
            null
        }
    }
}
