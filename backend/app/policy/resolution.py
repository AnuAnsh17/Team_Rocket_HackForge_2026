"""Effective-policy resolution.

Resolution answers one question: **which approved policy version governs this
claim, and which allowances apply?**

The answer is allowed to be "unresolved". That is a first-class outcome, not an
error, and it is the correct answer whenever:

* no approved assignment covers the claim's scope;
* two assignments at equal priority point at different policy versions (a
  conflict, which must be resolved by a human rather than by a tie-break rule
  invented in code);
* the only matching assignment refers to a policy version that is not approved;
* a required dimension (for example the organization's timezone) is missing.

Precedence is NOT inferred from specificity. ``priority`` is compared only after
the resolver has established that both assignments genuinely apply, so the system
never silently assumes that "most specific wins" or that "a higher grade means a
higher allowance". Those are policy semantics, documented in
docs/role-policy-hierarchy.md and awaiting the real policy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ApprovalState, PolicyAssignmentScopeType, PolicyReviewState
from app.core.logging import get_logger
from app.models.policy import PolicyAssignment, PolicyVersion
from app.policy.base import EvaluationScope

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AppliedAssignment:
    assignment_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    priority: int


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    """The policy context that governs a claim."""

    resolved: bool
    policy_version_id: uuid.UUID | None = None
    version_label: str | None = None
    allowance_profile_id: uuid.UUID | None = None
    applied_assignments: tuple[AppliedAssignment, ...] = ()
    unresolved_reasons: tuple[str, ...] = ()
    dimensions_consulted: dict[str, str | None] = field(default_factory=dict)


def _matches(assignment: PolicyAssignment, scope: EvaluationScope) -> bool:
    """Whether an assignment's scope actually applies to this claim."""
    scope_type = assignment.scope_type
    if scope_type == PolicyAssignmentScopeType.ORGANIZATION.value:
        return assignment.scope_id == scope.organization_id
    if scope_type == PolicyAssignmentScopeType.OFFICE_LOCATION.value:
        return (
            scope.office_location_id is not None and assignment.scope_id == scope.office_location_id
        )
    if scope_type == PolicyAssignmentScopeType.DEPARTMENT.value:
        return scope.department_id is not None and assignment.scope_id == scope.department_id
    if scope_type == PolicyAssignmentScopeType.COST_CENTER.value:
        return scope.cost_center_id is not None and assignment.scope_id == scope.cost_center_id
    if scope_type == PolicyAssignmentScopeType.JOB_GRADE.value:
        return scope.job_grade_id is not None and assignment.scope_id == scope.job_grade_id
    if scope_type == PolicyAssignmentScopeType.TRIP.value:
        return scope.trip_id is not None and assignment.scope_id == scope.trip_id
    if scope_type == PolicyAssignmentScopeType.EMPLOYEE.value:
        return assignment.scope_id == scope.membership_id
    if scope_type == PolicyAssignmentScopeType.EXPENSE_CATEGORY.value:
        return scope.category is not None and str(assignment.scope_id) == scope.category
    # Legal entity and jurisdiction dimensions are modelled but cannot be matched
    # until the organization records them; treating an unmatched assignment as
    # applicable would be a guess.
    if scope_type in (
        PolicyAssignmentScopeType.LEGAL_ENTITY.value,
        PolicyAssignmentScopeType.JURISDICTION.value,
    ):
        return False
    return False


def resolve_effective_policy(
    session: Session,
    *,
    organization_id: uuid.UUID,
    scope: EvaluationScope,
    on_date: date | None,
) -> ResolvedPolicy:
    """Resolve the governing policy version for one claim.

    ``on_date`` is the claim's transaction date, used for the effective-period
    comparison. When it is None the resolution cannot be trusted and is reported
    as unresolved rather than evaluated against today's policy.
    """
    if on_date is None:
        return ResolvedPolicy(
            resolved=False,
            unresolved_reasons=(
                "the claim has no reliable transaction date, so the effective policy period "
                "cannot be determined",
            ),
            dimensions_consulted=scope.dimensions,
        )

    assignments = (
        session.execute(
            select(PolicyAssignment).where(
                PolicyAssignment.organization_id == organization_id,
                PolicyAssignment.approval_state == ApprovalState.APPROVED.value,
            )
        )
        .scalars()
        .all()
    )

    applicable = [
        assignment
        for assignment in assignments
        if _matches(assignment, scope)
        and (assignment.effective_from is None or assignment.effective_from <= on_date)
        and (assignment.effective_to is None or assignment.effective_to >= on_date)
    ]

    if not applicable:
        return ResolvedPolicy(
            resolved=False,
            unresolved_reasons=(
                "no approved policy assignment covers this claim's organization, context and "
                "effective period",
            ),
            dimensions_consulted=scope.dimensions,
        )

    versions = set()
    for assignment in applicable:
        version = session.get(PolicyVersion, assignment.policy_version_id)
        if version is None:
            continue
        if version.review_state == PolicyReviewState.APPROVED.value:
            versions.add(version.id)

    if not versions:
        return ResolvedPolicy(
            resolved=False,
            unresolved_reasons=(
                "the matching policy assignments reference policy versions that are not approved",
            ),
            dimensions_consulted=scope.dimensions,
        )

    if len(versions) > 1:
        # A genuine conflict. Tie-breaking here would invent policy semantics.
        return ResolvedPolicy(
            resolved=False,
            unresolved_reasons=(
                "multiple approved policy versions apply to this claim at the same scope; "
                "precedence is not configured, so the resolution is reported as unresolved "
                "instead of being guessed",
            ),
            dimensions_consulted=scope.dimensions,
        )

    policy_version_id = next(iter(versions))
    relevant = [a for a in applicable if a.policy_version_id == policy_version_id]
    top_priority = max(a.priority for a in relevant)
    applied = tuple(
        AppliedAssignment(
            assignment_id=a.id, scope_type=a.scope_type, scope_id=a.scope_id, priority=a.priority
        )
        for a in sorted(relevant, key=lambda a: (-a.priority, a.scope_type))
        if a.priority == top_priority
    )
    version = session.get(PolicyVersion, policy_version_id)

    return ResolvedPolicy(
        resolved=True,
        policy_version_id=policy_version_id,
        version_label=version.version_label if version else None,
        allowance_profile_id=next(
            (a.allowance_profile_id for a in relevant if a.allowance_profile_id), None
        ),
        applied_assignments=applied,
        dimensions_consulted=scope.dimensions,
    )
