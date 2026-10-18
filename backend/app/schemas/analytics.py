"""Typed, currency-safe DTOs for database-backed dashboard analytics."""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum

from pydantic import Field

from app.core.enums import ExpenseStatus
from app.schemas.common import ApiModel, CurrencyCode, MoneyString, Page


class AnalyticsAmount(ApiModel):
    """A single-currency aggregate; amount is null when no amount is recorded."""

    currency: CurrencyCode | None = None
    claim_count: int = Field(
        ..., ge=0, description="Claims in this bucket, including missing amounts."
    )
    amount_claim_count: int = Field(..., ge=0, description="Claims with a persisted amount.")
    amount_total: MoneyString | None = Field(
        default=None,
        description="Exact NUMERIC sum for this currency; null when no amount is recorded.",
    )


class AnalyticsStatusCount(ApiModel):
    status: ExpenseStatus
    claim_count: int = Field(..., ge=0)


class AnalyticsStatusAmount(AnalyticsAmount):
    status: ExpenseStatus


class AnalyticsDepartmentAmount(AnalyticsAmount):
    department_id: uuid.UUID | None = Field(
        default=None, description="Null means the current membership has no department."
    )
    department_name: str | None = None


class AnalyticsLocationAmount(AnalyticsAmount):
    office_location_id: uuid.UUID | None = Field(
        default=None, description="Null means the current membership has no office location."
    )
    office_location_name: str | None = None


class AnalyticsCategoryAmount(AnalyticsAmount):
    category: str | None = Field(
        default=None,
        description="Null means no category is recorded; other values are stored as entered.",
    )


class AnalyticsMonthlyAmount(AnalyticsAmount):
    month: date = Field(
        ..., description="First calendar date of the month containing the expense dates."
    )


class AnalyticsOverviewResponse(ApiModel):
    """Organization-level overview for an inclusive transaction-date range."""

    from_date: date
    to_date: date
    claim_count: int = Field(
        ..., ge=0, description="Dated claims whose expense_date is in the requested range."
    )
    claims_requiring_review: int = Field(
        ..., ge=0, description="Claims in submitted or in_review workflow status."
    )
    claims_needing_information: int = Field(..., ge=0)
    claims_missing_critical_fields: int = Field(
        ...,
        ge=0,
        description=(
            "Dated in-range claims missing merchant, amount or currency. Undated claims are "
            "reported separately in claims_with_unknown_transaction_date."
        ),
    )
    claims_with_uncertain_critical_fields: int = Field(
        ...,
        ge=0,
        description="Dated in-range claims with current critical-field evidence carrying uncertainty_reason.",
    )
    claims_with_unknown_transaction_date: int = Field(
        ...,
        ge=0,
        description="All organization claims with no expense_date; these cannot be assigned to the selected period.",
    )
    status_counts: list[AnalyticsStatusCount]
    status_amounts: list[AnalyticsStatusAmount]
    by_department: list[AnalyticsDepartmentAmount]
    by_office_location: list[AnalyticsLocationAmount]
    by_category: list[AnalyticsCategoryAmount]
    monthly_totals: list[AnalyticsMonthlyAmount] = Field(
        description="Sparse calendar-month buckets; an omitted month had no dated claims in the requested range."
    )


class AnalyticsGroupBy(StrEnum):
    MONTH = "month"
    DEPARTMENT = "department"
    LOCATION = "location"
    CATEGORY = "category"
    EMPLOYEE = "employee"
    STATUS = "status"


class AnalyticsSpendRow(AnalyticsAmount):
    """One group and one currency; separate rows prevent mixed-currency totals."""

    bucket_start: date | None = Field(
        default=None, description="Calendar month start when group_by=month."
    )
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    office_location_id: uuid.UUID | None = None
    office_location_name: str | None = None
    category: str | None = None
    employee_membership_id: uuid.UUID | None = Field(
        default=None, description="Present only for group_by=employee; requires analytics:read_org."
    )
    employee_display_name: str | None = None
    status: ExpenseStatus | None = None


class AnalyticsSpendResponse(ApiModel):
    from_date: date
    to_date: date
    group_by: AnalyticsGroupBy
    claims_with_unknown_transaction_date: int = Field(
        ...,
        ge=0,
        description="Claims matching the other filters but lacking expense_date; excluded from groups.",
    )
    results: Page[AnalyticsSpendRow]


# The canonical bucket key for a bucket whose descriptor value is null: a membership
# with no department or office location, or an expense with no category. The bucket is
# real and must have a stable identity, so it is keyed explicitly instead of being
# represented by an empty string that a client would have to special-case.
UNASSIGNED_BUCKET_KEY = "__unassigned__"


class AnalyticsSpendMatrixRow(AnalyticsAmount):
    """One (primary bucket, secondary bucket, currency) cell of the spend matrix.

    A heatmap needs a key per axis that survives a null descriptor value, so each row
    carries one canonical string key per requested dimension in addition to the typed
    descriptor fields. Descriptor fields belonging to dimensions that were not requested
    are null; a second dimension's value is never written into the wrong field.
    """

    primary_key: str = Field(
        ...,
        description=(
            "Canonical key of the primary-dimension bucket: an ISO month start for month, "
            "otherwise the bucket's identifier or value, with null descriptors keyed as "
            f"{UNASSIGNED_BUCKET_KEY}."
        ),
    )
    secondary_key: str = Field(
        ...,
        description=(
            "Canonical key of the secondary-dimension bucket, on the same rules as primary_key."
        ),
    )
    bucket_start: date | None = Field(
        default=None, description="Calendar month start when month is a requested dimension."
    )
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    office_location_id: uuid.UUID | None = None
    office_location_name: str | None = None
    category: str | None = None
    employee_membership_id: uuid.UUID | None = Field(
        default=None, description="Present only when employee is a requested dimension."
    )
    employee_display_name: str | None = None
    status: ExpenseStatus | None = None


class AnalyticsSpendMatrixResponse(ApiModel):
    """A two-dimensional spend aggregation, one row per bucket pair and currency."""

    from_date: date
    to_date: date
    primary: AnalyticsGroupBy
    secondary: AnalyticsGroupBy
    claims_with_unknown_transaction_date: int = Field(
        ...,
        ge=0,
        description="Claims matching the other filters but lacking expense_date; excluded from groups.",
    )
    results: Page[AnalyticsSpendMatrixRow]


class AnalyticsDepartmentRow(AnalyticsAmount):
    """One department's expenditure and review workload, for one currency.

    ``amount_total`` is *requested* expenditure: the sum of persisted claim amounts in
    range, whatever their workflow status. Approved expenditure is reported separately
    and is a subset of it - approval is a workflow decision, not a payment, so neither
    figure means money has moved.
    """

    department_id: uuid.UUID | None = Field(
        default=None,
        description="Null for claims whose member has no department: unassigned, not unknown.",
    )
    department_name: str | None = None
    approved_claim_count: int = Field(..., ge=0)
    approved_amount_total: MoneyString | None = Field(
        default=None, description="Sum of amounts on claims in an approved state."
    )
    pending_review_count: int = Field(
        ...,
        ge=0,
        description="Claims in submitted or in_review: the same definition overview uses.",
    )
    needs_info_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)
    draft_count: int = Field(..., ge=0)
    average_amount_total: MoneyString | None = Field(
        default=None,
        description="Mean amount per claim that has an amount; null when none does.",
    )
    requested_share: MoneyString | None = Field(
        default=None,
        description=(
            "This department's share of the organization's requested expenditure in the "
            "same currency, to four decimal places. Null when the currency total is zero."
        ),
    )


class AnalyticsDepartmentTotals(AnalyticsAmount):
    """The organization-wide figures the department rows are a breakdown of."""

    approved_claim_count: int = Field(..., ge=0)
    approved_amount_total: MoneyString | None = None
    pending_review_count: int = Field(..., ge=0)
    needs_info_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)
    draft_count: int = Field(..., ge=0)
    unassigned_claim_count: int = Field(
        ...,
        ge=0,
        description="Claims counted above whose member has no department.",
    )


class AnalyticsDepartmentSummaryResponse(ApiModel):
    """Department-wise expenditure and review workload for the selected period.

    ``totals`` is the whole organization per currency and ``departments`` decomposes it,
    so a consumer never has to add the rows up (and cannot add them up wrongly). Amounts
    are never combined across currencies.
    """

    from_date: date
    to_date: date
    claims_with_unknown_transaction_date: int = Field(
        ...,
        ge=0,
        description="Claims matching the other filters but lacking expense_date; excluded from groups.",
    )
    totals: list[AnalyticsDepartmentTotals]
    departments: list[AnalyticsDepartmentRow]
