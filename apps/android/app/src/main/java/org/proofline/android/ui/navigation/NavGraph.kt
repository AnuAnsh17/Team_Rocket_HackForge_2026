package org.proofline.android.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import org.proofline.android.data.repository.TravelDayRepository
import org.proofline.android.ui.screens.*
import org.proofline.android.ui.viewmodel.ProoflineViewModel

sealed class Screen(val route: String, val title: String) {
    object Home : Screen("home", "Home")
    object Expenses : Screen("expenses?status={status}", "Claims") {
        fun createRoute(status: String? = null) = if (status != null) "expenses?status=$status" else "expenses"
    }
    object Calendar : Screen("calendar", "Calendar")
    object Capture : Screen("capture", "Capture")
    object Profile : Screen("profile", "Profile")
    object Detail : Screen("detail/{expenseId}", "Detail") {
        fun createRoute(expenseId: String) = "detail/$expenseId"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NavGraph(viewModel: ProoflineViewModel, travelRepo: TravelDayRepository) {
    val navController = rememberNavController()
    val state by viewModel.uiState.collectAsState()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val bottomNavItems = listOf(
        Screen.Home,
        Screen.Expenses,
        Screen.Calendar,
        Screen.Profile
    )

    Scaffold(
        floatingActionButton = {
            if (currentRoute == Screen.Home.route || currentRoute == Screen.Calendar.route) {
                FloatingActionButton(onClick = { navController.navigate(Screen.Capture.route) }) {
                    Icon(Icons.Default.Add, contentDescription = "Add Receipt")
                }
            }
        },
        bottomBar = {
            if (bottomNavItems.any { currentRoute?.startsWith(it.route.substringBefore("?")) == true }) {
                NavigationBar {
                    bottomNavItems.forEach { screen ->
                        val selected = when (screen) {
                            Screen.Expenses -> currentRoute?.startsWith("expenses") == true
                            else -> currentRoute == screen.route
                        }
                        NavigationBarItem(
                            icon = {
                                when (screen) {
                                    Screen.Home -> Icon(Icons.Default.Home, contentDescription = screen.title)
                                    Screen.Expenses -> Icon(Icons.Default.List, contentDescription = screen.title)
                                    Screen.Calendar -> Icon(Icons.Default.DateRange, contentDescription = screen.title)
                                    Screen.Profile -> Icon(Icons.Default.Person, contentDescription = screen.title)
                                    else -> {}
                                }
                            },
                            label = { Text(screen.title) },
                            selected = selected,
                            onClick = {
                                val targetRoute = if (screen == Screen.Expenses) Screen.Expenses.createRoute() else screen.route
                                if (currentRoute != targetRoute) {
                                    navController.navigate(targetRoute) {
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
                    onNavigateToExpenses = { status ->
                        navController.navigate(Screen.Expenses.createRoute(status))
                    },
                    onNavigateToCapture = { navController.navigate(Screen.Capture.route) },
                    onRefresh = { viewModel.loadData() }
                )
            }
            composable(
                route = Screen.Expenses.route,
                arguments = listOf(navArgument("status") { nullable = true; defaultValue = null })
            ) { backStackEntry ->
                val status = backStackEntry.arguments?.getString("status")
                ExpensesScreen(
                    state = state,
                    initialStatusFilter = status,
                    onRefresh = { viewModel.loadData() },
                    onExpenseClick = { expenseId ->
                        navController.navigate(Screen.Detail.createRoute(expenseId))
                    }
                )
            }
            composable(Screen.Calendar.route) {
                CalendarScreen(
                    state = state,
                    travelRepo = travelRepo,
                    onNavigateToCapture = { navController.navigate(Screen.Capture.route) },
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
                ProfileScreen(
                    state = state,
                    onRefresh = { viewModel.loadData() },
                    onSeedDemo = { viewModel.seedDemoDataset() }
                )
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
