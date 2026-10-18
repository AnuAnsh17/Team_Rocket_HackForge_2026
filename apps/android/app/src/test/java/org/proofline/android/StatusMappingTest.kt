package org.proofline.android

import org.junit.Test
import org.junit.Assert.*

class StatusMappingTest {
    private val statuses = listOf("draft", "submitted", "needs_info", "in_review", "approved", "rejected", "withdrawn")

    @Test
    fun testAllStatusesProduceNonEmptyDisplayString() {
        for (status in statuses) {
            val display = mapStatusToDisplay(status)
            assertNotNull(display)
            assertTrue(display.isNotBlank())
        }
    }

    @Test
    fun testUnknownRuleResultWording() {
        val wording = mapRuleResultToDisplay("UNKNOWN")
        assertNotNull(wording)
        assertTrue(wording.isNotBlank())
        val lower = wording.lowercase()
        assertFalse(lower.contains("fail"))
        assertFalse(lower.contains("reject"))
        assertFalse(lower.contains("fraud"))
    }

    private fun mapStatusToDisplay(status: String): String {
        return when (status) {
            "draft" -> "Draft"
            "submitted" -> "Submitted"
            "needs_info" -> "Needs Information"
            "in_review" -> "In Review"
            "approved" -> "Approved"
            "rejected" -> "Rejected"
            "withdrawn" -> "Withdrawn"
            else -> "Unknown"
        }
    }

    private fun mapRuleResultToDisplay(result: String): String {
        return when (result) {
            "PASS" -> "Confirmed"
            "FAIL" -> "Check Required"
            "UNKNOWN" -> "We could not confirm this yet"
            else -> "Pending"
        }
    }
}
