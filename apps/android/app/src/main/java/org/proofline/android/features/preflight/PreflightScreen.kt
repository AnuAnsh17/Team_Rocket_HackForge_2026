package org.proofline.android.features.preflight

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.designsystem.ResultPill
import org.proofline.android.core.model.Finding
import org.proofline.android.core.model.RuleResult
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun PreflightScreen(
    expenseId: String,
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onProceedToSubmit: (expenseId: String) -> Unit
) {
    var findings by remember { mutableStateOf<List<Finding>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(expenseId) {
        isLoading = true
        errorMessage = null
        apiClient.checkPolicy(expenseId)
            .onSuccess { res ->
                findings = res.findings
                isLoading = false
            }
            .onFailure { err ->
                // If policy endpoint not yet wired on backend or returns empty, load expense findings
                apiClient.getExpense(expenseId)
                    .onSuccess { exp ->
                        findings = exp.findings
                        isLoading = false
                    }
                    .onFailure { fallbackErr ->
                        errorMessage = NetworkConfig.describeConnectionProblem(fallbackErr)
                        isLoading = false
                    }
            }
    }

    ProoflineScaffold(
        title = "Policy Guidance",
        onBackClick = onBackClick
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(ProoflineDimensions.SpacingMd),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                // Advisory Notice Banner
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
                        .background(ProoflineColors.SurfaceRaised)
                        .border(1.dp, ProoflineColors.Accent, RoundedCornerShape(ProoflineDimensions.RadiusSm))
                        .padding(ProoflineDimensions.SpacingSm)
                ) {
                    Row(verticalAlignment = Alignment.Top) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Advisory",
                            tint = ProoflineColors.Accent,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.padding(4.dp))
                        Column {
                            Text(
                                text = "Pre-flight Guidance (Advisory Only)",
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                                color = ProoflineColors.Accent
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "This is preliminary guidance based on current claim details. Aggregate limits, concurrent claims, or finance reviewer verification can change the outcome upon final submission.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = ProoflineColors.TextMuted,
                                fontSize = 13.sp
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                Text(
                    text = "Policy Rule Breakdown",
                    style = MaterialTheme.typography.titleLarge
                )

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))

                when {
                    isLoading -> {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(200.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = ProoflineColors.Accent)
                        }
                    }
                    errorMessage != null -> {
                        ProoflineCard {
                            Text(
                                text = "Notice",
                                style = MaterialTheme.typography.headlineMedium,
                                color = ProoflineColors.StatusNeedsInfo
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(text = errorMessage ?: "", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    findings.isEmpty() -> {
                        ProoflineCard {
                            Text(
                                text = "No Policy Exceptions Detected",
                                style = MaterialTheme.typography.headlineMedium,
                                color = ProoflineColors.ResultPass
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "All required receipt fields appear complete. You may proceed with submission.",
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                    else -> {
                        LazyColumn(
                            verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)
                        ) {
                            items(findings, key = { it.id }) { finding ->
                                ProoflineCard {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = finding.ruleId,
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold
                                        )
                                        ResultPill(result = finding.result)
                                    }

                                    Spacer(modifier = Modifier.height(4.dp))

                                    Text(
                                        text = finding.employeeMessage ?: finding.message,
                                        style = MaterialTheme.typography.bodyLarge,
                                        fontWeight = FontWeight.SemiBold
                                    )

                                    if (finding.sourceReference != null) {
                                        Spacer(modifier = Modifier.height(4.dp))
                                        Text(
                                            text = "Source Clause: ${finding.sourceReference.clause}${if (!finding.sourceReference.textExcerpt.isNullOrBlank()) " - ${finding.sourceReference.textExcerpt}" else ""}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = ProoflineColors.Accent
                                        )
                                    }

                                    if (!finding.calculation.isNullOrBlank()) {
                                        Spacer(modifier = Modifier.height(4.dp))
                                        Text(
                                            text = "Calculation: ${finding.calculation}",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = ProoflineColors.TextMuted
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

            Button(
                onClick = { onProceedToSubmit(expenseId) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(ProoflineDimensions.MinTouchTarget),
                shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                colors = ButtonDefaults.buttonColors(containerColor = ProoflineColors.Accent)
            ) {
                Text(
                    text = "Proceed to Submit Claim",
                    fontWeight = FontWeight.SemiBold,
                    color = ProoflineColors.Text
                )
            }
        }
    }
}
