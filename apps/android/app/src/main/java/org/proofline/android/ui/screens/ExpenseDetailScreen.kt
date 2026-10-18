package org.proofline.android.ui.screens

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.proofline.android.core.designsystem.ProoflineWording
import org.proofline.android.data.model.Expense
import org.proofline.android.data.model.Finding
import org.proofline.android.ui.viewmodel.ExpenseDetailState

/**
 * One claim, read from the backend.
 *
 * What was removed here and why: this screen used to print
 * `Status: Submitted / In Review` and `Secure Bill Viewer: Authorized stream
 * ready.` as literal strings, without asking the backend anything. Both were
 * fabricated claims about a real expense. Now every line shown comes from the
 * fetched record, and the states that are not known are shown as unknown:
 * "Could not load" is a truthful answer, a made-up status is not.
 *
 * Receipt images are not fetched or displayed by this build, and the screen says
 * so rather than implying an authorized stream exists.
 */
@Composable
fun ExpenseDetailScreen(
    expenseId: String,
    state: ExpenseDetailState,
    onLoad: (String) -> Unit,
    onBack: () -> Unit
) {
    LaunchedEffect(expenseId) { onLoad(expenseId) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "Claim Details",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        when {
            state.isLoading -> Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(96.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(modifier = Modifier.size(28.dp))
            }

            state.expense != null -> ExpenseFields(state.expense)

            else -> Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "This claim could not be loaded",
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    Text(
                        text = state.errorMessage
                            ?: "The backend returned no record for this claim.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                }
            }
        }

        Text(
            text = "Claim ID: $expenseId",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Button(onClick = onBack) {
            Text("Back to List")
        }
    }
}

@Composable
private fun ExpenseFields(expense: Expense) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Field("Status", ProoflineWording.statusLabelOrUnknown(expense.status))
            Field("Version", expense.version.toString())
            Field("Channel", expense.channel)
            Field("Merchant", expense.merchant?.value ?: "Not provided")
            Field("Date", expense.expense_date?.value ?: "Not provided")
            Field(
                "Amount",
                expense.amount?.value?.let { "${it.value} ${it.currency}" } ?: "Not provided"
            )
            Field("Category", expense.category ?: "Not provided")
            Field("Business purpose", expense.business_purpose ?: "Not provided")
            Field("Created", expense.created_at)
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Policy findings (${expense.findings.size})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            HorizontalDivider()
            if (expense.findings.isEmpty()) {
                Text(
                    text = "The backend reported no findings for this claim. That is what the " +
                        "server returned, not an assessment made on this device.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                expense.findings.forEach { FindingRow(it) }
            }
        }
    }

    Text(
        text = "Receipt images are not fetched or displayed by this build.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
}

@Composable
private fun FindingRow(finding: Finding) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = ProoflineWording.resultLabelOrRaw(finding.result),
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold
        )
        Text(
            text = "${finding.severity.uppercase()} — ${finding.message}",
            style = MaterialTheme.typography.bodySmall
        )
        finding.source_reference?.let { reference ->
            Text(
                text = "Policy ${reference.clause}: ${reference.text_excerpt}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
    }
}

@Composable
private fun Field(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium
        )
    }
}
