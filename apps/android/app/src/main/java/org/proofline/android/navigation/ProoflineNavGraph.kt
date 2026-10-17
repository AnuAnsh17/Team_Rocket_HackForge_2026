package org.proofline.android.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import org.proofline.android.core.network.ProoflineApiClient
import org.proofline.android.features.capture.CaptureScreen
import org.proofline.android.features.correction.CorrectionScreen
import org.proofline.android.features.home.HomeScreen
import org.proofline.android.features.preflight.PreflightScreen
import org.proofline.android.features.review.ReviewExtractionScreen
import org.proofline.android.features.claims.ClaimsListScreen
import org.proofline.android.features.status.ClaimStatusScreen
import org.proofline.android.features.submit.SubmitScreen

object ProoflineRoutes {
    const val HOME = "home"
    const val CLAIMS = "claims"
    const val CAPTURE = "capture"
    const val REVIEW = "review/{expenseId}"
    const val PREFLIGHT = "preflight/{expenseId}"
    const val SUBMIT = "submit/{expenseId}"
    const val STATUS = "status/{expenseId}"
    const val CORRECTION = "correction/{expenseId}"

    fun review(expenseId: String) = "review/$expenseId"
    fun preflight(expenseId: String) = "preflight/$expenseId"
    fun submit(expenseId: String) = "submit/$expenseId"
    fun status(expenseId: String) = "status/$expenseId"
    fun correction(expenseId: String) = "correction/$expenseId"
}

@Composable
fun ProoflineNavGraph(
    navController: NavHostController,
    apiClient: ProoflineApiClient
) {
    NavHost(
        navController = navController,
        startDestination = ProoflineRoutes.HOME
    ) {
        composable(ProoflineRoutes.HOME) {
            HomeScreen(
                apiClient = apiClient,
                onNavigateToCapture = {
                    navController.navigate(ProoflineRoutes.CAPTURE)
                },
                onNavigateToClaim = { expenseId ->
                    navController.navigate(ProoflineRoutes.status(expenseId))
                },
                onNavigateToClaimsList = {
                    navController.navigate(ProoflineRoutes.CLAIMS)
                }
            )
        }

        composable(ProoflineRoutes.CLAIMS) {
            ClaimsListScreen(
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onNavigateToClaim = { expenseId ->
                    navController.navigate(ProoflineRoutes.status(expenseId))
                }
            )
        }

        composable(ProoflineRoutes.CAPTURE) {
            CaptureScreen(
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onUploadSuccess = { expenseId ->
                    navController.navigate(ProoflineRoutes.review(expenseId)) {
                        popUpTo(ProoflineRoutes.HOME)
                    }
                }
            )
        }

        composable(
            route = ProoflineRoutes.REVIEW,
            arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
        ) { backStackEntry ->
            val expenseId = backStackEntry.arguments?.getString("expenseId") ?: return@composable
            ReviewExtractionScreen(
                expenseId = expenseId,
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onProceedToPreflight = { id ->
                    navController.navigate(ProoflineRoutes.preflight(id))
                }
            )
        }

        composable(
            route = ProoflineRoutes.PREFLIGHT,
            arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
        ) { backStackEntry ->
            val expenseId = backStackEntry.arguments?.getString("expenseId") ?: return@composable
            PreflightScreen(
                expenseId = expenseId,
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onProceedToSubmit = { id ->
                    navController.navigate(ProoflineRoutes.submit(id))
                }
            )
        }

        composable(
            route = ProoflineRoutes.SUBMIT,
            arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
        ) { backStackEntry ->
            val expenseId = backStackEntry.arguments?.getString("expenseId") ?: return@composable
            SubmitScreen(
                expenseId = expenseId,
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onNavigateToStatus = { id ->
                    navController.navigate(ProoflineRoutes.status(id)) {
                        popUpTo(ProoflineRoutes.HOME)
                    }
                }
            )
        }

        composable(
            route = ProoflineRoutes.STATUS,
            arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
        ) { backStackEntry ->
            val expenseId = backStackEntry.arguments?.getString("expenseId") ?: return@composable
            ClaimStatusScreen(
                expenseId = expenseId,
                apiClient = apiClient,
                onBackClick = { navController.navigate(ProoflineRoutes.HOME) { popUpTo(ProoflineRoutes.HOME) { inclusive = true } } },
                onNavigateToCorrection = { id ->
                    navController.navigate(ProoflineRoutes.correction(id))
                }
            )
        }

        composable(
            route = ProoflineRoutes.CORRECTION,
            arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
        ) { backStackEntry ->
            val expenseId = backStackEntry.arguments?.getString("expenseId") ?: return@composable
            CorrectionScreen(
                expenseId = expenseId,
                apiClient = apiClient,
                onBackClick = { navController.popBackStack() },
                onCorrectionSuccess = { id ->
                    navController.navigate(ProoflineRoutes.status(id)) {
                        popUpTo(ProoflineRoutes.STATUS) { inclusive = true }
                    }
                }
            )
        }
    }
}
