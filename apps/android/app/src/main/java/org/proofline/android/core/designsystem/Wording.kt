package org.proofline.android.core.designsystem

import androidx.compose.ui.graphics.Color
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.model.RuleResult

/**
 * Proofline status palette.
 *
 * Ported from the `mobile-app-prior` branch. Kept in the `core` package so both
 * the design system and the wording rules can be unit tested on the JVM without
 * a device.
 */
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
    val ResultUnknown = Color(0xFF97A2C0)
}

/**
 * Employee-facing wording rules.
 *
 * Two rules are load-bearing and are asserted by `WordingComplianceTest`:
 *
 *  1. A rejected claim is described as "Not reimbursed"; the employee is never
 *     told they were rejected, and the copy never accuses them of anything.
 *  2. `RuleResult.UNKNOWN` is a first-class outcome, worded so it cannot be read
 *     as either a pass or a failure.
 */
object ProoflineWording {

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

    /**
     * Label for a raw status string coming off the wire.
     *
     * An unrecognised status is reported as unknown rather than being mapped to
     * a plausible-looking status, which would be a fabricated claim.
     */
    fun statusLabelOrUnknown(rawStatus: String?): String {
        val status = ExpenseStatus.entries.firstOrNull { it.name.lowercase() == rawStatus?.lowercase() }
            ?: return "Status unavailable"
        return statusLabel(status)
    }

    /**
     * Label for a raw rule result coming off the wire.
     *
     * An unrecognised result keeps the server's own token in the message rather
     * than being rounded to a pass or a failure.
     */
    fun resultLabelOrRaw(rawResult: String?): String {
        val result = RuleResult.entries.firstOrNull { it.name.equals(rawResult, ignoreCase = true) }
            ?: return "Outcome unavailable (server said '${rawResult ?: "nothing"}')"
        return resultLabel(result)
    }
}
