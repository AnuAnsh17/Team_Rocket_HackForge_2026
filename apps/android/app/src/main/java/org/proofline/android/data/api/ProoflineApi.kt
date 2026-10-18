package org.proofline.android.data.api

import org.proofline.android.data.model.DemoSeedResponse
import org.proofline.android.data.model.ExpenseListResponse
import org.proofline.android.data.model.MembershipSummary
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Query

interface ProoflineApi {
    @GET("me")
    suspend fun getMe(
        @Header("X-Demo-Actor") demoActor: String? = null
    ): Response<MembershipSummary>

    @GET("expenses")
    suspend fun getExpenses(
        @Header("X-Demo-Actor") demoActor: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("status") status: String? = null
    ): Response<ExpenseListResponse>

    @POST("demo/seed")
    suspend fun seedDemo(): Response<DemoSeedResponse>
}
