package org.proofline.android.features.submit

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun SubmitScreen(
    expenseId: String,
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onNavigateToStatus: (expenseId: String) -> Unit,
    viewModel: SubmitViewModel = viewModel(
        factory = SubmitViewModel.Factory(expenseId, apiClient)
    )
) {
    val uiState by viewModel.uiState.collectAsState()

    ProoflineScaffold(
        title = "Submit Claim",
        onBackClick = onBackClick
    ) {
        when (val state = uiState) {
            is SubmitUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = ProoflineColors.Accent)
                }
            }
            is SubmitUiState.Success -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(ProoflineDimensions.SpacingMd),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Box(
                        modifier = Modifier
                            .size(64.dp)
                            .clip(CircleShape)
                            .background(ProoflineColors.ResultPass),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = "Success",
                            tint = ProoflineColors.Text,
                            modifier = Modifier.size(36.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    Text(
                        text = "Claim Successfully Submitted",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        text = "Your expense claim is now in the review queue.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = ProoflineColors.TextMuted
                    )

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingLg))

                    ProoflineCard {
                        Text(
                            text = "Claim Reference",
                            style = MaterialTheme.typography.labelSmall
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = state.claimId,
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.Bold,
                            color = ProoflineColors.Accent
                        )
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingLg))

                    Button(
                        onClick = { onNavigateToStatus(state.claimId) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(ProoflineDimensions.MinTouchTarget),
                        shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                        colors = ButtonDefaults.buttonColors(containerColor = ProoflineColors.Accent)
                    ) {
                        Text("View Claim Status & History", fontWeight = FontWeight.SemiBold)
                    }
                }
            }
            is SubmitUiState.Ready, is SubmitUiState.Submitting, is SubmitUiState.Error -> {
                val exp = when (state) {
                    is SubmitUiState.Ready -> state.expense
                    is SubmitUiState.Submitting -> state.expense
                    is SubmitUiState.Error -> state.expense
                    else -> null
                }
                val isSubmitting = state is SubmitUiState.Submitting
                val errorMessage = (state as? SubmitUiState.Error)?.message

                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(ProoflineDimensions.SpacingMd),
                    verticalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text(
                            text = "Confirm Claim Details",
                            style = MaterialTheme.typography.titleLarge
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Once submitted, this expense will be checked against applicable policy rules.",
                            style = MaterialTheme.typography.bodyMedium
                        )

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                        if (exp != null) {
                            ProoflineCard(title = "Summary") {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Merchant", color = ProoflineColors.TextMuted)
                                    Text(exp.merchant.value, fontWeight = FontWeight.SemiBold)
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Amount", color = ProoflineColors.TextMuted)
                                    Text("${exp.amount.value.currency} ${exp.amount.value.value}", fontWeight = FontWeight.Bold)
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Expense Date", color = ProoflineColors.TextMuted)
                                    Text(exp.expenseDate.value)
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Category", color = ProoflineColors.TextMuted)
                                    Text(exp.category ?: "Uncategorized")
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Receipts Attached", color = ProoflineColors.TextMuted)
                                    Text("${exp.receipts.size} file(s)")
                                }
                            }
                        }

                        if (errorMessage != null) {
                            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                            ProoflineCard {
                                Text(
                                    text = "Submission Notice",
                                    style = MaterialTheme.typography.headlineMedium,
                                    color = ProoflineColors.StatusRejected
                                )
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(errorMessage, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }

                    Button(
                        onClick = { viewModel.submit() },
                        enabled = !isSubmitting && exp != null,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(ProoflineDimensions.MinTouchTarget),
                        shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                        colors = ButtonDefaults.buttonColors(containerColor = ProoflineColors.Accent)
                    ) {
                        if (isSubmitting) {
                            CircularProgressIndicator(
                                color = ProoflineColors.Text,
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text(
                                text = "Submit Claim",
                                fontWeight = FontWeight.SemiBold,
                                color = ProoflineColors.Text
                            )
                        }
                    }
                }
            }
        }
    }
}
