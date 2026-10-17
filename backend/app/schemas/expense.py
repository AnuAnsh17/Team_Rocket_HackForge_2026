"""Expense DTOs - the canonical claim representation shared by every client."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.core.enums import ExpenseChannel, ExpenseStatus
from app.schemas.common import (
    ApiModel,
    CurrencyCode,
    FieldValue,
    Money,
    MoneyString,
    NonNegativeMoney,
    Page,
)
from app.schemas.identity import UserSummary
from app.schemas.receipt import ReceiptSummary
from app.schemas.review import FindingResponse


class LineItemResponse(ApiModel):
    """One receipt line, with its policy-derived eligibility.

    ``eligibility`` is NOT_EVALUATED until a verified rule has actually run, and
    UNKNOWN when a rule needs evidence that is unavailable. Neither state is
    presented as ineligible.
    """

    id: uuid.UUID
    line_number: int | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_amount: MoneyString | None = None
    amount: MoneyString | None = Field(
        default=None,
        description=(
            "Line amount as a decimal string. Line items carry no per-field provenance in this "
            "schema: only whole claim fields have a tracked source."
        ),
    )
    currency: str | None = None
    tax_amount: MoneyString | None = None
    discount_amount: MoneyString | None = None
    category: str | None = None
    eligibility: str
    ineligibility_reason: str | None = None


class TripSummary(ApiModel):
    id: uuid.UUID
    purpose: str
    destination_city: str | None = None
    destination_country_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str


class ExpenseSummary(ApiModel):
    """Row shape for list endpoints and review queues."""

    id: uuid.UUID
    version: int
    employee: UserSummary
    channel: ExpenseChannel
    status: ExpenseStatus
    merchant: str | None = None
    expense_date: date | None = None
    amount: Money
    category: str | None = None
    trip_id: uuid.UUID | None = None
    receipt_count: int = Field(0, ge=0)
    open_finding_count: int = Field(0, ge=0)
    blocking_finding_count: int = Field(0, ge=0)
    open_duplicate_candidate_count: int = Field(0, ge=0)
    submitted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(Page[ExpenseSummary]):
    pass


class ExpenseResponse(ApiModel):
    """The canonical claim detail.

    Field naming and nesting are fixed by docs/api-contract.md. Both web
    applications and the mobile app consume exactly this shape; neither may add
    a private variant.
    """

    id: uuid.UUID
    version: int = Field(
        ..., description="Optimistic-concurrency token. Send it back on any mutation."
    )
    organization_id: uuid.UUID
    employee: UserSummary
    channel: ExpenseChannel
    status: ExpenseStatus

    trip_id: uuid.UUID | None = None
    trip: TripSummary | None = None

    merchant: FieldValue[str]
    expense_date: FieldValue[date]
    amount: Money
    receipt_number: FieldValue[str] | None = None

    category: str | None = None
    business_purpose: str | None = None
    client_name: str | None = None
    attendee_count: int | None = None

    amount_reporting: NonNegativeMoney | None = Field(
        default=None,
        description=(
            "Normalised reporting amount. Null unless the approved policy requires conversion; "
            "this build applies no exchange rate."
        ),
    )

    receipts: list[ReceiptSummary] = Field(default_factory=list)
    line_items: list[LineItemResponse] = Field(default_factory=list)
    findings: list[FindingResponse] = Field(default_factory=list)

    evaluated_policy_version_id: uuid.UUID | None = None
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateExpenseRequest(ApiModel):
    """Create a draft claim from JSON metadata.

    Receipt images are uploaded separately through
    ``POST /api/v1/expenses/{expense_id}/receipts`` - the single canonical upload
    route. This request deliberately carries no ``source`` or ``reviewed``
    fields: provenance is assigned by the server from the caller's role, so a
    client cannot claim reviewer provenance.
    """

    employee_membership_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Only accepted from a caller authorized to create on behalf of another employee. "
            "An employee's own claims are always created against their own membership."
        ),
    )
    channel: ExpenseChannel = ExpenseChannel.WEB
    trip_id: uuid.UUID | None = None
    merchant: str | None = Field(default=None, max_length=300)
    expense_date: date | None = None
    amount: MoneyString | None = Field(default=None, ge=0)
    currency: CurrencyCode | None = None
    category: str | None = Field(default=None, max_length=64)
    business_purpose: str | None = None
    client_name: str | None = Field(default=None, max_length=200)
    attendee_count: int | None = Field(default=None, ge=0)


class UpdateExpenseRequest(ApiModel):
    """Correct allowed fields on a draft or submitted claim.

    Plain scalar values only. The server derives ``FieldSource`` from the
    caller's role (employee_input vs reviewer_correction) and records a new
    provenance row; incrementing ``version`` is automatic.
    """

    expected_version: int = Field(
        ..., ge=1, description="Required. A mismatch is refused with STALE_VERSION."
    )
    merchant: str | None = Field(default=None, max_length=300)
    expense_date: date | None = None
    amount: MoneyString | None = Field(default=None, ge=0)
    currency: CurrencyCode | None = None
    category: str | None = Field(default=None, max_length=64)
    business_purpose: str | None = None
    client_name: str | None = Field(default=None, max_length=200)
    attendee_count: int | None = Field(default=None, ge=0)
    trip_id: uuid.UUID | None = None


class SubmitExpenseRequest(ApiModel):
    """Submit a complete draft for human review."""

    expected_version: int = Field(..., ge=1, description="Required optimistic-concurrency token.")
