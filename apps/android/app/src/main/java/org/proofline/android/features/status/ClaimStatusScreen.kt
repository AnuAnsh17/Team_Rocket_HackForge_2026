package org.proofline.android.features.status

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import kotlinx.coroutines.launch
import org.proofline.android.core.designsystem.EmployeeNoticeState
import org.proofline.android.core.designsystem.EmployeeStateBanner
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.designsystem.ResultPill
import org.proofline.android.core.designsystem.StatusPill
import org.proofline.android.core.model.Expense
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun ClaimStatusScreen(
    expenseId: String,
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onNavigateToCorrection: (expenseId: String) -> Unit
) {
    var expense by remember { mutableStateOf<Expense?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun loadExpense() {
        scope.launch {
            isLoading = true
            errorMessage = null
            apiClient.getExpense(expenseId)
                .onSuccess { exp ->
                    expense = exp
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

    ProoflineScaffold(
        title = "Claim Status",
        onBackClick = onBackClick
    ) {
        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = ProoflineColors.Accent)
            }
        } else if (errorMessage != null) {
            Box(modifier = Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
                ProoflineCard {
                    Text("Connection Notice", style = MaterialTheme.typography.headlineMedium, color = ProoflineColors.StatusNeedsInfo)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(errorMessage ?: "", style = MaterialTheme.typography.bodyMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(onClick = { loadExpense() }) {
                        Text("Retry")
                    }
                }
            }
        } else {
            val exp = expense
            if (exp != null) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(ProoflineDimensions.SpacingMd)
                        .verticalScroll(rememberScrollState())
                ) {
                    // Header Row
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = exp.merchant.value,
                                style = MaterialTheme.typography.titleLarge
                            )
                            Text(
                                text = "Submitted on ${exp.submittedAt?.take(10) ?: exp.createdAt.take(10)}",
                                style = MaterialTheme.typography.labelSmall
                            )
                        }
                        IconButton(onClick = { loadExpense() }) {
                            Icon(imageVector = Icons.Default.Refresh, contentDescription = "Refresh status")
                        }
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    // Status and State Banner
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${exp.amount.value.currency} ${exp.amount.value.value}",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold
                        )
                        StatusPill(status = exp.status)
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    when (exp.status) {
                        ExpenseStatus.NEEDS_INFO -> {
                            EmployeeStateBanner(state = EmployeeNoticeState.NEEDS_INFO)
                            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                            Button(
                                onClick = { onNavigateToCorrection(expenseId) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(ProoflineDimensions.MinTouchTarget),
                                shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                                colors = ButtonDefaults.buttonColors(containerColor = ProoflineColors.StatusNeedsInfo)
                            ) {
                                Icon(imageVector = Icons.Default.Edit, contentDescription = null)
                                Spacer(modifier = Modifier.padding(4.dp))
                                Text("Provide Requested Details", fontWeight = FontWeight.Bold, color = ProoflineColors.Surface)
                            }
                        }
                        ExpenseStatus.REJECTED -> {
                            EmployeeStateBanner(state = EmployeeNoticeState.POLICY_ISSUE)
                        }
                        ExpenseStatus.IN_REVIEW, ExpenseStatus.SUBMITTED -> {
                            EmployeeStateBanner(state = EmployeeNoticeState.IN_REVIEW)
                        }
                        else -> {}
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    // Details Card
                    ProoflineCard(title = "Claim Summary") {
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Category", color = ProoflineColors.TextMuted)
                            Text(exp.category ?: "Uncategorized", fontWeight = FontWeight.Medium)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Expense Date", color = ProoflineColors.TextMuted)
                            Text(exp.expenseDate.value, fontWeight = FontWeight.Medium)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Version", color = ProoflineColors.TextMuted)
                            Text("v${exp.version}", fontWeight = FontWeight.Medium)
                        }
                        if (!exp.businessPurpose.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Purpose", color = ProoflineColors.TextMuted)
                                Text(exp.businessPurpose, fontWeight = FontWeight.Medium)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                    // Policy Findings
                    if (exp.findings.isNotEmpty()) {
                        Text(
                            text = "Auditor Findings",
                            style = MaterialTheme.typography.titleLarge
                        )
                        Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                        Column(verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)) {
                            exp.findings.forEach { finding ->
                                ProoflineCard {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(finding.ruleId, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                                        ResultPill(result = finding.result)
                                    }
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = finding.employeeMessage ?: finding.message,
                                        style = MaterialTheme.typography.bodyLarge,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    if (finding.sourceReference != null) {
                                        Spacer(modifier = Modifier.height(2.dp))
                                        Text(
                                            text = "Clause: ${finding.sourceReference.clause}${if (!finding.sourceReference.textExcerpt.isNullOrBlank()) " - ${finding.sourceReference.textExcerpt}" else ""}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = ProoflineColors.Accent
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
}
