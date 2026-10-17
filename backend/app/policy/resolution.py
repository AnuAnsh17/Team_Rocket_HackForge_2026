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

from app.core.enums import (
    ApprovalState,
    PolicyAssignmentScopeType,
    PolicyReviewState,
    scope_selector_kind,
)
from app.core.logging import get_logger
from app.core.scope_keys import canonical_match_key
from app.models.policy import PolicyAssignment, PolicyVersion
from app.policy.base import EvaluationScope

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AppliedAssignment:
    """An assignment the resolver determined actually applies to this claim.

    Exactly one of ``scope_id`` / ``scope_key`` is populated, matching the
    dimension's selector kind. Both are carried so a reviewer-facing explanation can
    state what matched, rather than showing an id for a dimension that has none.
    """

    assignment_id: uuid.UUID
    scope_type: str
    priority: int
    scope_id: uuid.UUID | None = None
    scope_key: str | None = None

    @property
    def selector(self) -> str:
        """A printable form of whichever selector this dimension uses."""
        if self.scope_id is not None:
            return str(self.scope_id)
        return self.scope_key or ""


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


# Text matching delegates entirely to app/core/scope_keys.py. There is deliberately no
# local normalization here: the previous local implementation
# (``value.strip().casefold()``) differed from the database's
# ``lower(COALESCE(scope_key, ''))``, which let two keys the resolver considered
# identical both be stored. The contract now lives in one module, and ``scope_key``
# stores the canonical form, so the unique index and this comparison operate on exactly
# the same string.


def _presented_selector(scope: EvaluationScope, scope_type: str) -> uuid.UUID | str | None:
    """What this claim presents for one scope dimension, or None when unknown.

    ``None`` means the claim genuinely has no value for that dimension -- no trip, no
    category, an organization with no recorded jurisdiction. A dimension with no
    value cannot match any assignment, and the resolver reports the resulting
    absence of an applicable policy rather than assuming the dimension is satisfied.
    """
    member = PolicyAssignmentScopeType(scope_type)
    if member is PolicyAssignmentScopeType.ORGANIZATION:
        # Always known: a claim cannot exist outside an organization.
        return scope.organization_id
    if member is PolicyAssignmentScopeType.OFFICE_LOCATION:
        return scope.office_location_id
    if member is PolicyAssignmentScopeType.DEPARTMENT:
        return scope.department_id
    if member is PolicyAssignmentScopeType.COST_CENTER:
        return scope.cost_center_id
    if member is PolicyAssignmentScopeType.JOB_GRADE:
        return scope.job_grade_id
    if member is PolicyAssignmentScopeType.TRIP:
        return scope.trip_id
    if member is PolicyAssignmentScopeType.EMPLOYEE:
        return scope.membership_id
    if member is PolicyAssignmentScopeType.LEGAL_ENTITY:
        # The organization's recorded legal entity. A text dimension: there is no
        # legal_entities table, so there is no id to compare against.
        return canonical_match_key(scope.legal_entity_name)
    if member is PolicyAssignmentScopeType.JURISDICTION:
        return canonical_match_key(scope.jurisdiction_code)
    if member is PolicyAssignmentScopeType.EXPENSE_CATEGORY:
        return canonical_match_key(scope.category)
    raise ValueError(  # pragma: no cover - unreachable while the enum is exhaustive
        f"no selector is defined for scope type {member.value!r}"
    )


def _matches(assignment: PolicyAssignment, scope: EvaluationScope) -> bool:
    """Whether an assignment's scope actually applies to this claim.

    Dispatch is driven by ``scope_selector_kind``, which is the single source of
    truth for whether a dimension is identified by a UUID or by a text key. Every
    supported dimension is therefore handled by construction, and adding one to the
    enum without classifying it raises instead of silently never matching.
    """
    kind = scope_selector_kind(assignment.scope_type)
    presented = _presented_selector(scope, assignment.scope_type)
    if presented is None:
        return False
    if kind == "uuid":
        return assignment.scope_id is not None and assignment.scope_id == presented
    # Both sides are canonicalised. The stored key is required to be canonical already
    # (see app/core/scope_keys.py and the CHECK constraint), and canonicalising the
    # stored side as well means a legacy or out-of-band row still matches correctly
    # instead of silently never applying.
    stored = canonical_match_key(assignment.scope_key)
    return stored is not None and stored == presented


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
            assignment_id=a.id,
            scope_type=a.scope_type,
            priority=a.priority,
            scope_id=a.scope_id,
            scope_key=a.scope_key,
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
