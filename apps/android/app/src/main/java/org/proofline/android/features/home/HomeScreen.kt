package org.proofline.android.features.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.designsystem.StatusPill
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.model.ExpenseSummary
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient
import java.math.BigDecimal

@Composable
fun HomeScreen(
    apiClient: ProoflineApiClient,
    onNavigateToCapture: () -> Unit,
    onNavigateToClaim: (String) -> Unit,
    onNavigateToClaimsList: () -> Unit
) {
    var expenses by remember { mutableStateOf<List<ExpenseSummary>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun loadData() {
        scope.launch {
            isLoading = true
            errorMessage = null
            apiClient.getExpenses()
                .onSuccess { response ->
                    expenses = response.items
                    isLoading = false
                }
                .onFailure { error ->
                    errorMessage = NetworkConfig.describeConnectionProblem(error)
                    isLoading = false
                }
        }
    }

    LaunchedEffect(Unit) {
        loadData()
    }

    val totalSpent = remember(expenses) {
        expenses
            .filter { it.status != ExpenseStatus.REJECTED && it.status != ExpenseStatus.WITHDRAWN }
            .fold(BigDecimal.ZERO) { acc, item ->
                acc.add(item.amount.value.toBigDecimalOrNull() ?: BigDecimal.ZERO)
            }
    }

    val pendingCount = remember(expenses) {
        expenses.count { it.status == ExpenseStatus.SUBMITTED || it.status == ExpenseStatus.IN_REVIEW }
    }

    val needsInfoCount = remember(expenses) {
        expenses.count { it.status == ExpenseStatus.NEEDS_INFO }
    }

    ProoflineScaffold(
        title = "Proofline Expenses",
        floatingActionButton = {
            FloatingActionButton(
                onClick = onNavigateToCapture,
                containerColor = ProoflineColors.Accent,
                contentColor = ProoflineColors.Text
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(imageVector = Icons.Default.Add, contentDescription = "Add receipt")
                    Spacer(modifier = Modifier.padding(2.dp))
                    Text("Scan / Upload", fontWeight = FontWeight.SemiBold)
                }
            }
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(ProoflineDimensions.SpacingMd)
        ) {
            // Metrics Summary Cards
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)
            ) {
                ProoflineCard(modifier = Modifier.weight(1f)) {
                    Text("Submitted Spend", style = MaterialTheme.typography.labelSmall)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "₹ $totalSpent",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = ProoflineColors.Text
                    )
                }

                ProoflineCard(modifier = Modifier.weight(1f)) {
                    Text("Pending Review", style = MaterialTheme.typography.labelSmall)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "$pendingCount",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = ProoflineColors.StatusSubmitted
                    )
                }

                if (needsInfoCount > 0) {
                    ProoflineCard(modifier = Modifier.weight(1f)) {
                        Text("Needs You", style = MaterialTheme.typography.labelSmall, color = ProoflineColors.StatusNeedsInfo)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "$needsInfoCount",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                            color = ProoflineColors.StatusNeedsInfo
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Recent Claims",
                    style = MaterialTheme.typography.titleLarge
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "View All",
                        style = MaterialTheme.typography.bodyMedium,
                        color = ProoflineColors.Accent,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier
                            .clickable { onNavigateToClaimsList() }
                            .padding(end = 8.dp)
                    )
                    IconButton(onClick = { loadData() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh claims",
                            tint = ProoflineColors.TextMuted
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

            when {
                isLoading -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = ProoflineColors.Accent)
                    }
                }
                errorMessage != null -> {
                    ProoflineCard {
                        Text(
                            text = "Connection Notice",
                            style = MaterialTheme.typography.headlineMedium,
                            color = ProoflineColors.StatusNeedsInfo
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = errorMessage ?: "",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
                expenses.isEmpty() -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "No claims submitted yet",
                                style = MaterialTheme.typography.bodyLarge,
                                color = ProoflineColors.TextMuted
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Tap 'Scan / Upload' below to capture your first receipt.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = ProoflineColors.TextMuted
                            )
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)
                    ) {
                        items(expenses, key = { it.id }) { expense ->
                            ProoflineCard(
                                modifier = Modifier.clickable { onNavigateToClaim(expense.id) }
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.Top
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = expense.merchant ?: "Unknown Merchant",
                                            style = MaterialTheme.typography.headlineMedium,
                                            fontWeight = FontWeight.SemiBold
                                        )
                                        Spacer(modifier = Modifier.height(2.dp))
                                        Text(
                                            text = "${expense.expenseDate ?: "No date"} • ${expense.category ?: "Uncategorized"}",
                                            style = MaterialTheme.typography.labelSmall
                                        )
                                    }

                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(
                                            text = "${expense.amount.currency} ${expense.amount.value}",
                                            style = MaterialTheme.typography.headlineMedium,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Spacer(modifier = Modifier.height(4.dp))
                                        StatusPill(status = expense.status)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
