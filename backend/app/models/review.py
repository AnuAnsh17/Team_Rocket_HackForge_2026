"""Findings, duplicate candidates, review decisions and approval tasks.

Every constraint in this module exists to prevent one specific unfair or
unauditable outcome:

* ``confidence_in_unit_range`` / ``ranking_score_in_unit_range`` - a score is a
  ranking signal, not a calibrated probability, and it must at least be a number
  in range rather than a fabricated certainty.
* ``duplicate_pair_canonical`` (partial unique index in the migration) - the pair
  (A,B) and (B,A) cannot both exist, so a reviewer cannot be shown the same
  candidate twice and resolve it inconsistently.
* ``rejection_requires_reason`` - a claim cannot be rejected without a recorded
  human explanation.
* ``resolution_requires_state`` - a finding cannot be marked resolved or
  dismissed without recording who did it and when.
* The findings identity unique index - re-running evaluation for the same claim
  version, policy version and scope cannot multiply findings.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

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
    ApprovalTaskStatus,
    DuplicateStatus,
    FindingResult,
    FindingSeverity,
    FindingStatus,
    FindingType,
    RecommendedAction,
    ReviewAction,
    RoleCode,
)
from app.db.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
)


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One deterministic rule outcome against one claim version.

    ``result`` is tri-state. UNKNOWN is the correct answer whenever required
    evidence or policy context is absent, and it is never treated as a pass.
    """

    __tablename__ = "findings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    # Stable rule identifier. Not a foreign key: a finding must remain readable
    # even if the rule row is later retired.
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    finding_type: Mapped[str] = enum_column(FindingType)
    result: Mapped[str] = enum_column(FindingResult)
    severity: Mapped[str] = enum_column(FindingSeverity)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    employee_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_reference: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    calculation: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str] = enum_column(RecommendedAction)

    status: Mapped[str] = enum_column(FindingStatus)
    expense_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # Hash over the resolved evaluation scope. Retries with the same inputs
    # produce the same fingerprint, so they cannot create a second finding.
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Superseded findings are kept, never deleted: history must stay inspectable.
    superseded_by_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("finding_type", FindingType),
        in_enum("result", FindingResult),
        in_enum("severity", FindingSeverity),
        in_enum("status", FindingStatus),
        in_enum("recommended_action", RecommendedAction),
        CheckConstraint("expense_version >= 1", name="expense_version_positive"),
        CheckConstraint(
            "status NOT IN ('resolved', 'dismissed') OR "
            "(resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="resolution_requires_state",
        ),
        CheckConstraint(
            "result <> 'FAIL' OR (expected_value IS NOT NULL OR calculation IS NOT NULL)",
            name="failure_requires_evidence",
        ),
    )


class DuplicateCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A possible duplicate pair. Never a confirmed duplicate, never fraud.

    Confirmation and dismissal are reviewer actions that require a reason and
    produce an audit event. No automatic rejection is triggered by a score.
    """

    __tablename__ = "duplicate_candidates"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expense_a_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    expense_b_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = enum_column(DuplicateStatus)
    # Independent signals: exact hash, perceptual similarity, normalised field
    # match, channel/context metadata.
    signals: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    ranking_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cross_channel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        in_enum("status", DuplicateStatus),
        CheckConstraint("expense_a_id <> expense_b_id", name="pair_members_differ"),
        CheckConstraint(
            "ranking_score IS NULL OR (ranking_score >= 0 AND ranking_score <= 1)",
            name="ranking_score_in_unit_range",
        ),
        CheckConstraint(
            "status = 'open' OR (resolved_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND resolution_reason IS NOT NULL)",
            name="resolution_requires_state",
        ),
    )


class ReviewDecision(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """An executed reviewer/approver decision. Audited atomically with the state
    change it caused."""

    __tablename__ = "review_decisions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # The reporting/approval edge that authorized this actor, captured at decision
    # time. Preserved so a historical decision stays explainable after a
    # reorganisation.
    delegation_basis: Mapped[str | None] = mapped_column(String(120), nullable=True)

    action: Mapped[str] = enum_column(ReviewAction)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    expense_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    # The approval task this decision resolved, when the decision closed one. The
    # reverse direction is intentionally absent from ApprovalTask: see the note
    # there about the mutual-foreign-key cycle.
    approval_task_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("approval_tasks.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("action", ReviewAction),
        CheckConstraint("expense_version >= 1", name="expense_version_positive"),
        # A rejection or a correction request must carry a human-entered reason.
        CheckConstraint(
            "action NOT IN ('reject', 'request_correction') OR "
            "(reason IS NOT NULL AND length(btrim(reason)) > 0)",
            name="rejection_requires_reason",
        ),
    )


class ApprovalTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A required approval step for a claim.

    Whether a step is required at all is decided by the approved policy and the
     organization's configured workflow - not by this table and not by an
    assumption that every organization has every stage. Unknown workflow
    configuration produces no task and is reported as unresolved rather than
    guessed.
    """

    __tablename__ = "approval_tasks"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_role: Mapped[str | None] = enum_column(RoleCode, nullable=True)
    assignee_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organization_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = enum_column(ApprovalTaskStatus)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Explains why the stage exists: which rule, grade, amount or hierarchy edge.
    requirement_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NOTE: there is deliberately no review_decision_id column here. It would
    # duplicate ReviewDecision.approval_task_id and, more importantly, create a
    # mutual foreign key between approval_tasks and review_decisions. A cycle like
    # that makes table creation order ambiguous for Alembic and would require a
    # deferred ALTER TABLE in every future schema rebuild. The single direction
    # (decision -> task) carries all the information: given a decision you can find
    # its task, and a task's decision is the one referencing it.

    __table_args__ = (
        UniqueConstraint("expense_id", "stage", "sequence"),
        in_enum("status", ApprovalTaskStatus),
        in_enum("required_role", RoleCode),
        CheckConstraint("sequence >= 0", name="sequence_non_negative"),
        CheckConstraint(
            "status NOT IN ('approved', 'rejected') OR "
            "(decided_at IS NOT NULL AND decided_by_user_id IS NOT NULL)",
            name="decision_requires_actor",
        ),
    )
