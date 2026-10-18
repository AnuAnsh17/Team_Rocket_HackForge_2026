package org.proofline.android.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.launch
import org.proofline.android.core.auth.SessionManager
import org.proofline.android.data.repository.TravelDayRepository
import org.proofline.android.ui.screens.LoginScreen
import org.proofline.android.ui.viewmodel.LoginViewModel
import org.proofline.android.ui.viewmodel.ProoflineViewModel

/** Root routes. Everything behind [APP] requires a persisted Supabase session. */
object RootRoutes {
    const val LOGIN = "login"
    const val APP = "app"
}

/**
 * Starts at the login screen when the device holds no usable session, and in the
 * app when it does.
 *
 * The decision is made once per composition from the persisted store:
 * [SessionManager.hasRestorableSession] is true when both tokens are present. An
 * expired *access* token is not a reason to show the login screen - it is renewed
 * on the first backend call - but a missing refresh token is.
 *
 * Sign-out is a real sign-out: the session is revoked server-side (best effort)
 * and the local store is cleared before the login screen is shown.
 */
@Composable
fun ProoflineNavGraph(
    viewModel: ProoflineViewModel,
    loginViewModel: LoginViewModel,
    travelRepo: TravelDayRepository,
    sessionManager: SessionManager
) {
    val navController = rememberNavController()
    val scope = rememberCoroutineScope()
    val startDestination = remember {
        if (sessionManager.hasRestorableSession()) RootRoutes.APP else RootRoutes.LOGIN
    }

    NavHost(navController = navController, startDestination = startDestination) {
        composable(RootRoutes.LOGIN) {
            val loginState by loginViewModel.uiState.collectAsState()
            LoginScreen(
                state = loginState,
                onEmailChange = loginViewModel::onEmailChange,
                onPasswordChange = loginViewModel::onPasswordChange,
                onSubmit = {
                    loginViewModel.signIn {
                        navController.navigate(RootRoutes.APP) {
                            popUpTo(RootRoutes.LOGIN) { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                }
            )
        }

        composable(RootRoutes.APP) {
            AppScaffold(
                viewModel = viewModel,
                travelRepo = travelRepo,
                onSignOut = {
                    scope.launch {
                        sessionManager.signOutAsync()
                        navController.navigate(RootRoutes.LOGIN) {
                            popUpTo(RootRoutes.APP) { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                }
            )
        }
    }
}
