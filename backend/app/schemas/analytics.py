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
