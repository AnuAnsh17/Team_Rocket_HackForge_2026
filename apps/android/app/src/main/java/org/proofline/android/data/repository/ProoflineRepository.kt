package org.proofline.android.data.repository

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import org.proofline.android.data.api.ProoflineApi
import org.proofline.android.data.model.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class ProoflineRepository(
    initialBaseUrl: String = DEFAULT_BASE_URL
) {
    companion object {
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000/api/v1/"
    }

    private val customGson: Gson = GsonBuilder()
        .registerTypeAdapter(Money::class.java, MoneyDeserializer())
        .create()

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .build()

    private var currentBaseUrl: String = if (initialBaseUrl.endsWith("/")) initialBaseUrl else "$initialBaseUrl/"
    private var api: ProoflineApi = buildApi(currentBaseUrl)

    var currentDemoActor: String = DemoActors.default

    private fun buildApi(baseUrl: String): ProoflineApi {
        val url = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        return Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(customGson))
            .build()
            .create(ProoflineApi::class.java)
    }

    fun setBaseUrl(newUrl: String) {
        currentBaseUrl = if (newUrl.endsWith("/")) newUrl else "$newUrl/"
        api = buildApi(currentBaseUrl)
    }

    suspend fun getMe(): Result<MembershipSummary> {
        return try {
            val response = api.getMe(currentDemoActor)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errorBody = response.errorBody()?.string()
                val message = parseErrorMessage(errorBody) ?: "Failed to load employee membership (HTTP ${response.code()})"
                Result.failure(Exception(message))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.localizedMessage ?: e.message}"))
        }
    }

    suspend fun getExpenses(status: String? = null): Result<ExpenseListResponse> {
        return try {
            val response = api.getExpenses(currentDemoActor, status = status)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errorBody = response.errorBody()?.string()
                val message = parseErrorMessage(errorBody) ?: "Failed to load expenses (HTTP ${response.code()})"
                Result.failure(Exception(message))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.localizedMessage ?: e.message}"))
        }
    }

    suspend fun seedDemo(): Result<Unit> = runCatching {
        api.seedDemo(currentDemoActor)
        Unit
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
