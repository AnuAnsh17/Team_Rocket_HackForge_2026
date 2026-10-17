"""Users, organization memberships, reporting relationships and role grants.

This module is where the authorization model becomes data:

* :class:`User` is a global identity. It carries no roles and no organization.
* :class:`OrganizationMembership` is the org-scoped *employment* record. It is
  the authoritative source of an employee's employment status, grade,
  department, cost center, location and manager. Putting employment context here
  rather than on a separate profile table avoids two records that can disagree.
* :class:`ReportingRelationship` is a first-class, historised edge rather than a
  self-referencing column, because "who approved this in March" must remain
  answerable after a reorganisation.
* :class:`RoleAssignment` grants a role inside a scope. A role name alone never
  grants anything: permissions are derived from the granted roles, and scope is
  checked separately at the resource.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import MembershipStatus, RoleCode
from app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
    in_values,
)

# Scope dimensions for a role grant.
ROLE_SCOPE_TYPES = (
    "organization",
    "department",
    "cost_center",
    "office_location",
    "team",
    "self",
)

# Types of reporting edge.
REPORTING_RELATIONSHIP_TYPES = ("primary", "secondary", "dotted")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person. Global identity, deliberately carrying no authorization data."""

    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Email is optional and treated as personal data: never logged in full.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # The subject identifier issued by the external identity provider.
    external_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Denormalised convenience only; authoritative membership rows decide scope.
    primary_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("auth_provider", "external_subject"),
        UniqueConstraint("email"),
        CheckConstraint(
            "(external_subject IS NULL AND auth_provider IS NULL) "
            "OR (external_subject IS NOT NULL AND auth_provider IS NOT NULL)",
            name="external_identity_consistent",
        ),
    )


class OrganizationMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An employment record inside one organization.

    A user may belong to more than one organization (for example a contractor or
    an employee of two legal entities), so membership - not the user row - is the
    unit of employment context and of role granting.
    """

    __tablename__ = "organization_memberships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    employee_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = enum_column(MembershipStatus)
    job_grade_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("job_grades.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True
    )
    office_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("office_locations.id", ondelete="SET NULL"), nullable=True
    )
    # Convenience pointer to the primary manager. The historised source of truth
    # is reporting_relationships.
    primary_manager_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        in_enum("status", MembershipStatus),
        CheckConstraint(
            "ended_on IS NULL OR joined_on IS NULL OR ended_on >= joined_on",
            name="ended_after_joined",
        ),
        CheckConstraint(
            "primary_manager_membership_id IS NULL OR primary_manager_membership_id <> id",
            name="manager_is_not_self",
        ),
    )


class ReportingRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A time-bounded manager relationship.

    Kept as its own table so that an approval decision can be attributed to the
    reporting line that existed when the decision was made, even after the
    organization chart changes.
    """

    __tablename__ = "reporting_relationships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    employee_membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    manager_membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(16), nullable=False, default="primary")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_values("relationship_type", REPORTING_RELATIONSHIP_TYPES),
        CheckConstraint(
            "employee_membership_id <> manager_membership_id", name="manager_is_not_employee"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="effective_range_valid"
        ),
    )


class RoleAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Grants one role to one membership inside one scope.

    ``scope_id`` is always populated. For ``scope_type = 'organization'`` it
    equals ``organization_id``; using the organization id rather than NULL keeps
    the uniqueness constraint meaningful, because PostgreSQL treats NULLs as
    distinct and would otherwise allow duplicate organization-scope grants.
    """

    __tablename__ = "role_assignments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = enum_column(RoleCode)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("membership_id", "role", "scope_type", "scope_id"),
        in_enum("role", RoleCode),
        in_values("scope_type", ROLE_SCOPE_TYPES),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at", name="revoke_after_grant"
        ),
    )
