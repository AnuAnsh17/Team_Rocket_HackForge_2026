package org.proofline.android.features.correction

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.model.FindingStatus
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun CorrectionScreen(
    expenseId: String,
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onCorrectionSuccess: (expenseId: String) -> Unit,
    viewModel: CorrectionViewModel = viewModel(
        factory = CorrectionViewModel.Factory(expenseId, apiClient)
    )
) {
    val uiState by viewModel.uiState.collectAsState()

    var merchant by remember { mutableStateOf("") }
    var date by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var currency by remember { mutableStateOf("INR") }
    var category by remember { mutableStateOf("") }
    var purpose by remember { mutableStateOf("") }
    var clientName by remember { mutableStateOf("") }
    var attendeeCount by remember { mutableStateOf("") }

    // Synchronize local form fields when expense loads or reloads
    LaunchedEffect(uiState) {
        val exp = when (val state = uiState) {
            is CorrectionUiState.Ready -> state.expense
            is CorrectionUiState.Error -> state.expense
            else -> null
        }
        if (exp != null) {
            merchant = exp.merchant.value
            date = exp.expenseDate.value
            amount = exp.amount.value.value
            currency = exp.amount.value.currency
            category = exp.category.orEmpty()
            purpose = exp.businessPurpose.orEmpty()
            clientName = exp.clientName.orEmpty()
            attendeeCount = exp.attendeeCount?.toString().orEmpty()
        } else if (uiState is CorrectionUiState.Success) {
            onCorrectionSuccess(expenseId)
        }
    }

    ProoflineScaffold(
        title = "Provide Requested Details",
        onBackClick = onBackClick
    ) {
        when (val state = uiState) {
            is CorrectionUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = ProoflineColors.Accent)
                }
            }
            is CorrectionUiState.Ready, is CorrectionUiState.Submitting, is CorrectionUiState.Error -> {
                val exp = when (state) {
                    is CorrectionUiState.Ready -> state.expense
                    is CorrectionUiState.Error -> state.expense
                    else -> viewModel.currentExpense
                }
                val isSubmitting = state is CorrectionUiState.Submitting
                val errorMessage = (state as? CorrectionUiState.Error)?.message
                val openFindings = exp?.findings?.filter { it.status == FindingStatus.OPEN } ?: emptyList()

                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(ProoflineDimensions.SpacingMd)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        text = "Reviewer Information Request",
                        style = MaterialTheme.typography.titleLarge
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Finance has requested additional context to process your reimbursement.",
                        style = MaterialTheme.typography.bodyMedium
                    )

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    if (openFindings.isNotEmpty()) {
                        ProoflineCard(title = "Requested Action Items") {
                            Column(verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)) {
                                openFindings.forEach { finding ->
                                    Row(verticalAlignment = Alignment.Top) {
                                        Icon(
                                            imageVector = Icons.Default.Info,
                                            contentDescription = null,
                                            tint = ProoflineColors.StatusNeedsInfo,
                                            modifier = Modifier.size(18.dp)
                                        )
                                        Spacer(modifier = Modifier.padding(4.dp))
                                        Column {
                                            Text(
                                                text = finding.employeeMessage ?: finding.message,
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.SemiBold,
                                                color = ProoflineColors.Text
                                            )
                                            if (finding.sourceReference != null) {
                                                Text(
                                                    text = "Clause: ${finding.sourceReference.clause}",
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = ProoflineColors.Accent
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))
                    }

                    if (errorMessage != null) {
                        ProoflineCard {
                            Text(
                                text = "Notice",
                                style = MaterialTheme.typography.headlineMedium,
                                color = ProoflineColors.StatusRejected
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(errorMessage, style = MaterialTheme.typography.bodyMedium)
                        }
                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                    }

                    ProoflineCard(title = "Correct or Complete Fields (Version ${exp?.version ?: 1})") {
                        OutlinedTextField(
                            value = merchant,
                            onValueChange = { merchant = it },
                            label = { Text("Merchant") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = ProoflineColors.Accent,
                                unfocusedBorderColor = ProoflineColors.Border
                            )
                        )

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        Row(horizontalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)) {
                            OutlinedTextField(
                                value = amount,
                                onValueChange = { amount = it },
                                label = { Text("Amount") },
                                modifier = Modifier.weight(2f),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = ProoflineColors.Accent,
                                    unfocusedBorderColor = ProoflineColors.Border
                                )
                            )
                            OutlinedTextField(
                                value = currency,
                                onValueChange = { currency = it },
                                label = { Text("Currency") },
                                modifier = Modifier.weight(1f),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = ProoflineColors.Accent,
                                    unfocusedBorderColor = ProoflineColors.Border
                                )
                            )
                        }

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        OutlinedTextField(
                            value = category,
                            onValueChange = { category = it },
                            label = { Text("Expense Category") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = ProoflineColors.Accent,
                                unfocusedBorderColor = ProoflineColors.Border
                            )
                        )

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        OutlinedTextField(
                            value = purpose,
                            onValueChange = { purpose = it },
                            label = { Text("Business Purpose") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = ProoflineColors.Accent,
                                unfocusedBorderColor = ProoflineColors.Border
                            )
                        )

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        OutlinedTextField(
                            value = clientName,
                            onValueChange = { clientName = it },
                            label = { Text("Client Name") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = ProoflineColors.Accent,
                                unfocusedBorderColor = ProoflineColors.Border
                            )
                        )

                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        OutlinedTextField(
                            value = attendeeCount,
                            onValueChange = { attendeeCount = it },
                            label = { Text("Attendee Count") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = ProoflineColors.Accent,
                                unfocusedBorderColor = ProoflineColors.Border
                            )
                        )
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingLg))

                    Button(
                        onClick = {
                            viewModel.submitCorrection(
                                merchant = merchant,
                                date = date,
                                amount = amount,
                                currency = currency,
                                category = category,
                                purpose = purpose,
                                clientName = clientName,
                                attendeeCount = attendeeCount
                            )
                        },
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
                                text = "Submit Correction & Re-evaluate",
                                fontWeight = FontWeight.SemiBold,
                                color = ProoflineColors.Text
                            )
                        }
                    }
                }
            }
            else -> {}
        }
    }
}
