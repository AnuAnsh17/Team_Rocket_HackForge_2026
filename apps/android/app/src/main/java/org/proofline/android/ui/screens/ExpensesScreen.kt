package org.proofline.android.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.proofline.android.ui.viewmodel.ProoflineUiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExpensesScreen(
    state: ProoflineUiState,
    initialStatusFilter: String? = null,
    onRefresh: () -> Unit,
    onExpenseClick: (String) -> Unit
) {
    val tabs = listOf(
        "All" to null,
        "Draft" to "draft",
        "Submitted" to "submitted",
        "Needs info" to "needs_info",
        "In review" to "in_review",
        "Approved" to "approved",
        "Not reimbursed" to "rejected"
    )

    var selectedTabIndex by remember {
        val initialIdx = tabs.indexOfFirst { it.second == initialStatusFilter }
        mutableStateOf(if (initialIdx >= 0) initialIdx else 0)
    }

    val currentStatusFilter = tabs[selectedTabIndex].second
    val filteredExpenses = if (currentStatusFilter == null) {
        state.expenses
    } else {
        state.expenses.filter { it.status == currentStatusFilter }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp)
    ) {
        Text(
            text = "My Expenses",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(12.dp))

        ScrollableTabRow(
            selectedTabIndex = selectedTabIndex,
            edgePadding = 0.dp
        ) {
            tabs.forEachIndexed { index, (label, status) ->
                val count = if (status == null) state.expenses.size else state.expenses.count { it.status == status }
                Tab(
                    selected = selectedTabIndex == index,
                    onClick = { selectedTabIndex = index },
                    text = {
                        Text(text = "$label ($count)")
                    }
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        if (state.errorMessage != null) {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(text = state.errorMessage, color = MaterialTheme.colorScheme.onErrorContainer)
                    Button(onClick = onRefresh) { Text("Retry") }
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
        }

        if (state.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else if (filteredExpenses.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                val tabName = tabs[selectedTabIndex].first.lowercase()
                Text("No $tabName claims yet.")
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(filteredExpenses) { expense ->
                    val merchantName = expense.merchant?.value ?: "Unknown merchant"
                    val moneyObj = expense.amount?.value
                    val amountStr = if (moneyObj != null) "${moneyObj.currency} ${moneyObj.value}" else "—"
                    val dateStr = expense.expense_date?.value ?: "Date missing"
                    val statusColor = when (expense.status) {
                        "approved" -> Color(0xFF2E7D32)
                        "rejected" -> Color(0xFFC62828)
                        "submitted", "in_review" -> Color(0xFF1565C0)
                        "needs_info" -> Color(0xFFEF6C00)
                        else -> Color(0xFF757575)
                    }

                    Card(
                        onClick = { onExpenseClick(expense.id) },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = merchantName,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyLarge
                                )
                                Text(
                                    text = amountStr,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = dateStr,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Surface(
                                    color = statusColor.copy(alpha = 0.15f),
                                    shape = MaterialTheme.shapes.small
                                ) {
                                    Text(
                                        text = expense.status.uppercase(),
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = statusColor
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
