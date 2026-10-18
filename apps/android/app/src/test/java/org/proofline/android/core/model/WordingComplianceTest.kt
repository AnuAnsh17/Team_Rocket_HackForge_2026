package org.proofline.android.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.proofline.android.core.designsystem.ProoflineWording

class WordingComplianceTest {

    @Test
    fun testRejectedWordingIsNotAccusatory() {
        val label = ProoflineWording.statusLabel(ExpenseStatus.REJECTED)
        assertEquals("Not reimbursed", label)
        assertFalse(label.equals("Rejected", ignoreCase = true))
    }

    @Test
    fun testUnknownResultWordingIsFirstClass() {
        val label = ProoflineWording.resultLabel(RuleResult.UNKNOWN)
        assertEquals("We could not confirm this yet", label)
        assertFalse(label.contains("pass", ignoreCase = true))
        assertFalse(label.contains("fail", ignoreCase = true))
    }

    @Test
    fun testEmployeeCopyContainsNoAccusatoryTerms() {
        val forbiddenTerms = listOf("fraud", "violat", "guilty", "cheat", "scam", "illegal", "liar", "penal")

        val allStatusLabels = ExpenseStatus.entries.map { ProoflineWording.statusLabel(it) }
        val allResultLabels = RuleResult.entries.map { ProoflineWording.resultLabel(it) }

        for (text in allStatusLabels + allResultLabels) {
            for (term in forbiddenTerms) {
                assertFalse(
                    "Employee copy '$text' must not contain accusatory term '$term'",
                    text.contains(term, ignoreCase = true)
                )
            }
        }
    }
}
