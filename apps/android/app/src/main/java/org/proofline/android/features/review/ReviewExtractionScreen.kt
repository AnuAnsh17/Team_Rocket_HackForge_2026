package org.proofline.android.features.review

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.model.Expense
import org.proofline.android.core.model.FieldSource
import org.proofline.android.core.model.UpdateExpenseRequest
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun ReviewExtractionScreen(
    expenseId: String,
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onProceedToPreflight: (expenseId: String) -> Unit
) {
    var expense by remember { mutableStateOf<Expense?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var isSaving by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    var merchant by remember { mutableStateOf("") }
    var date by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var currency by remember { mutableStateOf("INR") }
    var category by remember { mutableStateOf("") }
    var purpose by remember { mutableStateOf("") }
    var clientName by remember { mutableStateOf("") }
    var attendeeCount by remember { mutableStateOf("") }

    fun loadExpense() {
        scope.launch {
            isLoading = true
            errorMessage = null
            apiClient.getExpense(expenseId)
                .onSuccess { exp ->
                    expense = exp
                    merchant = exp.merchant.value
                    date = exp.expenseDate.value
                    amount = exp.amount.value.value
                    currency = exp.amount.value.currency
                    category = exp.category.orEmpty()
                    purpose = exp.businessPurpose.orEmpty()
                    clientName = exp.clientName.orEmpty()
                    attendeeCount = exp.attendeeCount?.toString().orEmpty()
                    isLoading = false
                }
                .onFailure { err ->
                    errorMessage = NetworkConfig.describeConnectionProblem(err)
                    isLoading = false
                }
        }
    }

    LaunchedEffect(expenseId) {
        loadExpense()
    }

    fun saveAndProceed() {
        val currentExpense = expense ?: return
        scope.launch {
            isSaving = true
            errorMessage = null

            val updateReq = UpdateExpenseRequest(
                expectedVersion = currentExpense.version,
                merchant = merchant.ifBlank { null },
                expenseDate = date.ifBlank { null },
                amount = amount.ifBlank { null },
                currency = currency.ifBlank { null },
                category = category.ifBlank { null },
                businessPurpose = purpose.ifBlank { null },
                clientName = clientName.ifBlank { null },
                attendeeCount = attendeeCount.toIntOrNull()
            )

            apiClient.updateExpense(currentExpense.id, updateReq)
                .onSuccess {
                    isSaving = false
                    onProceedToPreflight(currentExpense.id)
                }
                .onFailure { err ->
                    isSaving = false
                    errorMessage = NetworkConfig.describeConnectionProblem(err)
                }
        }
    }

    ProoflineScaffold(
        title = "Review Extracted Values",
        onBackClick = onBackClick
    ) {
        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = ProoflineColors.Accent)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(ProoflineDimensions.SpacingMd)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = "Verify Receipt Information",
                    style = MaterialTheme.typography.titleLarge
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Check the details read from your receipt and add any required business context.",
                    style = MaterialTheme.typography.bodyMedium
                )

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                // Uncertainty Warning Banner
                val currentExp = expense
                val merchantUncertainty = currentExp?.merchant?.uncertaintyReason
                val amountUncertainty = currentExp?.amount?.uncertaintyReason

                if (!merchantUncertainty.isNullOrBlank() || !amountUncertainty.isNullOrBlank()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
                            .background(ProoflineColors.SurfaceRaised)
                            .border(1.dp, ProoflineColors.SeverityWarning, RoundedCornerShape(ProoflineDimensions.RadiusSm))
                            .padding(ProoflineDimensions.SpacingSm)
                    ) {
                        Column {
                            Text(
                                text = "Uncertain Evidence Detected",
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                                color = ProoflineColors.SeverityWarning
                            )
                            if (!merchantUncertainty.isNullOrBlank()) {
                                Text("• Merchant: $merchantUncertainty", style = MaterialTheme.typography.bodyMedium)
                            }
                            if (!amountUncertainty.isNullOrBlank()) {
                                Text("• Amount: $amountUncertainty", style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                }

                if (errorMessage != null) {
                    ProoflineCard {
                        Text(
                            text = "Error",
                            style = MaterialTheme.typography.headlineMedium,
                            color = ProoflineColors.StatusRejected
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(text = errorMessage ?: "", style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                }

                // Fields
                ProoflineCard(title = "Claim Details") {
                    OutlinedTextField(
                        value = merchant,
                        onValueChange = { merchant = it },
                        label = { Text("Merchant Name") },
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
                            label = { Text("Total Amount") },
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
                        value = date,
                        onValueChange = { date = it },
                        label = { Text("Expense Date (YYYY-MM-DD)") },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = ProoflineColors.Accent,
                            unfocusedBorderColor = ProoflineColors.Border
                        )
                    )

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                    OutlinedTextField(
                        value = category,
                        onValueChange = { category = it },
                        label = { Text("Expense Category (e.g. meal, travel, lodging)") },
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
                }

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                ProoflineCard(title = "Policy Context") {
                    OutlinedTextField(
                        value = clientName,
                        onValueChange = { clientName = it },
                        label = { Text("Client Name (if applicable)") },
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
                    onClick = { saveAndProceed() },
                    enabled = !isSaving,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(ProoflineDimensions.MinTouchTarget),
                    shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                    colors = ButtonDefaults.buttonColors(containerColor = ProoflineColors.Accent)
                ) {
                    if (isSaving) {
                        CircularProgressIndicator(
                            color = ProoflineColors.Text,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = "Check Policy Guidance",
                            fontWeight = FontWeight.SemiBold,
                            color = ProoflineColors.Text
                        )
                    }
                }
            }
        }
    }
}
