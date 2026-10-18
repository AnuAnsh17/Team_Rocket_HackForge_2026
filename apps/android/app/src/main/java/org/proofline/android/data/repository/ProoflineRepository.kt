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
    baseUrl: String = "http://10.0.2.2:8000/api/v1/"
) {
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

    private val api: ProoflineApi = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(client)
        .addConverterFactory(GsonConverterFactory.create(customGson))
        .build()
        .create(ProoflineApi::class.java)

    // Real seeded UUID from backend/app/services/demo_service.py (employee.asha)
    var currentDemoActor: String = DemoActors.default
    private val gson = Gson()

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
