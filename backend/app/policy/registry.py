"""Rule registry.

The registry is the only place that turns stored rule rows into executable rule
objects. In this scaffold it holds **zero rules**, because no authoritative policy
document has been supplied, and a rule cannot be activated without a verified
source clause and a named human validator (enforced by
``policy_rules.source_requires_validation``).

Adding a rule therefore requires three things, in this order:
  1. A verified clause in the real policy document.
  2. A human-validated parameters row with review_state = 'approved'.
  3. An evaluator implementation registered below, with PASS/FAIL/UNKNOWN tests.

An unregistered ``evaluator_type`` is reported as a diagnostic rather than
silently skipped, so a database row that claims to be active but has no code
behind it cannot quietly reduce coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    FindingResult,
    FindingSeverity,
    FindingType,
    PolicyReviewState,
    RecommendedAction,
)
from app.core.logging import get_logger
from app.core.scope_keys import canonical_match_key
from app.models.policy import PolicyRule as PolicyRuleRow
from app.policy.base import FindingDraft, PolicyRule, RuleContext

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RegisteredRule:
    """A rule row joined to its executable implementation."""

    row_id: UUID
    rule_id: str
    policy_version_id: UUID
    version_label: str
    evaluator_type: str | None
    parameters: dict[str, object]
    source_clause: str | None
    source_excerpt: str | None
    source_reference: dict[str, object] | None
    implementation: PolicyRule
    # The single category this clause is scoped to, or None for a clause that applies to
    # every category. Populated from the stored rule row so applicability comes from policy
    # data rather than from a list maintained in code.
    applicable_category: str | None = None


@dataclass(frozen=True, slots=True)
class RegistryLoad:
    """The outcome of loading the registry for one policy version."""

    rules: tuple[RegisteredRule, ...] = ()
    unregistered_evaluator_types: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.rules


# Executable rule implementations, keyed by evaluator_type. Empty by design:
# populating this requires a verified clause and validated parameters.
_RULE_IMPLEMENTATIONS: dict[str, PolicyRule] = {}


class _DemoMealCapRule:
    """Fictional rule used only when an explicit local demo flag is enabled."""

    rule_id = "demo_only_meal_cap"
    evaluator_type = "demo_only_meal_cap_v1"

    def evaluate(self, context: RuleContext) -> FindingDraft:
        claim = context.claim
        amount = claim.amount
        if claim.category != "meal":
            return FindingDraft(
                rule_id=self.rule_id,
                finding_type=FindingType.MISSING_POLICY_CONTEXT,
                result=FindingResult.UNKNOWN,
                severity=FindingSeverity.INFO,
                message="The fictional demo rule applies only to the synthetic meal category.",
                recommended_action=RecommendedAction.NONE,
            )
        if not amount.usable or amount.value_decimal is None or claim.currency != "INR":
            return FindingDraft(
                rule_id=self.rule_id,
                finding_type=FindingType.MISSING_POLICY_CONTEXT,
                result=FindingResult.UNKNOWN,
                severity=FindingSeverity.WARNING,
                message="The fictional demo rule cannot evaluate the available amount evidence.",
                recommended_action=RecommendedAction.REVIEW,
            )
        cap = context.rule_parameters.get("synthetic_cap")
        from decimal import Decimal, InvalidOperation

        try:
            threshold = Decimal(str(cap))
        except (InvalidOperation, TypeError, ValueError):
            return FindingDraft(
                rule_id=self.rule_id,
                finding_type=FindingType.MISSING_POLICY_CONTEXT,
                result=FindingResult.UNKNOWN,
                severity=FindingSeverity.WARNING,
                message="The synthetic demo rule configuration is invalid.",
                recommended_action=RecommendedAction.REVIEW,
            )
        passed = amount.value_decimal <= threshold
        return FindingDraft(
            rule_id=self.rule_id,
            finding_type=FindingType.INDIVIDUAL_LIMIT_EXCEEDED,
            result=FindingResult.PASS if passed else FindingResult.FAIL,
            severity=FindingSeverity.INFO if passed else FindingSeverity.WARNING,
            message=(
                "Fictional demo policy: the synthetic meal amount is within the demo cap."
                if passed
                else "Fictional demo policy: the synthetic meal amount exceeds the demo cap."
            ),
            recommended_action=RecommendedAction.NONE if passed else RecommendedAction.REVIEW,
            source_reference=None,
            expected=f"at most {threshold} INR (synthetic demo fixture only)",
            observed=f"{amount.value_decimal} {claim.currency}",
            evidence={"synthetic_demo_rule": True},
        )


class _DemoCategoryCeilingRule:
    """Fictional per-claim ceiling for one expense category.

    Everything this rule needs comes from the validated rule parameters: the category it
    is scoped to and the ceiling amount. No amount is written here, which is what keeps a
    threshold out of the source tree and in a reviewable, validated row.

    The rule never decides anything. It reports PASS, FAIL or UNKNOWN and leaves the
    reimbursement decision to a human reviewer. Only the local demo flags can cause it to
    be loaded at all - see ``load_registry``.
    """

    rule_id = "demo_only_category_ceiling"
    evaluator_type = "demo_only_category_ceiling_v1"

    def _unknown(
        self,
        context: RuleContext,
        message: str,
        *,
        severity: FindingSeverity = FindingSeverity.WARNING,
        action: RecommendedAction = RecommendedAction.REVIEW,
    ) -> FindingDraft:
        return FindingDraft(
            rule_id=self.rule_id,
            finding_type=FindingType.MISSING_POLICY_CONTEXT,
            result=FindingResult.UNKNOWN,
            severity=severity,
            message=message,
            recommended_action=action,
            evidence={
                "demo_only": True,
                "policy_nature": "DEMO ONLY - FICTIONAL",
                "category": context.claim.category,
            },
        )

    def evaluate(self, context: RuleContext) -> FindingDraft:
        claim = context.claim
        parameters = context.rule_parameters
        declared_category = parameters.get("category")

        # Applicability. The evaluator already filters by category, so reaching this branch
        # means the rule was invoked outside that path; it answers UNKNOWN rather than
        # judging a claim it does not govern.
        if declared_category is not None and (
            canonical_match_key(str(declared_category)) != canonical_match_key(claim.category)
        ):
            return self._unknown(
                context,
                "This fictional clause is scoped to a different expense category, so it "
                "does not apply to this claim.",
                severity=FindingSeverity.INFO,
                action=RecommendedAction.NONE,
            )

        raw_ceiling = parameters.get("ceiling_amount")
        if raw_ceiling is None:
            return self._unknown(
                context,
                "The fictional demo ceiling for this category is not configured, so the "
                "claim cannot be checked against it.",
            )
        try:
            ceiling = Decimal(str(raw_ceiling))
        except (InvalidOperation, TypeError, ValueError):
            return self._unknown(
                context,
                "The fictional demo ceiling for this category is not a usable amount, so "
                "the claim cannot be checked against it.",
            )
        if not ceiling.is_finite():
            return self._unknown(
                context,
                "The fictional demo ceiling for this category is not a finite amount.",
            )

        # Currency: the ceilings are INR-only and no rate source is approved, so a foreign
        # currency claim is UNKNOWN. Converting here would invent an exchange rate.
        if claim.currency != "INR":
            return self._unknown(
                context,
                "The fictional demo ceilings are defined in INR only and no exchange rate "
                "source is configured, so this claim cannot be compared against a ceiling. "
                "It is reported as UNKNOWN rather than converted.",
            )

        amount = claim.amount
        if not amount.usable or amount.value_decimal is None:
            return self._unknown(
                context,
                "The claim amount is missing, unreadable, or has no reviewed provenance, "
                "so the fictional ceiling cannot be applied to it.",
            )

        observed = amount.value_decimal
        passed = observed <= ceiling
        clause = context.source_clause or "DEMO-EXP"
        return FindingDraft(
            rule_id=self.rule_id,
            finding_type=FindingType.INDIVIDUAL_LIMIT_EXCEEDED,
            result=FindingResult.PASS if passed else FindingResult.FAIL,
            severity=FindingSeverity.INFO if passed else FindingSeverity.WARNING,
            message=(
                f"Fictional demo policy ({clause}): the claimed {observed} INR is within the "
                f"invented ceiling of {ceiling} INR for this category. This is not a "
                "reimbursement decision and requires human review."
                if passed
                else f"Fictional demo policy ({clause}): the claimed {observed} INR exceeds "
                f"the invented ceiling of {ceiling} INR for this category. This is a review "
                "flag, not a rejection; a finance reviewer decides."
            ),
            employee_message=(
                None
                if passed
                else "This claim is above a policy ceiling used for this demonstration. A "
                "reviewer will look at it."
            ),
            recommended_action=RecommendedAction.NONE if passed else RecommendedAction.REVIEW,
            calculation=(
                f"{observed} INR compared with the fictional ceiling {ceiling} INR ({clause})"
            ),
            expected=f"at most {ceiling} INR per claim (fictional demo clause {clause})",
            observed=f"{observed} INR",
            evidence={
                "demo_only": True,
                "policy_nature": "DEMO ONLY - FICTIONAL",
                "clause": clause,
                "category": claim.category,
                "ceiling_amount": str(ceiling),
                "observed_amount": str(observed),
                "currency": claim.currency,
                "amount_source": amount.source.value if amount.source else None,
                "amount_reviewed": amount.reviewed,
            },
        )


_RULE_IMPLEMENTATIONS[_DemoMealCapRule.evaluator_type] = _DemoMealCapRule()
_RULE_IMPLEMENTATIONS[_DemoCategoryCeilingRule.evaluator_type] = _DemoCategoryCeilingRule()


def rule_applies_to_category(rule: RegisteredRule, category: str | None) -> bool:
    """Whether a clause is in scope for a claim's category.

    A clause with no category applies to every claim. A clause with a category applies
    only when the claim's category matches it, compared with the same canonicalisation
    used for scope keys so the two never disagree.

    This exists so a claim is evaluated against the clauses that actually govern it. The
    alternative - running every category clause against every claim - produces a page of
    unrelated findings, which is worse than no finding at all.
    """
    if rule.applicable_category is None:
        return True
    return canonical_match_key(rule.applicable_category) == canonical_match_key(category)


def register_rule(implementation: PolicyRule) -> None:
    """Register one executable rule implementation."""
    if implementation.evaluator_type in _RULE_IMPLEMENTATIONS:
        raise ValueError(f"evaluator_type {implementation.evaluator_type!r} is already registered")
    _RULE_IMPLEMENTATIONS[implementation.evaluator_type] = implementation


def registered_evaluator_types() -> tuple[str, ...]:
    return tuple(sorted(_RULE_IMPLEMENTATIONS))


def get_registered_rule(evaluator_type: str) -> PolicyRule | None:
    """The executable implementation behind an evaluator type, if any.

    Public so tests exercise the implementation the registry would actually run, rather
    than a second instance constructed for the test.
    """
    return _RULE_IMPLEMENTATIONS.get(evaluator_type)


def load_registry(session: Session, *, policy_version_id: UUID) -> RegistryLoad:
    """Load every active, approved rule for one policy version.

    Activation is re-checked here rather than trusted from the row, so a row that
    was approved and then had its clause removed cannot still execute.
    """
    rows = (
        session.execute(
            select(PolicyRuleRow).where(
                PolicyRuleRow.policy_version_id == policy_version_id,
                PolicyRuleRow.is_active.is_(True),
                PolicyRuleRow.review_state == PolicyReviewState.APPROVED.value,
            )
        )
        .scalars()
        .all()
    )

    registered: list[RegisteredRule] = []
    unregistered: list[str] = []
    warnings: list[str] = []

    for row in rows:
        if row.rule_id.startswith("demo_only_") and not (
            settings.demo_synthetic_policy_enabled
            and settings.app_env in ("development", "test")
            and settings.demo_mode
        ):
            continue
        if not row.source_clause or not row.validated_at:
            warnings.append(
                f"rule {row.rule_id!r} is marked active but lacks a verified clause or "
                "validation record; it will not be executed"
            )
            continue
        implementation = (
            _RULE_IMPLEMENTATIONS.get(row.evaluator_type) if row.evaluator_type else None
        )
        if implementation is None:
            unregistered.append(row.evaluator_type or "<none>")
            continue
        registered.append(
            RegisteredRule(
                row_id=row.id,
                rule_id=row.rule_id,
                policy_version_id=row.policy_version_id,
                version_label="",
                evaluator_type=row.evaluator_type,
                parameters=row.parameters or {},
                source_clause=row.source_clause,
                source_excerpt=row.source_excerpt,
                source_reference=row.source_reference,
                implementation=implementation,
                applicable_category=row.category,
            )
        )

    if unregistered:
        logger.warning(
            "active policy rules have no registered implementation",
            extra={"evaluator_types": unregistered},
        )
    return RegistryLoad(
        rules=tuple(registered),
        unregistered_evaluator_types=tuple(sorted(set(unregistered))),
        warnings=tuple(warnings),
    )
