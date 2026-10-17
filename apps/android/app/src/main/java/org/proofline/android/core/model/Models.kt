package org.proofline.android.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class EvidencePointer(
    @SerialName("receipt_id") val receiptId: String,
    @SerialName("page") val page: Int = 1,
    @SerialName("region") val region: JsonElement? = null
)

@Serializable
data class FieldValue<T>(
    @SerialName("value") val value: T,
    @SerialName("source") val source: FieldSource,
    @SerialName("reviewed") val reviewed: Boolean = false,
    @SerialName("confidence") val confidence: String? = null,
    @SerialName("evidence") val evidence: EvidencePointer? = null,
    @SerialName("uncertainty_reason") val uncertaintyReason: String? = null
)

/**
 * Lean Money representation. Provenance is tracked by wrapping in FieldValue<Money>.
 * Money values are always decimal strings - never floating-point Double.
 */
@Serializable
data class Money(
    @SerialName("value") val value: String,
    @SerialName("currency") val currency: String
)

@Serializable
data class NonNegativeMoney(
    @SerialName("value") val value: String,
    @SerialName("currency") val currency: String,
    @SerialName("rate") val rate: String? = null,
    @SerialName("rate_date") val rateDate: String? = null,
    @SerialName("rate_source") val rateSource: String? = null
)

@Serializable
data class SourceReference(
    @SerialName("document_id") val documentId: String? = null,
    @SerialName("clause") val clause: String,
    @SerialName("text_excerpt") val textExcerpt: String? = null
)

@Serializable
data class Finding(
    @SerialName("id") val id: String,
    @SerialName("expense_id") val expenseId: String,
    @SerialName("type") val type: FindingType,
    @SerialName("rule_id") val ruleId: String,
    @SerialName("policy_version_id") val policyVersionId: String? = null,
    @SerialName("policy_version_label") val policyVersionLabel: String? = null,
    @SerialName("result") val result: RuleResult,
    @SerialName("severity") val severity: FindingSeverity,
    @SerialName("message") val message: String,
    @SerialName("employee_message") val employeeMessage: String? = null,
    @SerialName("source_reference") val sourceReference: SourceReference? = null,
    @SerialName("evidence") val evidence: JsonElement? = null,
    @SerialName("calculation") val calculation: String? = null,
    @SerialName("expected") val expected: String? = null,
    @SerialName("observed") val observed: String? = null,
    @SerialName("recommended_action") val recommendedAction: RecommendedAction,
    @SerialName("status") val status: FindingStatus,
    @SerialName("expense_version") val expenseVersion: Int,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("superseded_by_finding_id") val supersededByFindingId: String? = null,
    @SerialName("created_at") val createdAt: String
)

@Serializable
data class ReceiptSummary(
    @SerialName("id") val id: String,
    @SerialName("content_url") val contentUrl: String,
    @SerialName("extraction_status") val extractionStatus: ExtractionStatus,
    @SerialName("detected_mime_type") val detectedMimeType: String? = null,
    @SerialName("derivation_type") val derivationType: String = "original",
    @SerialName("uploaded_at") val uploadedAt: String
)

@Serializable
data class LineItem(
    @SerialName("id") val id: String,
    @SerialName("line_number") val lineNumber: Int? = null,
    @SerialName("description") val description: String? = null,
    @SerialName("quantity") val quantity: String? = null,
    @SerialName("unit_amount") val unitAmount: String? = null,
    @SerialName("amount") val amount: String? = null,
    @SerialName("currency") val currency: String? = null,
    @SerialName("tax_amount") val taxAmount: String? = null,
    @SerialName("discount_amount") val discountAmount: String? = null,
    @SerialName("category") val category: String? = null,
    @SerialName("eligibility") val eligibility: LineItemEligibility = LineItemEligibility.NOT_EVALUATED,
    @SerialName("ineligibility_reason") val ineligibilityReason: String? = null
)

@Serializable
data class UserSummary(
    @SerialName("id") val id: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("is_active") val isActive: Boolean = true
)

@Serializable
data class TripSummary(
    @SerialName("id") val id: String,
    @SerialName("purpose") val purpose: String,
    @SerialName("destination_city") val destinationCity: String? = null,
    @SerialName("destination_country_code") val destinationCountryCode: String? = null,
    @SerialName("start_date") val startDate: String? = null,
    @SerialName("end_date") val endDate: String? = null,
    @SerialName("status") val status: String
)

@Serializable
data class Expense(
    @SerialName("id") val id: String,
    @SerialName("version") val version: Int,
    @SerialName("organization_id") val organizationId: String,
    @SerialName("employee") val employee: UserSummary,
    @SerialName("channel") val channel: ExpenseChannel,
    @SerialName("status") val status: ExpenseStatus,
    @SerialName("trip_id") val tripId: String? = null,
    @SerialName("trip") val trip: TripSummary? = null,
    @SerialName("merchant") val merchant: FieldValue<String>,
    @SerialName("expense_date") val expenseDate: FieldValue<String>,
    @SerialName("amount") val amount: FieldValue<Money>,
    @SerialName("receipt_number") val receiptNumber: FieldValue<String>? = null,
    @SerialName("category") val category: String? = null,
    @SerialName("business_purpose") val businessPurpose: String? = null,
    @SerialName("client_name") val clientName: String? = null,
    @SerialName("attendee_count") val attendeeCount: Int? = null,
    @SerialName("amount_reporting") val amountReporting: NonNegativeMoney? = null,
    @SerialName("receipts") val receipts: List<ReceiptSummary> = emptyList(),
    @SerialName("line_items") val lineItems: List<LineItem> = emptyList(),
    @SerialName("findings") val findings: List<Finding> = emptyList(),
    @SerialName("evaluated_policy_version_id") val evaluatedPolicyVersionId: String? = null,
    @SerialName("submitted_at") val submittedAt: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String
)

@Serializable
data class PageInfo(
    @SerialName("limit") val limit: Int = 50,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("total") val total: Int? = null
)

@Serializable
data class ExpenseSummary(
    @SerialName("id") val id: String,
    @SerialName("version") val version: Int,
    @SerialName("employee") val employee: UserSummary,
    @SerialName("channel") val channel: ExpenseChannel,
    @SerialName("status") val status: ExpenseStatus,
    @SerialName("merchant") val merchant: String? = null,
    @SerialName("expense_date") val expenseDate: String? = null,
    @SerialName("amount") val amount: Money,
    @SerialName("category") val category: String? = null,
    @SerialName("trip_id") val tripId: String? = null,
    @SerialName("receipt_count") val receiptCount: Int = 0,
    @SerialName("open_finding_count") val openFindingCount: Int = 0,
    @SerialName("blocking_finding_count") val blockingFindingCount: Int = 0,
    @SerialName("open_duplicate_candidate_count") val openDuplicateCandidateCount: Int = 0,
    @SerialName("submitted_at") val submittedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String
)

@Serializable
data class ExpenseListResponse(
    @SerialName("items") val items: List<ExpenseSummary> = emptyList(),
    @SerialName("page") val page: PageInfo = PageInfo()
)

@Serializable
data class CreateExpenseRequest(
    @SerialName("employee_membership_id") val employeeMembershipId: String? = null,
    @SerialName("channel") val channel: ExpenseChannel = ExpenseChannel.ANDROID,
    @SerialName("trip_id") val tripId: String? = null,
    @SerialName("merchant") val merchant: String? = null,
    @SerialName("expense_date") val expenseDate: String? = null,
    @SerialName("amount") val amount: String? = null,
    @SerialName("currency") val currency: String? = null,
    @SerialName("category") val category: String? = null,
    @SerialName("business_purpose") val businessPurpose: String? = null,
    @SerialName("client_name") val clientName: String? = null,
    @SerialName("attendee_count") val attendeeCount: Int? = null
)

@Serializable
data class UpdateExpenseRequest(
    @SerialName("expected_version") val expectedVersion: Int,
    @SerialName("merchant") val merchant: String? = null,
    @SerialName("expense_date") val expenseDate: String? = null,
    @SerialName("amount") val amount: String? = null,
    @SerialName("currency") val currency: String? = null,
    @SerialName("category") val category: String? = null,
    @SerialName("business_purpose") val businessPurpose: String? = null,
    @SerialName("client_name") val clientName: String? = null,
    @SerialName("attendee_count") val attendeeCount: Int? = null,
    @SerialName("trip_id") val tripId: String? = null
)

@Serializable
data class PolicyCheckResponse(
    @SerialName("findings") val findings: List<Finding> = emptyList(),
    @SerialName("overall_result") val overallResult: RuleResult = RuleResult.UNKNOWN
)

@Serializable
data class ApiErrorDetail(
    @SerialName("location") val location: List<String> = emptyList(),
    @SerialName("message") val message: String,
    @SerialName("type") val type: String? = null
)

@Serializable
data class ApiErrorPayload(
    @SerialName("code") val code: String,
    @SerialName("message") val message: String,
    @SerialName("details") val details: List<ApiErrorDetail> = emptyList(),
    @SerialName("request_id") val requestId: String? = null
)

@Serializable
data class ApiErrorEnvelope(
    @SerialName("error") val error: ApiErrorPayload
)
