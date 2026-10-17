"""Organization, structural context, and allowance profiles."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ALLOWANCE_PERIOD_TYPES, PolicyReviewState
from app.db.base import (
    MONEY,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
    in_values,
    non_negative,
)

# NOTE ON DELIBERATE NULLABILITY
# ------------------------------
# Timezone and reporting currency are NULLABLE on purpose. The approved company
# policy and the organization's operating timezone have not been supplied, and
# docs/policy-assumptions.md lists both as unresolved. Modelling them as
# nullable makes "not yet configured" representable; defaulting them to values
# would silently invent a day-boundary rule and a currency, which the build plan
# forbids. A CHECK on allowance_profile_items below makes the same point for
# limits: no limit may exist without a cited source clause.


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An organization or legal entity. Tenant boundary for every owned record."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    legal_entity_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    jurisdiction_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Must be configured by an organization administrator; never defaulted.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reporting_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "departments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class CostCenter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cost_centers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class OfficeLocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Physical work location, used as a policy-resolution dimension."""

    __tablename__ = "office_locations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class JobGrade(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Grade / job level / band.

    This table is empty in the scaffold. No grade levels, levels or bands are
    invented: the real set is organizational data supplied by the company.
    """

    __tablename__ = "job_grades"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Ordering hint only. It is NOT assumed to correlate with allowance size;
    # policy resolution must be driven by explicit assignments.
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class AllowanceProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A named set of allowances that can be assigned to employees or scopes.

    A profile carries no limits by itself; its items do, and each item must cite
    a verified policy source clause.
    """

    __tablename__ = "allowance_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_state: Mapped[str] = enum_column(PolicyReviewState)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        in_enum("review_state", PolicyReviewState),
    )


class AllowanceProfileItem(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One allowance line inside a profile.

    INTEGRITY GUARD - ``limit_requires_source``: the database refuses a row that
    carries an amount without also citing a source clause and a currency. This is
    the storage-level expression of "never invent policy thresholds": an
    unsourced limit cannot be persisted, so it can never later be mistaken for
    approved policy.
    """

    __tablename__ = "allowance_profile_items"

    allowance_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("allowance_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    limit_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    policy_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_rules.id", ondelete="SET NULL"), nullable=True
    )
    source_clause: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        in_values("period_type", ALLOWANCE_PERIOD_TYPES),
        CheckConstraint(
            "limit_amount IS NULL OR (source_clause IS NOT NULL AND currency IS NOT NULL)",
            name="limit_requires_source",
        ),
        non_negative("limit_amount"),
    )
