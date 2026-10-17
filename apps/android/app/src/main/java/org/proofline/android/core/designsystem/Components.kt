package org.proofline.android.core.designsystem

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.model.RuleResult
import org.proofline.android.core.network.NetworkConfig

@Composable
fun DemoModeBanner(
    modifier: Modifier = Modifier
) {
    if (NetworkConfig.isDemoMode) {
        Box(
            modifier = modifier
                .fillMaxWidth()
                .background(Color(0xFF2E240D))
                .border(1.dp, ProoflineColors.SeverityWarning)
                .padding(horizontal = 12.dp, vertical = 6.dp)
        ) {
            Column {
                Text(
                    text = "DEMO MODE — Simulated Actor Identity",
                    color = ProoflineColors.SeverityWarning,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "Actor: ${NetworkConfig.demoActorId.take(13)}... | Backend: ${NetworkConfig.baseUrl}",
                    color = ProoflineColors.TextMuted,
                    fontSize = 10.sp
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProoflineScaffold(
    title: String,
    onBackClick: (() -> Unit)? = null,
    floatingActionButton: @Composable () -> Unit = {},
    content: @Composable () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge
                    )
                },
                    navigationIcon = {
                        if (onBackClick != null) {
                            IconButton(onClick = onBackClick) {
                                Icon(
                                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                    contentDescription = "Navigate back",
                                    tint = ProoflineColors.Text
                                )
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = ProoflineColors.SurfaceRaised,
                        titleContentColor = ProoflineColors.Text
                    )
                )
        },
        floatingActionButton = floatingActionButton,
        containerColor = ProoflineColors.Surface
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            content()
        }
    }
}

@Composable
fun ProoflineCard(
    modifier: Modifier = Modifier,
    title: String? = null,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(ProoflineDimensions.RadiusMd))
            .background(ProoflineColors.SurfaceMuted)
            .border(1.dp, ProoflineColors.Border, RoundedCornerShape(ProoflineDimensions.RadiusMd))
            .padding(ProoflineDimensions.SpacingMd)
    ) {
        Column {
            if (title != null) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.padding(bottom = ProoflineDimensions.SpacingSm)
                )
            }
            content()
        }
    }
}

@Composable
fun StatusPill(
    status: ExpenseStatus,
    modifier: Modifier = Modifier
) {
    val color = ProoflineWording.statusColor(status)
    val label = ProoflineWording.statusLabel(status)

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .background(ProoflineColors.SurfaceRaised)
            .border(1.dp, color, RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(color)
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = label,
            color = ProoflineColors.Text,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
fun ResultPill(
    result: RuleResult,
    modifier: Modifier = Modifier
) {
    val color = ProoflineWording.resultColor(result)
    val label = ProoflineWording.resultLabel(result)

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .background(ProoflineColors.SurfaceRaised)
            .border(1.dp, color, RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(color)
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = label,
            color = ProoflineColors.Text,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

enum class EmployeeNoticeState {
    NEEDS_INFO,
    POLICY_ISSUE,
    POSSIBLE_DUPLICATE,
    IN_REVIEW
}

@Composable
fun EmployeeStateBanner(
    state: EmployeeNoticeState,
    modifier: Modifier = Modifier
) {
    val (title, body, color) = when (state) {
        EmployeeNoticeState.NEEDS_INFO -> Triple(
            "We need something from you",
            "Finance has asked for information that is missing from this claim. Add it and we will re-check the claim.",
            ProoflineColors.StatusNeedsInfo
        )
        EmployeeNoticeState.POLICY_ISSUE -> Triple(
            "This claim does not meet the policy",
            "A policy rule that applies to this claim is not satisfied. You can see the clause and calculation, and submit corrections.",
            ProoflineColors.StatusRejected
        )
        EmployeeNoticeState.POSSIBLE_DUPLICATE -> Triple(
            "This might have been submitted twice",
            "We found another claim that looks similar. A person will check it; nothing is assumed, and you do not need to do anything yet.",
            ProoflineColors.SeverityWarning
        )
        EmployeeNoticeState.IN_REVIEW -> Triple(
            "A person is reviewing this",
            "The claim is with finance. You will see a status update once a decision is made.",
            ProoflineColors.StatusInReview
        )
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .background(ProoflineColors.SurfaceMuted)
            .border(1.dp, ProoflineColors.Border, RoundedCornerShape(ProoflineDimensions.RadiusSm))
            .padding(start = 4.dp)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .border(2.dp, color, RoundedCornerShape(topStart = ProoflineDimensions.RadiusSm, bottomStart = ProoflineDimensions.RadiusSm))
                .padding(ProoflineDimensions.SpacingSm)
        ) {
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = color
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = body,
                    style = MaterialTheme.typography.bodyMedium,
                    color = ProoflineColors.TextMuted
                )
            }
        }
    }
}
