"""Trips, expense claims, per-field provenance history and line items.

Two design points worth stating explicitly:

1. ``expenses`` holds the CURRENT value of each claim field, denormalised so a
   list or detail query stays cheap. The authoritative, immutable provenance for
   each field at each version lives in :class:`ExpenseFieldEvidence`. A partial
   unique index (created in the initial migration) guarantees at most one
   ``is_current`` row per (expense, field), so the two representations cannot
   drift apart silently.
2. No policy threshold, limit or category eligibility is encoded here. Category
   is a free-form code that the policy layer interprets; eligibility is never
   inferred from a keyword.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    ExpenseChannel,
    ExpenseFieldName,
    ExpenseStatus,
    FieldSource,
    LineItemEligibility,
    TripStatus,
)
from app.db.base import (
    MONEY,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
    non_negative,
)


class Trip(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An optional business trip.

    A trip is recorded only when it is actually supplied or entered. The system
    must never infer a trip from an employee's home city: that inference would
    silently change which policy applies.
    """

    __tablename__ = "trips"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    destination_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = enum_column(TripStatus)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("status", TripStatus),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="end_after_start",
        ),
    )


class Expense(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One reimbursement claim.

    ``version`` is the optimistic-concurrency token. Every correction increments
    it, which is what lets a decision reject a stale write instead of
    overwriting a reviewer's work.

    Money columns are NUMERIC. ``amount`` is the ORIGINAL transaction amount and
    currency; ``amount_reporting`` plus ``reporting_rate*`` are populated only
    when the approved policy requires conversion, and are NULL otherwise - the
    scaffold does not apply any exchange rate.
    """

    __tablename__ = "expenses"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("trips.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = enum_column(ExpenseChannel)
    status: Mapped[str] = enum_column(ExpenseStatus)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    merchant: Mapped[str | None] = mapped_column(String(300), nullable=True)
    expense_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attendee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    amount_reporting: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reporting_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reporting_rate: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reporting_rate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reporting_rate_source: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # The policy version that most recently governed an evaluation of this claim.
    # Preserved so a historical decision can be explained after the policy moves on.
    evaluated_policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("channel", ExpenseChannel),
        in_enum("status", ExpenseStatus),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "attendee_count IS NULL OR attendee_count >= 0", name="attendee_count_sane"
        ),
        CheckConstraint(
            "(amount IS NULL AND currency IS NULL) OR (amount IS NOT NULL AND currency IS NOT NULL)",
            name="amount_requires_currency",
        ),
        non_negative("amount"),
        non_negative("amount_reporting"),
    )


class ExpenseFieldEvidence(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Per-field provenance for one expense version. Append-only in practice.

    This is what makes "show me why" answerable: for every field it records the
    value, where the value came from, whether a human reviewed it, the extraction
    quality signal, the receipt region when the provider actually supplied one,
    and why a value is uncertain.

    ``is_current`` marks the row that reflects the claim's current version. A
    partial unique index in the migration enforces one current row per field.
    """

    __tablename__ = "expense_field_evidence"

    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    expense_version: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = enum_column(ExpenseFieldName)
    source: Mapped[str] = enum_column(FieldSource)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_decimal: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_integer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Provider quality signal, NOT a calibrated probability. Null when the
    # provider supplies no meaningful value.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("field_name", ExpenseFieldName),
        in_enum("source", FieldSource),
        UniqueConstraint("expense_id", "expense_version", "field_name"),
        CheckConstraint("expense_version >= 1", name="expense_version_positive"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_in_unit_range",
        ),
        # Employee-entered data must never masquerade as receipt evidence: any
        # row claiming extraction provenance must name the receipt it came from.
        CheckConstraint(
            "source <> 'receipt_extraction' OR receipt_id IS NOT NULL",
            name="extraction_requires_receipt",
        ),
        CheckConstraint(
            "source <> 'computed' OR reviewed = false",
            name="computed_values_are_not_human_reviewed",
        ),
    )


class LineItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A line on a receipt.

    Eligibility is a policy outcome, not a guess: an item that has not been
    evaluated stays NOT_EVALUATED, and an item whose treatment depends on a rule
    that is not yet verified stays UNKNOWN. No keyword blacklist is applied here.
    """

    __tablename__ = "line_items"

    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    unit_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    eligibility: Mapped[str] = enum_column(LineItemEligibility)
    ineligibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_rules.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        in_enum("eligibility", LineItemEligibility),
        UniqueConstraint("expense_id", "extraction_run_id", "line_number"),
        non_negative("quantity"),
        non_negative("amount"),
        # An item may only be marked ineligible when a reason has been recorded.
        CheckConstraint(
            "eligibility <> 'ineligible' OR ineligibility_reason IS NOT NULL",
            name="ineligibility_requires_reason",
        ),
    )
