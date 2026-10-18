package org.proofline.android.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import org.proofline.android.ui.screens.*
import org.proofline.android.ui.viewmodel.ProoflineViewModel

sealed class Screen(val route: String, val title: String) {
    object Home : Screen("home", "Home")
    object Expenses : Screen("expenses", "Claims")
    object Capture : Screen("capture", "Capture")
    object Profile : Screen("profile", "Profile")
    object Detail : Screen("detail/{expenseId}", "Detail") {
        fun createRoute(expenseId: String) = "detail/$expenseId"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NavGraph(viewModel: ProoflineViewModel) {
    val navController = rememberNavController()
    val state by viewModel.uiState.collectAsState()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val items = listOf(
        Screen.Home,
        Screen.Expenses,
        Screen.Capture,
        Screen.Profile
    )

    Scaffold(
        bottomBar = {
            if (currentRoute in items.map { it.route }) {
                NavigationBar {
                    items.forEach { screen ->
                        NavigationBarItem(
                            icon = {
                                when (screen) {
                                    Screen.Home -> Icon(Icons.Default.Home, contentDescription = screen.title)
                                    Screen.Expenses -> Icon(Icons.Default.List, contentDescription = screen.title)
                                    Screen.Capture -> Icon(Icons.Default.Add, contentDescription = screen.title)
                                    Screen.Profile -> Icon(Icons.Default.Person, contentDescription = screen.title)
                                    else -> {}
                                }
                            },
                            label = { Text(screen.title) },
                            selected = currentRoute == screen.route,
                            onClick = {
                                if (currentRoute != screen.route) {
                                    navController.navigate(screen.route) {
                                        popUpTo(navController.graph.findStartDestination().id) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            }
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Home.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Home.route) {
                HomeScreen(
                    state = state,
                    onNavigateToExpenses = { navController.navigate(Screen.Expenses.route) },
                    onNavigateToCapture = { navController.navigate(Screen.Capture.route) },
                    onRefresh = { viewModel.loadData() }
                )
            }
            composable(Screen.Expenses.route) {
                ExpensesScreen(
                    state = state,
                    onRefresh = { viewModel.loadData() },
                    onExpenseClick = { expenseId ->
                        navController.navigate(Screen.Detail.createRoute(expenseId))
                    }
                )
            }
            composable(Screen.Capture.route) {
                CaptureScreen(
                    onBack = { navController.popBackStack() }
                )
            }
            composable(Screen.Profile.route) {
                ProfileScreen(state = state)
            }
            composable(
                route = Screen.Detail.route,
                arguments = listOf(navArgument("expenseId") { type = NavType.StringType })
            ) { backStackEntry ->
                val expenseId = backStackEntry.arguments?.getString("expenseId") ?: ""
                ExpenseDetailScreen(
                    expenseId = expenseId,
                    onBack = { navController.popBackStack() }
                )
            }
        }
    }
}
