package org.proofline.android.data.sample

import org.proofline.android.data.model.*

object SampleDataProvider {
    val sampleMembership = MembershipSummary(
        id = "6dbc60b8-8577-56ec-806e-4201fa5993c4",
        organization_id = "org-demo-1234",
        user = UserSummary(
            id = "6dbc60b8-8577-56ec-806e-4201fa5993c4",
            display_name = "Asha Menon (Sample Offline)",
            is_active = true
        ),
        employee_code = "DEMO-ASHA",
        status = "active",
        manager_membership_id = "manager-priya-uuid",
        joined_on = "2024-01-15"
    )

    val sampleExpenses = listOf(
        Expense(
            id = "exp-01",
            version = 1,
            status = "draft",
            channel = "android",
            merchant = FieldValue("Blue Tokai Coffee", "employee_input", true, null, null, null),
            expense_date = FieldValue("2026-10-15", "employee_input", true, null, null, null),
            amount = FieldValue(Money("350.00", "INR"), "employee_input", true, null, null, null),
            category = "Meals",
            business_purpose = "Team sync coffee",
            findings = emptyList(),
            created_at = "2026-10-15T10:00:00Z"
        ),
        Expense(
            id = "exp-02",
            version = 1,
            status = "submitted",
            channel = "android",
            merchant = FieldValue("Uber Rides", "receipt_extraction", false, 0.95, EvidenceRef("rec-1", 1, null), null),
            expense_date = FieldValue("2026-10-14", "receipt_extraction", false, 0.92, EvidenceRef("rec-1", 1, null), null),
            amount = FieldValue(Money("850.00", "INR"), "receipt_extraction", false, 0.98, EvidenceRef("rec-1", 1, null), null),
            category = "Transport",
            business_purpose = "Client meeting commute",
            findings = listOf(
                Finding("f-1", "approval_required", "rule-approval", "v1", "UNKNOWN", "warning", "Requires manager approval", null, "review", "open", "2026-10-14T12:00:00Z")
            ),
            created_at = "2026-10-14T11:30:00Z"
        ),
        Expense(
            id = "exp-03",
            version = 1,
            status = "needs_info",
            channel = "web",
            merchant = FieldValue("IndiGo Airlines", "receipt_extraction", true, 0.99, EvidenceRef("rec-2", 1, null), null),
            expense_date = FieldValue("2026-10-10", "receipt_extraction", true, 0.99, EvidenceRef("rec-2", 1, null), null),
            amount = FieldValue(Money("7400.00", "INR"), "receipt_extraction", true, 0.99, EvidenceRef("rec-2", 1, null), null),
            category = "Travel",
            business_purpose = "Flight to Mumbai office",
            findings = listOf(
                Finding("f-2", "missing_policy_context", "rule-purpose", "v1", "FAIL", "blocking", "Missing client name for travel", null, "request_correction", "open", "2026-10-10T15:00:00Z")
            ),
            created_at = "2026-10-10T14:00:00Z"
        ),
        Expense(
            id = "exp-04",
            version = 1,
            status = "in_review",
            channel = "android",
            merchant = FieldValue("Taj Hotel Dining", "receipt_extraction", true, 0.94, EvidenceRef("rec-3", 1, null), null),
            expense_date = FieldValue("2026-10-08", "receipt_extraction", true, 0.94, EvidenceRef("rec-3", 1, null), null),
            amount = FieldValue(Money("3200.00", "INR"), "receipt_extraction", true, 0.94, EvidenceRef("rec-3", 1, null), null),
            category = "Client Entertainment",
            business_purpose = "Dinner with prospective client",
            findings = emptyList(),
            created_at = "2026-10-08T21:00:00Z"
        ),
        Expense(
            id = "exp-05",
            version = 1,
            status = "approved",
            channel = "web",
            merchant = FieldValue("WeWork Office Supplies", "receipt_extraction", true, 0.98, EvidenceRef("rec-4", 1, null), null),
            expense_date = FieldValue("2026-10-05", "receipt_extraction", true, 0.98, EvidenceRef("rec-4", 1, null), null),
            amount = FieldValue(Money("1450.00", "INR"), "receipt_extraction", true, 0.98, EvidenceRef("rec-4", 1, null), null),
            category = "Office",
            business_purpose = "Stationery and printer cartridges",
            findings = emptyList(),
            created_at = "2026-10-05T09:00:00Z"
        ),
        Expense(
            id = "exp-06",
            version = 1,
            status = "rejected",
            channel = "android",
            merchant = FieldValue("Luxury Spa & Wellness", "employee_input", true, null, null, null),
            expense_date = FieldValue("2026-10-02", "employee_input", true, null, null, null),
            amount = FieldValue(Money("5000.00", "INR"), "employee_input", true, null, null, null),
            category = "Personal",
            business_purpose = "Personal wellness",
            findings = listOf(
                Finding("f-3", "ineligible_category", "rule-category", "v1", "FAIL", "blocking", "Personal expenses are not reimbursable", null, "none", "resolved", "2026-10-03T10:00:00Z")
            ),
            created_at = "2026-10-02T18:00:00Z"
        )
    )
}
