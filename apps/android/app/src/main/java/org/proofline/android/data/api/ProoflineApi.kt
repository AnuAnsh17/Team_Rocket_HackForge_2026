package org.proofline.android.data.api

import org.proofline.android.data.model.DemoSeedResponse
import org.proofline.android.data.model.Expense
import org.proofline.android.data.model.ExpenseListResponse
import org.proofline.android.data.model.MembershipSummary
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Backend routes used by the list and detail screens.
 *
 * There is deliberately no identity argument here. The `Authorization` header is
 * attached by the OkHttp interceptor on the client this interface is built with,
 * so a call site cannot forget it and cannot substitute an identity of its own.
 */
interface ProoflineApi {
    @GET("me")
    suspend fun getMe(): Response<MembershipSummary>

    @GET("expenses")
    suspend fun getExpenses(
        @Query("limit") limit: Int = 20,
        @Query("status") status: String? = null
    ): Response<ExpenseListResponse>

    @GET("expenses/{expenseId}")
    suspend fun getExpense(
        @Path("expenseId") expenseId: String
    ): Response<Expense>

    @POST("demo/seed")
    suspend fun seedDemo(): Response<DemoSeedResponse>
}
