package org.proofline.android.core.model

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelSerializationTest {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    @Test
    fun testMoneyDecimalStringPreservation() {
        // Lean Money model wrapped in FieldValue for provenance tracking
        val money = Money(
            value = "1400.50",
            currency = "INR"
        )
        val fieldMoney = FieldValue(
            value = money,
            source = FieldSource.RECEIPT_EXTRACTION,
            reviewed = true
        )

        val serialized = json.encodeToString(fieldMoney)
        assertTrue(serialized.contains("\"value\":\"1400.50\""))
        assertTrue(serialized.contains("\"currency\":\"INR\""))
        assertTrue(serialized.contains("\"source\":\"receipt_extraction\""))

        val deserialized = json.decodeFromString<FieldValue<Money>>(serialized)
        assertEquals("1400.50", deserialized.value.value)
        assertEquals("INR", deserialized.value.currency)
        assertEquals(FieldSource.RECEIPT_EXTRACTION, deserialized.source)
    }

    @Test
    fun testFindingSerialization() {
        val rawJson = """
        {
            "id": "0198f2b4-0000-0000-0000-000000000001",
            "expense_id": "0198f2b4-0000-0000-0000-000000000002",
            "type": "individual_limit_exceeded",
            "rule_id": "rule_daily_dinner_cap",
            "policy_version_id": "0198f2b4-0000-0000-0000-000000000003",
            "policy_version_label": "FY2026-V1",
            "result": "FAIL",
            "severity": "blocking",
            "message": "Dinner limit exceeded by ₹400.00",
            "employee_message": "Daily dinner limit is ₹1000.00. This claim is for ₹1400.00.",
            "source_reference": {
                "document_id": "doc_pol_2026_01",
                "clause": "4.2(b)",
                "text_excerpt": "Dinner per diem capped at 1000 INR"
            },
            "evidence": null,
            "calculation": "1400.00 - 1000.00 = 400.00 excess",
            "expected": "<= 1000.00 INR",
            "observed": "1400.00 INR",
            "recommended_action": "request_correction",
            "status": "open",
            "expense_version": 2,
            "created_at": "2026-10-18T00:00:00Z"
        }
        """.trimIndent()

        val finding = json.decodeFromString<Finding>(rawJson)
        assertEquals("0198f2b4-0000-0000-0000-000000000001", finding.id)
        assertEquals(FindingType.INDIVIDUAL_LIMIT_EXCEEDED, finding.type)
        assertEquals(RuleResult.FAIL, finding.result)
        assertEquals(FindingSeverity.BLOCKING, finding.severity)
        assertEquals(RecommendedAction.REQUEST_CORRECTION, finding.recommendedAction)
        assertEquals(FindingStatus.OPEN, finding.status)
        assertEquals("4.2(b)", finding.sourceReference?.clause)
        assertEquals("doc_pol_2026_01", finding.sourceReference?.documentId)
        assertEquals("Dinner per diem capped at 1000 INR", finding.sourceReference?.textExcerpt)
        assertEquals("1400.00 INR", finding.observed)
    }

    @Test
    fun testExpenseSerialization() {
        val rawJson = """
        {
            "id": "0198f2b4-0000-0000-0000-000000000010",
            "version": 3,
            "organization_id": "0198f2b4-0000-0000-0000-000000000011",
            "employee": {
                "id": "0198f2b4-0000-0000-0000-000000000012",
                "display_name": "Demo Employee",
                "is_active": true
            },
            "channel": "android",
            "status": "needs_info",
            "trip_id": null,
            "merchant": {
                "value": "Central Bistro",
                "source": "receipt_extraction",
                "reviewed": false
            },
            "expense_date": {
                "value": "2026-10-17",
                "source": "receipt_extraction",
                "reviewed": true
            },
            "amount": {
                "value": {
                    "value": "850.00",
                    "currency": "INR"
                },
                "source": "receipt_extraction",
                "reviewed": true
            },
            "category": "meal",
            "business_purpose": "Client meeting",
            "receipts": [],
            "line_items": [],
            "findings": [],
            "created_at": "2026-10-17T12:00:00Z",
            "updated_at": "2026-10-17T12:05:00Z"
        }
        """.trimIndent()

        val expense = json.decodeFromString<Expense>(rawJson)
        assertEquals("0198f2b4-0000-0000-0000-000000000010", expense.id)
        assertEquals(3, expense.version)
        assertEquals(ExpenseChannel.ANDROID, expense.channel)
        assertEquals(ExpenseStatus.NEEDS_INFO, expense.status)
        assertEquals("Central Bistro", expense.merchant.value)
        assertEquals("850.00", expense.amount.value.value)
        assertEquals("INR", expense.amount.value.currency)
    }

    @Test
    fun testApiErrorEnvelope() {
        val rawJson = """
        {
            "error": {
                "code": "STALE_VERSION",
                "message": "The expense has been modified since it was loaded.",
                "details": [
                    { "location": ["body", "expected_version"], "message": "Expected version 1 but found 2." }
                ],
                "request_id": "req_123456"
            }
        }
        """.trimIndent()

        val envelope = json.decodeFromString<ApiErrorEnvelope>(rawJson)
        assertEquals("STALE_VERSION", envelope.error.code)
        assertEquals("req_123456", envelope.error.requestId)
        assertEquals(1, envelope.error.details.size)
        assertEquals("Expected version 1 but found 2.", envelope.error.details[0].message)
    }
}
