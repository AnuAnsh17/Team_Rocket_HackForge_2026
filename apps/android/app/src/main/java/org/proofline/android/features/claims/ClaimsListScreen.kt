package org.proofline.android.features.claims

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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.designsystem.StatusPill
import org.proofline.android.core.model.ExpenseSummary
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun ClaimsListScreen(
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onNavigateToClaim: (String) -> Unit,
    viewModel: ClaimsListViewModel = viewModel(
        factory = ClaimsListViewModel.Factory(apiClient)
    )
) {
    val uiState by viewModel.uiState.collectAsState()

    ProoflineScaffold(
        title = "All Claims",
        onBackClick = onBackClick
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(ProoflineDimensions.SpacingMd)
        ) {
            // Header Row with Title & Refresh
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Expense History",
                    style = MaterialTheme.typography.titleLarge
                )
                IconButton(onClick = { viewModel.loadClaims(isRefresh = true) }) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Refresh claims",
                        tint = ProoflineColors.TextMuted
                    )
                }
            }

            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

            // Status Grouping Tabs
            val currentTab = (uiState as? ClaimsListUiState.Success)?.currentTab ?: ClaimsFilterTab.ALL
            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(ClaimsFilterTab.entries) { tab ->
                    FilterChip(
                        selected = tab == currentTab,
                        onClick = { viewModel.setFilterTab(tab) },
                        label = { Text(tab.label) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = ProoflineColors.Accent,
                            selectedLabelColor = ProoflineColors.Text,
                            containerColor = ProoflineColors.SurfaceRaised,
                            labelColor = ProoflineColors.TextMuted
                        ),
                        shape = RoundedCornerShape(ProoflineDimensions.RadiusSm)
                    )
                }
            }

            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

            when (val state = uiState) {
                is ClaimsListUiState.Loading -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = ProoflineColors.Accent)
                    }
                }
                is ClaimsListUiState.Error -> {
                    ProoflineCard {
                        Text(
                            text = "Notice",
                            style = MaterialTheme.typography.headlineMedium,
                            color = ProoflineColors.StatusNeedsInfo
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(text = state.message, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                is ClaimsListUiState.Success -> {
                    if (state.filteredClaims.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No claims found under '${state.currentTab.label}'.",
                                style = MaterialTheme.typography.bodyLarge,
                                color = ProoflineColors.TextMuted
                            )
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)
                        ) {
                            items(state.filteredClaims, key = { it.id }) { expense ->
                                ClaimSummaryItem(
                                    expense = expense,
                                    onClick = { onNavigateToClaim(expense.id) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ClaimSummaryItem(
    expense: ExpenseSummary,
    onClick: () -> Unit
) {
    ProoflineCard(
        modifier = Modifier.clickable { onClick() }
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
                if (expense.openFindingCount > 0) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "• ${expense.openFindingCount} open finding(s)",
                        style = MaterialTheme.typography.labelSmall,
                        color = ProoflineColors.StatusNeedsInfo
                    )
                }
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
