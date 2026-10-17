"""Policy rule interface and typed evaluation context.

This module defines what a rule *is*. It deliberately contains no threshold, no
limit, no city cap, no time window and no exchange rate. Those values come from a
verified source clause and are stored with the rule; they are never literals in
code.

The tri-state contract is the centre of the design:

* ``PASS``    - reliable information exists and the rule is satisfied.
* ``FAIL``    - reliable information exists and the rule is breached.
* ``UNKNOWN`` - required fields, context or reliable evidence are missing.

``UNKNOWN`` must never be silently converted into ``PASS``. It routes to an
employee correction, a reviewer assessment, or a non-blocking notice depending on
the rule's impact, and that routing decision is carried on the finding itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.core.enums import (
    ExpenseChannel,
    ExpenseStatus,
    FieldSource,
    FindingResult,
    FindingSeverity,
    FindingType,
    RecommendedAction,
)
from app.schemas.common import SourceReference


@dataclass(frozen=True, slots=True)
class FieldSnapshot:
    """One claim field as the evaluator sees it."""

    value_text: str | None = None
    value_decimal: Decimal | None = None
    value_date: date | None = None
    value_integer: int | None = None
    currency: str | None = None
    source: FieldSource | None = None
    reviewed: bool = False
    confidence: float | None = None
    uncertainty_reason: str | None = None

    @property
    def usable(self) -> bool:
        """Whether the value may be relied on for a deterministic decision.

        A value whose provenance is unknown, or which is explicitly flagged
        uncertain, is not treated as reliable. This is the single place that
        decides that question, so no rule re-implements it inconsistently.
        """
        if self.source is None:
            return False
        if self.source is FieldSource.RECEIPT_EXTRACTION and not self.reviewed:
            return False
        return self.uncertainty_reason is None


@dataclass(frozen=True, slots=True)
class RelatedExpense:
    """Another claim inside the evaluated scope, for aggregate rules."""

    expense_id: uuid.UUID
    version: int
    expense_date: date | None
    amount: Decimal | None
    currency: str | None
    status: ExpenseStatus
    category: str | None
    trip_id: uuid.UUID | None
    office_location_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class EvaluationScope:
    """The resolved context a rule is evaluated against.

    ``fingerprint`` is a stable hash over the scope and its contributing claim
    versions. Evaluation is idempotent for a given
    (claim version, policy version, scope fingerprint), which is what stops a
    retry from producing duplicate findings.
    """

    organization_id: uuid.UUID
    membership_id: uuid.UUID
    office_location_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    job_grade_id: uuid.UUID | None = None
    jurisdiction_code: str | None = None
    timezone: str | None = None
    trip_id: uuid.UUID | None = None
    trip_destination_city: str | None = None
    category: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    related_expenses: tuple[RelatedExpense, ...] = ()
    fingerprint: str = ""
    unresolved_reasons: tuple[str, ...] = ()
    dimensions: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClaimView:
    """Read-only snapshot of the claim under evaluation."""

    expense_id: uuid.UUID
    version: int
    status: ExpenseStatus
    channel: ExpenseChannel
    merchant: FieldSnapshot
    expense_date: FieldSnapshot
    amount: FieldSnapshot
    currency: str | None
    category: str | None
    business_purpose: str | None
    client_name: str | None
    attendee_count: int | None
    line_item_count: int = 0
    receipt_count: int = 0
    has_failed_extraction: bool = False
    context_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Everything a rule is allowed to look at."""

    claim: ClaimView
    scope: EvaluationScope
    policy_version_id: uuid.UUID
    policy_version_label: str
    rule_parameters: dict[str, object] = field(default_factory=dict)
    source_clause: str | None = None
    source_excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class FindingDraft:
    """A finding a rule wants to raise, before persistence."""

    rule_id: str
    finding_type: FindingType
    result: FindingResult
    severity: FindingSeverity
    message: str
    recommended_action: RecommendedAction = RecommendedAction.REVIEW
    employee_message: str | None = None
    source_reference: SourceReference | None = None
    evidence: dict[str, object] | None = None
    calculation: str | None = None
    expected: str | None = None
    observed: str | None = None

    def __post_init__(self) -> None:
        if self.result is FindingResult.FAIL and not (self.expected or self.calculation):
            raise ValueError(
                "A FAIL finding must carry either the expected condition or the "
                "deterministic calculation that produced it. A failure without "
                "evidence cannot be reviewed or defended."
            )


@runtime_checkable
class PolicyRule(Protocol):
    """A deterministic rule implementation.

    Implementations must be pure: same context in, same finding out. No network
    call, no clock read and no dependence on wall-clock time. Where a rule needs
    the current date it takes it from the scope.
    """

    rule_id: str
    evaluator_type: str

    def evaluate(self, context: RuleContext) -> FindingDraft:
        """Return exactly one PASS, FAIL or UNKNOWN finding with evidence."""
        ...
