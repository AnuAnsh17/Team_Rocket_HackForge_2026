"""Finding, duplicate candidate, decision and approval task DTOs."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field, model_validator

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
from app.schemas.common import ApiModel, Page, SourceReference


class FindingResponse(ApiModel):
    """One rule outcome, with everything needed to explain it.

    ``result`` is tri-state and ``UNKNOWN`` is a valid, non-accusatory answer.
    ``recommended_action`` is advisory: it does not itself change the claim.
    """

    id: uuid.UUID
    expense_id: uuid.UUID
    type: FindingType
    rule_id: str
    policy_version_id: uuid.UUID | None = None
    policy_version_label: str | None = None
    result: FindingResult
    severity: FindingSeverity
    message: str = Field(..., description="Reviewer-facing explanation.")
    employee_message: str | None = Field(
        default=None,
        description=(
            "Employee-facing wording. Deliberately separate from the reviewer message and "
            "never accusatory."
        ),
    )
    source_reference: SourceReference | None = Field(
        default=None,
        description=(
            "The verified clause the rule came from. Null only for structural checks that do not "
            "depend on a policy clause."
        ),
    )
    evidence: dict[str, object] | None = None
    calculation: str | None = None
    expected: str | None = None
    observed: str | None = None
    recommended_action: RecommendedAction
    status: FindingStatus
    expense_version: int
    resolved_at: datetime | None = None
    superseded_by_finding_id: uuid.UUID | None = None
    created_at: datetime


class FindingListResponse(Page[FindingResponse]):
    pass


class ResolveFindingRequest(ApiModel):
    """Resolve or dismiss a finding with a recorded reason."""

    status: FindingStatus = Field(
        ..., description="Either resolved or dismissed. A finding is never deleted."
    )
    reason_code: str | None = Field(default=None, max_length=80)
    reason: str = Field(
        ..., min_length=1, description="Required and recorded in the audit history."
    )
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optional optimistic-concurrency check against the parent claim version.",
    )

    @model_validator(mode="after")
    def _only_resolvable_states(self) -> ResolveFindingRequest:
        if self.status not in (FindingStatus.RESOLVED, FindingStatus.DISMISSED):
            raise ValueError("status must be 'resolved' or 'dismissed'")
        return self


class DuplicateSignal(ApiModel):
    """One independent similarity signal behind a duplicate candidate."""

    signal_type: str = Field(
        ...,
        description="exact_hash | perceptual_similarity | normalized_field_match | channel_context",
    )
    matched: bool
    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Ranking signal only. Not a calibrated probability unless it has been evaluated.",
    )
    detail: str | None = None


class DuplicateCandidateResponse(ApiModel):
    """A possible duplicate pair. Never a confirmed duplicate and never fraud."""

    id: uuid.UUID
    status: DuplicateStatus
    expense_a_id: uuid.UUID
    expense_b_id: uuid.UUID
    algorithm_version: str
    signals: list[DuplicateSignal] = Field(default_factory=list)
    ranking_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Ordering signal for the review queue. Confirmation always requires a human.",
    )
    cross_channel: bool = False
    reviewed_at: datetime | None = None
    resolution_reason: str | None = None
    created_at: datetime


class DuplicateListResponse(Page[DuplicateCandidateResponse]):
    pass


class ResolveDuplicateRequest(ApiModel):
    """Confirm or dismiss a candidate, with a mandatory reason."""

    reason_code: str | None = Field(default=None, max_length=80)
    reason: str = Field(..., min_length=1)


class ReviewDecisionResponse(ApiModel):
    """An executed decision, as shown in the audit timeline."""

    id: uuid.UUID
    expense_id: uuid.UUID
    actor_user_id: uuid.UUID
    actor_display_name: str | None = None
    action: ReviewAction
    reason_code: str | None = None
    reason: str | None = None
    notes: str | None = None
    previous_status: str | None = None
    new_status: str
    expense_version: int
    created_at: datetime


class DecisionRequest(ApiModel):
    """A reviewer action.

    ``expected_version`` is mandatory: a decision based on a stale claim view is
    refused with STALE_VERSION rather than silently overwriting newer work.
    """

    action: ReviewAction
    reason_code: str | None = Field(default=None, max_length=80)
    reason: str | None = None
    notes: str | None = None
    expected_version: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _reason_required(self) -> DecisionRequest:
        if self.action in (
            ReviewAction.REJECT,
            ReviewAction.REQUEST_CORRECTION,
        ) and (not self.reason or not self.reason.strip()):
            raise ValueError(f"a reason is required when action is {self.action.value}")
        return self


class ApprovalTaskResponse(ApiModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    stage: str
    sequence: int = Field(..., ge=0)
    required_role: RoleCode | None = None
    assignee_membership_id: uuid.UUID | None = None
    status: ApprovalTaskStatus
    is_required: bool = True
    requirement_basis: str | None = Field(
        default=None,
        description="Why this stage exists: the rule, grade, amount or hierarchy edge that required it.",
    )
    due_at: date | None = None
    decided_at: datetime | None = None
