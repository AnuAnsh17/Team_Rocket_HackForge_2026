package org.proofline.android.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
enum class ExpenseStatus {
    @SerialName("draft") DRAFT,
    @SerialName("submitted") SUBMITTED,
    @SerialName("needs_info") NEEDS_INFO,
    @SerialName("in_review") IN_REVIEW,
    @SerialName("approved") APPROVED,
    @SerialName("rejected") REJECTED,
    @SerialName("withdrawn") WITHDRAWN
}

@Serializable
enum class ExpenseChannel {
    @SerialName("android") ANDROID,
    @SerialName("web") WEB,
    @SerialName("bulk") BULK,
    @SerialName("email_simulated") EMAIL_SIMULATED
}

@Serializable
enum class RuleResult {
    @SerialName("PASS") PASS,
    @SerialName("FAIL") FAIL,
    @SerialName("UNKNOWN") UNKNOWN
}

@Serializable
enum class FindingSeverity {
    @SerialName("info") INFO,
    @SerialName("warning") WARNING,
    @SerialName("blocking") BLOCKING
}

@Serializable
enum class FindingStatus {
    @SerialName("open") OPEN,
    @SerialName("acknowledged") ACKNOWLEDGED,
    @SerialName("resolved") RESOLVED,
    @SerialName("dismissed") DISMISSED
}

@Serializable
enum class FindingType {
    @SerialName("required_field_missing") REQUIRED_FIELD_MISSING,
    @SerialName("field_uncertain") FIELD_UNCERTAIN,
    @SerialName("arithmetic_mismatch") ARITHMETIC_MISMATCH,
    @SerialName("individual_limit_exceeded") INDIVIDUAL_LIMIT_EXCEEDED,
    @SerialName("aggregate_limit_exceeded") AGGREGATE_LIMIT_EXCEEDED,
    @SerialName("ineligible_category") INELIGIBLE_CATEGORY,
    @SerialName("ineligible_line_item") INELIGIBLE_LINE_ITEM,
    @SerialName("missing_policy_context") MISSING_POLICY_CONTEXT,
    @SerialName("policy_conflict") POLICY_CONFLICT,
    @SerialName("duplicate_candidate") DUPLICATE_CANDIDATE,
    @SerialName("approval_required") APPROVAL_REQUIRED,
    @SerialName("extraction_failed") EXTRACTION_FAILED
}

@Serializable
enum class DuplicateStatus {
    @SerialName("open") OPEN,
    @SerialName("confirmed") CONFIRMED,
    @SerialName("dismissed") DISMISSED
}

@Serializable
enum class ReviewAction {
    @SerialName("approve") APPROVE,
    @SerialName("reject") REJECT,
    @SerialName("request_correction") REQUEST_CORRECTION,
    @SerialName("escalate") ESCALATE
}

@Serializable
enum class RecommendedAction {
    @SerialName("none") NONE,
    @SerialName("review") REVIEW,
    @SerialName("request_correction") REQUEST_CORRECTION,
    @SerialName("escalate") ESCALATE
}

@Serializable
enum class FieldSource {
    @SerialName("receipt_extraction") RECEIPT_EXTRACTION,
    @SerialName("employee_input") EMPLOYEE_INPUT,
    @SerialName("reviewer_correction") REVIEWER_CORRECTION,
    @SerialName("imported_data") IMPORTED_DATA,
    @SerialName("computed") COMPUTED
}

@Serializable
enum class LineItemEligibility {
    @SerialName("eligible") ELIGIBLE,
    @SerialName("ineligible") INELIGIBLE,
    @SerialName("partial") PARTIAL,
    @SerialName("unknown") UNKNOWN,
    @SerialName("not_evaluated") NOT_EVALUATED
}

@Serializable
enum class ExtractionStatus {
    @SerialName("pending") PENDING,
    @SerialName("running") RUNNING,
    @SerialName("success") SUCCESS,
    @SerialName("partial") PARTIAL,
    @SerialName("failed") FAILED,
    @SerialName("unavailable") UNAVAILABLE
}

@Serializable
enum class TripStatus {
    @SerialName("planned") PLANNED,
    @SerialName("active") ACTIVE,
    @SerialName("completed") COMPLETED,
    @SerialName("cancelled") CANCELLED
}
