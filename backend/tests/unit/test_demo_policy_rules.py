"""Unit tests for the fictional demo policy rules.

These exercise the registered implementation directly, so a test cannot pass against a
look-alike object that the registry would never use.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.enums import (
    ExpenseChannel,
    ExpenseStatus,
    FieldSource,
    FindingResult,
    RecommendedAction,
)
from app.models.policy import PolicyRule as PolicyRuleRow
from app.policy.base import ClaimView, EvaluationScope, FieldSnapshot, RuleContext
from app.policy.registry import (
    RegisteredRule,
    get_registered_rule,
    registered_evaluator_types,
    rule_applies_to_category,
)

pytestmark = pytest.mark.unit

CEILING_EVALUATOR = "demo_only_category_ceiling_v1"


def _amount_snapshot(
    value: str | None, *, source=FieldSource.EMPLOYEE_INPUT, reviewed=False, uncertain=None
) -> FieldSnapshot:
    return FieldSnapshot(
        value_decimal=Decimal(value) if value is not None else None,
        currency="INR",
        source=source,
        reviewed=reviewed,
        uncertainty_reason=uncertain,
    )


def _claim(
    *,
    category: str | None = "meal",
    amount: FieldSnapshot | None = None,
    currency: str | None = "INR",
) -> ClaimView:
    return ClaimView(
        expense_id=uuid.uuid4(),
        version=1,
        status=ExpenseStatus.DRAFT,
        channel=ExpenseChannel.WEB,
        merchant=FieldSnapshot(),
        expense_date=FieldSnapshot(value_date=date(2026, 8, 1), source=FieldSource.EMPLOYEE_INPUT),
        amount=amount if amount is not None else _amount_snapshot("1000.00"),
        currency=currency,
        category=category,
        business_purpose=None,
        client_name=None,
        attendee_count=None,
    )


def _context(
    claim: ClaimView,
    *,
    ceiling: object = "1500.00",
    category: object = "meal",
    clause: str = "DEMO-EXP-001",
) -> RuleContext:
    parameters: dict[str, object] = {}
    if category is not None:
        parameters["category"] = category
    if ceiling is not None:
        parameters["ceiling_amount"] = ceiling
    return RuleContext(
        claim=claim,
        scope=EvaluationScope(
            organization_id=uuid.uuid4(), membership_id=uuid.uuid4(), category=claim.category
        ),
        policy_version_id=uuid.uuid4(),
        policy_version_label="DEMO ONLY - fictional v2",
        rule_parameters=parameters,
        source_clause=clause,
        source_excerpt="DEMO ONLY: invented ceiling.",
    )


def _rule():
    implementation = get_registered_rule(CEILING_EVALUATOR)
    assert implementation is not None, "the category ceiling rule must be registered"
    return implementation


class TestCeilingOutcomes:
    def test_pass_below_the_ceiling(self) -> None:
        finding = _rule().evaluate(_context(_claim(amount=_amount_snapshot("1400.00"))))
        assert finding.result is FindingResult.PASS
        assert finding.recommended_action is RecommendedAction.NONE

    def test_pass_at_exactly_the_ceiling(self) -> None:
        """A ceiling is inclusive: the limit is satisfied at its boundary."""
        finding = _rule().evaluate(_context(_claim(amount=_amount_snapshot("1500.00"))))
        assert finding.result is FindingResult.PASS

    def test_fail_above_the_ceiling_carries_evidence(self) -> None:
        finding = _rule().evaluate(_context(_claim(amount=_amount_snapshot("1500.01"))))
        assert finding.result is FindingResult.FAIL
        assert "1500" in (finding.expected or "")
        assert "1500.01" in (finding.observed or "")
        assert finding.calculation, "a FAIL must be reviewable without re-deriving it"
        assert finding.evidence is not None
        assert finding.evidence["demo_only"] is True
        assert finding.evidence["policy_nature"] == "DEMO ONLY - FICTIONAL"
        assert finding.recommended_action is RecommendedAction.REVIEW

    def test_fail_never_asserts_a_decision(self) -> None:
        """A rule raises a review flag; it never approves or rejects a claim.

        RecommendedAction carries only advisory next steps (none/review/request_correction/
        escalate). There is deliberately no "approve" member to return, and the rule must
        stay inside that vocabulary.
        """
        finding = _rule().evaluate(_context(_claim(amount=_amount_snapshot("99999.00"))))
        assert finding.result in {FindingResult.PASS, FindingResult.FAIL, FindingResult.UNKNOWN}
        assert finding.recommended_action in set(RecommendedAction)
        assert finding.recommended_action is RecommendedAction.REVIEW
        assert "reject" not in finding.message.lower().split("not a rejection")[0]


class TestCeilingUnknown:
    def test_unknown_when_amount_is_missing(self) -> None:
        finding = _rule().evaluate(_context(_claim(amount=FieldSnapshot(currency="INR"))))
        assert finding.result is FindingResult.UNKNOWN
        assert finding.recommended_action is RecommendedAction.REVIEW

    def test_unknown_when_amount_has_no_provenance(self) -> None:
        claim = _claim(amount=_amount_snapshot("1000.00", source=None))
        assert _rule().evaluate(_context(claim)).result is FindingResult.UNKNOWN

    def test_unknown_when_extraction_is_unreviewed(self) -> None:
        claim = _claim(
            amount=_amount_snapshot(
                "1000.00", source=FieldSource.RECEIPT_EXTRACTION, reviewed=False
            )
        )
        assert _rule().evaluate(_context(claim)).result is FindingResult.UNKNOWN

    def test_unknown_when_amount_is_flagged_uncertain(self) -> None:
        claim = _claim(amount=_amount_snapshot("1000.00", uncertain="blurred total"))
        assert _rule().evaluate(_context(claim)).result is FindingResult.UNKNOWN

    def test_unknown_for_a_non_inr_claim(self) -> None:
        """No rate source exists, so a foreign amount must not be converted."""
        claim = _claim(amount=_amount_snapshot("100.00"), currency="USD")
        finding = _rule().evaluate(_context(claim))
        assert finding.result is FindingResult.UNKNOWN
        assert "INR" in finding.message

    def test_unknown_when_the_clause_is_missing(self) -> None:
        assert _rule().evaluate(_context(_claim(), ceiling=None)).result is FindingResult.UNKNOWN

    def test_unknown_when_the_ceiling_is_not_a_number(self) -> None:
        finding = _rule().evaluate(_context(_claim(), ceiling="not-a-number"))
        assert finding.result is FindingResult.UNKNOWN

    def test_unknown_for_a_mismatched_category(self) -> None:
        """Belt and braces: invoking the clause outside its category judges nothing."""
        context = _context(_claim(category="parking"), category="meal", ceiling="1500.00")
        finding = _rule().evaluate(context)
        assert finding.result is FindingResult.UNKNOWN
        assert finding.recommended_action is RecommendedAction.NONE

    def test_unknown_is_never_a_pass(self) -> None:
        for claim in (
            _claim(amount=FieldSnapshot(currency="INR")),
            _claim(amount=_amount_snapshot("1000.00", source=None)),
            _claim(amount=_amount_snapshot("1.00"), currency="EUR"),
        ):
            assert _rule().evaluate(_context(claim)).result is not FindingResult.PASS


class TestApplicability:
    """A clause must not be applied to an unrelated category."""

    def _registered(self, category: str | None) -> RegisteredRule:
        return RegisteredRule(
            row_id=uuid.uuid4(),
            rule_id="demo_only_ceiling_meal",
            policy_version_id=uuid.uuid4(),
            version_label="v2",
            evaluator_type=CEILING_EVALUATOR,
            parameters={},
            source_clause="DEMO-EXP-001",
            source_excerpt=None,
            source_reference=None,
            implementation=_rule(),
            applicable_category=category,
        )

    def test_category_clause_matches_only_its_own_category(self) -> None:
        meal = self._registered("meal")
        assert rule_applies_to_category(meal, "meal") is True
        assert rule_applies_to_category(meal, "parking") is False
        assert rule_applies_to_category(meal, None) is False

    def test_general_clause_applies_to_every_category(self) -> None:
        general = self._registered(None)
        assert rule_applies_to_category(general, "meal") is True
        assert rule_applies_to_category(general, "anything") is True

    def test_matching_ignores_case_and_padding(self) -> None:
        assert rule_applies_to_category(self._registered("Meal"), " meal ") is True

    def test_ten_category_clauses_are_registered_as_one_evaluator(self) -> None:
        assert CEILING_EVALUATOR in registered_evaluator_types()


class TestDecimalArithmetic:
    def test_comparison_is_exact_and_not_binary_float(self) -> None:
        """0.1 + 0.2 != 0.3 in binary floating point; it must be exact here."""
        finding = _rule().evaluate(
            _context(_claim(amount=_amount_snapshot("0.30")), ceiling="0.30")
        )
        assert finding.result is FindingResult.PASS
        # The same value expressed with trailing noise would be a FAIL, proving no float
        # rounding is quietly applied.
        above = _rule().evaluate(
            _context(_claim(amount=_amount_snapshot("0.30000000000000004")), ceiling="0.30")
        )
        assert above.result is FindingResult.FAIL

    def test_evidence_records_decimal_strings(self) -> None:
        finding = _rule().evaluate(_context(_claim(amount=_amount_snapshot("1600.00"))))
        assert finding.evidence is not None
        assert finding.evidence["observed_amount"] == "1600.00"
        assert finding.evidence["ceiling_amount"] == "1500.00"

    def test_rule_reads_no_amount_literal(self) -> None:
        """The ceiling comes from parameters; the source must contain no money literal."""
        import inspect

        source = inspect.getsource(_rule().__class__)
        assert "1500" not in source and 'Decimal("1' not in source
        assert PolicyRuleRow is not None
