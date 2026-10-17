package org.proofline.android.core.designsystem

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.model.RuleResult

object ProoflineColors {
    val Surface = Color(0xFF0B1020)
    val SurfaceMuted = Color(0xFF161C2F)
    val SurfaceRaised = Color(0xFF111726)
    val Border = Color(0xFF26304A)
    val BorderStrong = Color(0xFF38446A)
    val Text = Color(0xFFE8ECF8)
    val TextMuted = Color(0xFF97A2C0)
    val Accent = Color(0xFF5B8CFF)

    val StatusDraft = Color(0xFF6B7691)
    val StatusSubmitted = Color(0xFF4A8FE7)
    val StatusNeedsInfo = Color(0xFFE0A33A)
    val StatusInReview = Color(0xFF8B7CF0)
    val StatusApproved = Color(0xFF3FA87A)
    val StatusRejected = Color(0xFFD4665F)
    val StatusWithdrawn = Color(0xFF6B7691)

    val SeverityInfo = Color(0xFF4A8FE7)
    val SeverityWarning = Color(0xFFE0A33A)
    val SeverityBlocking = Color(0xFFD4665F)

    val ResultPass = Color(0xFF3FA87A)
    val ResultFail = Color(0xFFD4665F)
    val ResultUnknown = Color(0xFF8B7CF0)
}

object ProoflineDimensions {
    val SpacingXs = 4.dp
    val SpacingSm = 8.dp
    val SpacingMd = 16.dp
    val SpacingLg = 24.dp
    val SpacingXl = 32.dp

    val RadiusSm = 6.dp
    val RadiusMd = 12.dp
    val RadiusLg = 16.dp

    val MinTouchTarget = 48.dp
}

object ProoflineWording {
    /**
     * Wording requirement: "Not reimbursed" rather than "Rejected".
     * An employee reading this on mobile must not be accused of wrongdoing.
     */
    fun statusLabel(status: ExpenseStatus): String = when (status) {
        ExpenseStatus.DRAFT -> "Draft"
        ExpenseStatus.SUBMITTED -> "Submitted"
        ExpenseStatus.NEEDS_INFO -> "Needs information"
        ExpenseStatus.IN_REVIEW -> "Under review"
        ExpenseStatus.APPROVED -> "Approved"
        ExpenseStatus.REJECTED -> "Not reimbursed"
        ExpenseStatus.WITHDRAWN -> "Withdrawn"
    }

    fun statusColor(status: ExpenseStatus): Color = when (status) {
        ExpenseStatus.DRAFT -> ProoflineColors.StatusDraft
        ExpenseStatus.SUBMITTED -> ProoflineColors.StatusSubmitted
        ExpenseStatus.NEEDS_INFO -> ProoflineColors.StatusNeedsInfo
        ExpenseStatus.IN_REVIEW -> ProoflineColors.StatusInReview
        ExpenseStatus.APPROVED -> ProoflineColors.StatusApproved
        ExpenseStatus.REJECTED -> ProoflineColors.StatusRejected
        ExpenseStatus.WITHDRAWN -> ProoflineColors.StatusWithdrawn
    }

    /**
     * Tri-state rule outcome labels.
     * UNKNOWN is never treated as a pass and never as an accusation.
     */
    fun resultLabel(result: RuleResult): String = when (result) {
        RuleResult.PASS -> "Meets the policy"
        RuleResult.FAIL -> "Does not meet the policy"
        RuleResult.UNKNOWN -> "We could not confirm this yet"
    }

    fun resultColor(result: RuleResult): Color = when (result) {
        RuleResult.PASS -> ProoflineColors.ResultPass
        RuleResult.FAIL -> ProoflineColors.ResultFail
        RuleResult.UNKNOWN -> ProoflineColors.ResultUnknown
    }
}

val ProoflineTypography = Typography(
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 22.sp,
        lineHeight = 28.sp,
        color = ProoflineColors.Text
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 24.sp,
        color = ProoflineColors.Text
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 15.sp,
        lineHeight = 20.sp,
        color = ProoflineColors.Text
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 18.sp,
        color = ProoflineColors.TextMuted
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        color = ProoflineColors.TextMuted
    )
)

private val DarkColorScheme = darkColorScheme(
    primary = ProoflineColors.Accent,
    onPrimary = Color.White,
    surface = ProoflineColors.Surface,
    onSurface = ProoflineColors.Text,
    surfaceVariant = ProoflineColors.SurfaceMuted,
    onSurfaceVariant = ProoflineColors.TextMuted,
    outline = ProoflineColors.Border,
    outlineVariant = ProoflineColors.BorderStrong,
    background = ProoflineColors.Surface,
    onBackground = ProoflineColors.Text
)

@Composable
fun ProoflineTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = ProoflineTypography,
        content = content
    )
}
