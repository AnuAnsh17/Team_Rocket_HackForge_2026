"""Re-evaluation planning.

A new claim, a correction, a status change that alters an aggregate basis, a
policy-version change or a duplicate resolution can all invalidate findings on
*other* claims. This module decides which claims must be re-evaluated and why,
without performing the work.

Two constraints from the build plan shape the design:

* "A new expense may change an aggregate finding on other claims. Record that
  change as a new evaluation/finding event rather than silently rewriting the
  past." So a re-evaluation appends findings and marks superseded ones; it never
  deletes.
* "If totals are materialized, provide reconciliation/rebuild logic." No aggregate
  table exists in this schema, so there is nothing to reconcile and no rebuild
  path to get wrong. Aggregates are computed by query over the included claims,
  which is why this module can stay small.

The planner is allowed to return an empty plan with a reason. That is the correct
answer while no aggregate rule is active, which is the current state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class ReEvaluationTrigger(StrEnum):
    """What changed. Each trigger names a different affected set."""

    RECEIPT_UPLOADED = "receipt_uploaded"
    RECEIPT_REEXTRACTED = "receipt_reextracted"
    EMPLOYEE_CORRECTION = "employee_correction"
    REVIEWER_CORRECTION = "reviewer_correction"
    STATUS_CHANGED = "status_changed"
    POLICY_VERSION_CHANGED = "policy_version_changed"
    ALLOWANCE_ASSIGNMENT_CHANGED = "allowance_assignment_changed"
    MEMBERSHIP_CONTEXT_CHANGED = "membership_context_changed"
    DUPLICATE_RESOLVED = "duplicate_resolved"


@dataclass(frozen=True, slots=True)
class ReEvaluationTarget:
    expense_id: uuid.UUID
    reason: str
    trigger: ReEvaluationTrigger


@dataclass(frozen=True, slots=True)
class ReEvaluationPlan:
    """Which claims to re-evaluate, and why the plan looks the way it does."""

    trigger: ReEvaluationTrigger
    source_expense_id: uuid.UUID | None = None
    targets: tuple[ReEvaluationTarget, ...] = ()
    skipped_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.targets


def plan_reevaluation(
    *,
    trigger: ReEvaluationTrigger,
    source_expense_id: uuid.UUID | None = None,
    aggregate_contributors: tuple[uuid.UUID, ...] = (),
    aggregate_rules_active: bool = False,
) -> ReEvaluationPlan:
    """Build a re-evaluation plan for one trigger.

    ``aggregate_rules_active`` is False in this build, because no policy rule can
    be activated without a verified clause. With no aggregate rule in play, a
    change to one claim cannot affect another claim's findings, so the honest plan
    is "re-evaluate only the changed claim" - stated explicitly rather than left
    as silence.
    """
    skipped: list[str] = []
    targets: list[ReEvaluationTarget] = []

    if source_expense_id is not None:
        targets.append(
            ReEvaluationTarget(
                expense_id=source_expense_id,
                reason=f"the claim itself changed ({trigger.value})",
                trigger=trigger,
            )
        )

    if aggregate_rules_active:
        for contributor_id in aggregate_contributors:
            if contributor_id == source_expense_id:
                continue
            targets.append(
                ReEvaluationTarget(
                    expense_id=contributor_id,
                    reason=(
                        "this claim contributes to an aggregate scope whose basis changed "
                        f"({trigger.value})"
                    ),
                    trigger=trigger,
                )
            )
    else:
        skipped.append(
            "no aggregate or context rule is active, so other claims cannot be affected by this "
            "change; only the changed claim is re-evaluated"
        )

    if trigger in (
        ReEvaluationTrigger.POLICY_VERSION_CHANGED,
        ReEvaluationTrigger.ALLOWANCE_ASSIGNMENT_CHANGED,
        ReEvaluationTrigger.MEMBERSHIP_CONTEXT_CHANGED,
    ):
        skipped.append(
            "a scope-wide re-evaluation requires an approved policy assignment, which does not "
            "exist yet; the sweep is recorded as skipped rather than silently performed over an "
            "empty rule set"
        )

    return ReEvaluationPlan(
        trigger=trigger,
        source_expense_id=source_expense_id,
        targets=tuple(targets),
        skipped_reasons=tuple(skipped),
    )
