"""Policy DTOs.

Every DTO here carries provenance: which document, which clause, which version,
and who validated it. A finding that cannot name its source clause is not a
finding this system is willing to present as policy-backed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.core.enums import ApprovalState, PolicyReviewState
from app.schemas.common import ApiModel, MoneyString, Page, SourceReference


class PolicyRuleSummary(ApiModel):
    """A rule as exposed to reviewers and administrators."""

    id: uuid.UUID
    rule_id: str
    title: str
    category: str | None = None
    evaluator_type: str | None = Field(
        default=None,
        description="Server-side evaluator identifier. Present for auditability, not for clients to run.",
    )
    parameters: dict[str, object] | None = Field(
        default=None,
        description="Validated parameters only. Null when no verified clause supplied them.",
    )
    source_reference: SourceReference | None = None
    review_state: PolicyReviewState
    is_active: bool = Field(
        ...,
        description=(
            "True only when the rule has a verified source clause and a recorded human "
            "validator. In this scaffold every rule is inactive."
        ),
    )
    validated_at: datetime | None = None


class PolicyVersionSummary(ApiModel):
    id: uuid.UUID
    version_label: str
    document_title: str
    document_sha256: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    review_state: PolicyReviewState
    approved_at: datetime | None = None
    rule_count: int = Field(0, ge=0)
    active_rule_count: int = Field(0, ge=0)


class PolicyVersionListResponse(Page[PolicyVersionSummary]):
    pass


class AllowanceProfileSummary(ApiModel):
    id: uuid.UUID
    code: str
    name: str
    currency: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    review_state: PolicyReviewState
    item_count: int = Field(0, ge=0)
    item_count_with_source: int = Field(
        0,
        ge=0,
        description="Items carrying a verified source clause. A subset of item_count by construction.",
    )


class PolicyAssignmentSummary(ApiModel):
    """One resolved or configured policy assignment."""

    id: uuid.UUID
    policy_version_id: uuid.UUID
    version_label: str
    scope_type: str
    scope_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Selector for a UUID-valued dimension (organization, office location, department, "
            "cost center, job grade, trip, employee). Exactly one of scope_id and scope_key is "
            "populated, according to the dimension."
        ),
    )
    scope_key: str | None = Field(
        default=None,
        description=(
            "Selector for a text-valued dimension (legal entity, jurisdiction, expense "
            "category), which has no table and therefore no id to point at."
        ),
    )
    priority: int
    approval_state: ApprovalState
    effective_from: date | None = None
    effective_to: date | None = None
    allowance_profile_id: uuid.UUID | None = None


class EffectivePolicyResponse(ApiModel):
    """The outcome of policy resolution for one subject and context.

    ``resolved`` is false whenever the resolution is ambiguous, incomplete or
    conflicting. That is a first-class answer, not an error: the caller is told
    that the policy context is unknown instead of being handed a guess.
    """

    resolved: bool
    policy_version: PolicyVersionSummary | None = None
    allowance_profile: AllowanceProfileSummary | None = None
    applied_assignments: list[PolicyAssignmentSummary] = Field(default_factory=list)
    active_exceptions: list[dict[str, object]] = Field(default_factory=list)
    unresolved_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Human-readable reasons the resolution is unresolved, for example "
            "'no approved policy version is assigned for this scope'."
        ),
    )
    resolution_dimensions: dict[str, str | None] = Field(
        default_factory=dict,
        description=(
            "The dimensions consulted (organization, office, grade, department, cost center, "
            "trip, exception) with the value used for each. Null means the dimension was absent."
        ),
    )


class PolicyCheckRequest(ApiModel):
    """Advisory pre-flight input. Writes nothing."""

    expense_id: uuid.UUID | None = Field(
        default=None,
        description="Optional existing draft to check. When null, the inline fields below are used.",
    )
    category: str | None = None
    amount: MoneyString | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expense_date: date | None = None
    trip_id: uuid.UUID | None = None
    client_name: str | None = None
    attendee_count: int | None = Field(default=None, ge=0)
    business_purpose: str | None = None


class PolicyCheckResponse(ApiModel):
    advisory: bool = Field(
        True,
        description=(
            "Always true. A pre-flight result is guidance only: aggregate state and reviewer "
            "decisions can change after submission, and reimbursement is never promised here."
        ),
    )
    resolved: bool
    unresolved_reasons: list[str] = Field(default_factory=list)
    policy_version: PolicyVersionSummary | None = None
    findings: list[dict[str, object]] = Field(
        default_factory=list,
        description="Same finding schema as a persisted finding, but not written to the database.",
    )
