"""Policy documents, versions, rules, assignments and explicit exceptions.

The rule that shapes this schema - and the reason several constraints exist - is
that no reimbursement rule may be active without (a) a verified source clause and
(b) a named human who validated it. ``policy_rules.source_requires_validation``
enforces exactly that at the storage layer. Everything in this module ships
empty.
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
    TEXT_VALUED_SCOPE_TYPES,
    UUID_VALUED_SCOPE_TYPES,
    ApprovalState,
    PolicyAssignmentScopeType,
    PolicyExceptionType,
    PolicyReviewState,
)
from app.db.base import (
    MONEY,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
    in_list,
    in_values,
)

# A policy exception may be attached to one of these subject kinds.
EXCEPTION_SUBJECT_TYPES = ("membership", "user", "expense", "trip", "expense_category")


class PolicyDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The source document a policy version was derived from.

    ``source_file_sha256`` is what makes "which exact file governed this rule"
    answerable. The file itself is NOT stored in the repository.
    """

    __tablename__ = "policy_documents"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "title", "source_file_sha256"),)


class PolicyVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One approved (or proposed) version of a policy document."""

    __tablename__ = "policy_versions"

    policy_document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_state: Mapped[str] = enum_column(PolicyReviewState)
    source_document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("policy_document_id", "version_label"),
        in_enum("review_state", PolicyReviewState),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_range_valid",
        ),
        CheckConstraint(
            "review_state <> 'approved' OR (approved_by_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL)",
            name="approval_requires_approver",
        ),
    )


class PolicyRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One deterministic rule belonging to a policy version.

    INTEGRITY GUARD - ``source_requires_validation``: a rule may only be marked
    active when it carries a source clause and records who validated it. A rule
    with invented parameters therefore cannot be activated, because there is no
    way to satisfy the constraint without naming a real source clause and a real
    human approver.
    """

    __tablename__ = "policy_rules"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Identifier of the evaluator class/function in app/policy. Deliberately a
    # string so that no callable is stored in the database.
    evaluator_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Validated parameters only. Never a placeholder for an unverified threshold.
    parameters: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    source_reference: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    source_clause: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str] = enum_column(PolicyReviewState)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("policy_version_id", "rule_id"),
        in_enum("review_state", PolicyReviewState),
        CheckConstraint(
            "is_active = false OR (source_clause IS NOT NULL "
            "AND validated_by_user_id IS NOT NULL AND validated_at IS NOT NULL "
            "AND evaluator_type IS NOT NULL)",
            name="source_requires_validation",
        ),
    )


class PolicyAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Assigns a policy version to a scope, with an explicit priority.

    Precedence between scopes is NOT implied by specificity. It is configuration:
    ``priority`` is compared only after the resolver has determined that both
    assignments actually apply, and an unresolved or conflicting resolution is
    reported as UNKNOWN rather than guessed. See docs/role-policy-hierarchy.md.
    """

    __tablename__ = "policy_assignments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    allowance_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("allowance_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope_type: Mapped[str] = enum_column(PolicyAssignmentScopeType)
    # Exactly one of scope_id / scope_key is populated, decided by the dimension.
    # ``scope_id`` addresses a UUID-valued dimension (organization, office location,
    # department, cost center, job grade, trip, employee) and equals organization_id
    # for organization scope. ``scope_key`` carries a text-valued dimension
    # (legal entity, jurisdiction, expense category), which has no table of its own
    # and therefore no id to point at.
    #
    # The split is not cosmetic. Before it, expense_category was treated as
    # UUID-valued, so the resolver compared str(scope_id) against a category such as
    # "meal" and could never match; legal entity and jurisdiction were never matched
    # at all. Which dimensions are which is defined once, in
    # app/core/enums.py::UUID_VALUED_SCOPE_TYPES / TEXT_VALUED_SCOPE_TYPES.
    #
    # Uniqueness is NOT declared here as a UniqueConstraint. PostgreSQL treats NULLs
    # as distinct in a unique index, and one of these two columns is always NULL, so
    # a plain unique constraint would silently allow duplicate assignments. The
    # unique index over their coalesced text is created in the migration.
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    scope_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approval_state: Mapped[str] = enum_column(ApprovalState)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # A scope assignment must carry exactly the selector its dimension needs, and
        # no other. This is what stops a category assignment being stored with a UUID
        # that can never match a category, which is the defect this constraint exists
        # to make unstorable rather than merely unlikely.
        CheckConstraint(
            "("
            "  scope_type IN " + in_list(sorted(t.value for t in UUID_VALUED_SCOPE_TYPES)) + ""
            "  AND scope_id IS NOT NULL AND scope_key IS NULL"
            ") OR ("
            "  scope_type IN " + in_list(sorted(t.value for t in TEXT_VALUED_SCOPE_TYPES)) + ""
            "  AND scope_key IS NOT NULL AND scope_id IS NULL"
            ")",
            name="scope_selector_consistent",
        ),
        in_enum("scope_type", PolicyAssignmentScopeType),
        in_enum("approval_state", ApprovalState),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_range_valid",
        ),
    )


class PolicyException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An explicit, authorized, time-bounded deviation from an assigned policy.

    Deliberately narrow: an exception needs a reason, an effective start, an
    approver and, when it carries an amount, a currency. ``time_bounded`` forces
    a review point, so an exception cannot quietly become permanent policy.
    """

    __tablename__ = "policy_exceptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    exception_type: Mapped[str] = enum_column(PolicyExceptionType)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    policy_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_rules.id", ondelete="SET NULL"), nullable=True
    )
    allowance_profile_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("allowance_profile_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    value_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approval_state: Mapped[str] = enum_column(ApprovalState)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_clause: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        in_enum("exception_type", PolicyExceptionType),
        in_enum("approval_state", ApprovalState),
        in_values("subject_type", EXCEPTION_SUBJECT_TYPES),
        CheckConstraint(
            "value_amount IS NULL OR currency IS NOT NULL", name="amount_requires_currency"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="effective_range_valid"
        ),
        CheckConstraint(
            "approval_state <> 'approved' OR granted_by_user_id IS NOT NULL",
            name="approval_requires_approver",
        ),
    )
