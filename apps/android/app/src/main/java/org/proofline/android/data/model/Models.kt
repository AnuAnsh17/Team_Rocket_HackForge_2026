package org.proofline.android.data.model

import com.google.gson.*
import java.lang.reflect.Type

data class UserSummary(
    val id: String,
    val display_name: String,
    val is_active: Boolean
)

data class MembershipSummary(
    val id: String,
    val organization_id: String,
    val user: UserSummary,
    val employee_code: String?,
    val status: String,
    val manager_membership_id: String?,
    val joined_on: String?
)

data class Money(val value: String, val currency: String)

class MoneyDeserializer : JsonDeserializer<Money> {
    override fun deserialize(json: JsonElement, typeOfT: Type, context: JsonDeserializationContext): Money {
        if (!json.isJsonObject) {
            throw JsonParseException("Expected JSON object for Money")
        }
        val obj = json.asJsonObject
        val valueElement = obj.get("value")
        if (valueElement == null || !valueElement.isJsonPrimitive || !valueElement.asJsonPrimitive.isString) {
            throw JsonParseException("Money value must be a decimal string, numbers are rejected per API contract")
        }
        val currencyElement = obj.get("currency")
        val currency = if (currencyElement != null && currencyElement.isJsonPrimitive) currencyElement.asString else "INR"
        return Money(value = valueElement.asString, currency = currency)
    }
}

data class EvidenceRef(
    val receipt_id: String?,
    val page: Int?,
    val region: List<Double>?
)

data class FieldValue<T>(
    val value: T?,
    val source: String,
    val reviewed: Boolean,
    val confidence: Double?,
    val evidence: EvidenceRef?,
    val uncertainty_reason: String?
)

data class SourceReference(
    val document_id: String,
    val clause: String,
    val text_excerpt: String
)

data class Finding(
    val id: String,
    val type: String,
    val rule_id: String,
    val policy_version: String,
    val result: String,
    val severity: String,
    val message: String,
    val source_reference: SourceReference?,
    val recommended_action: String?,
    val status: String,
    val created_at: String
)

data class Expense(
    val id: String,
    val version: Int,
    val status: String,
    val channel: String,
    val merchant: FieldValue<String>?,
    val expense_date: FieldValue<String>?,
    val amount: FieldValue<Money>?,
    val category: String?,
    val business_purpose: String?,
    val findings: List<Finding>,
    val created_at: String
)

data class PageInfo(
    val limit: Int,
    val next_cursor: String?,
    val total: Int
)

data class ExpenseListResponse(
    val items: List<Expense>,
    val page: PageInfo
)

data class ApiErrorEnvelope(
    val error: ApiError
)

data class ApiError(
    val code: String,
    val message: String
)

data class DemoSeedResponse(
    val organization_id: String,
    val message: String
)
