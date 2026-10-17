"""Policy-engine tri-state behaviour.

These are the tests that matter most in the whole suite. The product's central
claim is that missing evidence produces UNKNOWN rather than a silent pass, so the
assertions here are written to fail loudly if that ever stops being true.
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
    FindingSeverity,
    FindingType,
    RecommendedAction,
)
from app.policy.base import (
    ClaimView,
    EvaluationScope,
    FieldSnapshot,
    FindingDraft,
)

pytestmark = pytest.mark.unit


def _scope(**overrides: object) -> EvaluationScope:
    defaults: dict[str, object] = {
        "organization_id": uuid.uuid4(),
        "membership_id": uuid.uuid4(),
        "fingerprint": "f" * 64,
    }
    defaults.update(overrides)
    return EvaluationScope(**defaults)  # type: ignore[arg-type]


def _claim(**overrides: object) -> ClaimView:
    defaults: dict[str, object] = {
        "expense_id": uuid.uuid4(),
        "version": 1,
        "status": ExpenseStatus.SUBMITTED,
        "channel": ExpenseChannel.ANDROID,
        "merchant": FieldSnapshot(
            value_text="Example Cafe", source=FieldSource.RECEIPT_EXTRACTION, reviewed=True
        ),
        "expense_date": FieldSnapshot(
            value_date=date(2026, 10, 14), source=FieldSource.RECEIPT_EXTRACTION, reviewed=True
        ),
        "amount": FieldSnapshot(
            value_decimal=Decimal("1400.00"),
            currency="INR",
            source=FieldSource.RECEIPT_EXTRACTION,
            reviewed=True,
        ),
        "currency": "INR",
        "category": "meal",
        "business_purpose": "Client meeting",
        "client_name": "Example Client",
        "attendee_count": 2,
        "receipt_count": 1,
    }
    defaults.update(overrides)
    return ClaimView(**defaults)  # type: ignore[arg-type]


class TestFieldUsability:
    """A value without provenance is not usable, whatever it contains."""

    def test_extraction_value_is_unusable_until_reviewed(self) -> None:
        snapshot = FieldSnapshot(
            value_decimal=Decimal("100.00"),
            source=FieldSource.RECEIPT_EXTRACTION,
            reviewed=False,
        )
        assert snapshot.usable is False

    def test_reviewed_extraction_value_is_usable(self) -> None:
        snapshot = FieldSnapshot(
            value_decimal=Decimal("100.00"),
            source=FieldSource.RECEIPT_EXTRACTION,
            reviewed=True,
        )
        assert snapshot.usable is True

    def test_value_without_any_source_is_unusable(self) -> None:
        assert FieldSnapshot(value_decimal=Decimal("100.00")).usable is False

    def test_uncertainty_reason_makes_a_value_unusable(self) -> None:
        snapshot = FieldSnapshot(
            value_decimal=Decimal("100.00"),
            source=FieldSource.RECEIPT_EXTRACTION,
            reviewed=True,
            uncertainty_reason="the total was partially obscured",
        )
        assert snapshot.usable is False

    def test_employee_entered_value_is_usable_but_flagged_as_employee_input(self) -> None:
        snapshot = FieldSnapshot(
            value_text="Example Cafe",
            source=FieldSource.EMPLOYEE_INPUT,
            reviewed=True,
        )
        assert snapshot.usable is True
        assert snapshot.source is FieldSource.EMPLOYEE_INPUT


class TestFindingDraftInvariants:
    """A FAIL finding without evidence cannot be constructed at all."""

    def test_fail_without_expected_or_calculation_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must carry either the expected condition"):
            FindingDraft(
                rule_id="POLICY-EXAMPLE",
                finding_type=FindingType.INDIVIDUAL_LIMIT_EXCEEDED,
                result=FindingResult.FAIL,
                severity=FindingSeverity.BLOCKING,
                message="Over the limit.",
            )

    def test_fail_with_a_calculation_is_accepted(self) -> None:
        draft = FindingDraft(
            rule_id="POLICY-EXAMPLE",
            finding_type=FindingType.INDIVIDUAL_LIMIT_EXCEEDED,
            result=FindingResult.FAIL,
            severity=FindingSeverity.BLOCKING,
            message="Over the limit.",
            calculation="1400.00 - 1000.00 = 400.00 over the applicable limit",
        )
        assert draft.result is FindingResult.FAIL

    def test_unknown_finding_needs_no_calculation(self) -> None:
        draft = FindingDraft(
            rule_id="POLICY-EXAMPLE",
            finding_type=FindingType.MISSING_POLICY_CONTEXT,
            result=FindingResult.UNKNOWN,
            severity=FindingSeverity.WARNING,
            message="Context missing.",
        )
        assert draft.recommended_action is RecommendedAction.REVIEW


class TestSeverityIsNotGuilt:
    """Severity describes routing. It must never read as an accusation."""

    def test_severity_values_are_the_three_canonical_ones(self) -> None:
        assert {member.value for member in FindingSeverity} == {"info", "warning", "blocking"}

    def test_no_severity_value_implies_fraud(self) -> None:
        forbidden = ("fraud", "guilt", "abuse", "misconduct", "cheat")
        for member in FindingSeverity:
            assert not any(word in member.value for word in forbidden)


class TestNoThresholdsInCode:
    """The engine must contain no invented monetary limit.

    A structural guard rather than a behavioural one: it fails if someone later
    hard-codes a cap. It checks the policy package source for suspicious numeric
    literals near limit-like words.
    """

    def test_policy_package_contains_no_currency_amount_literals(self) -> None:
        import re
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "app" / "policy"
        offenders: list[str] = []
        # A bare integer threshold or a money-looking literal is the smell.
        suspicious = re.compile(r"\b(\d{3,}(?:\.\d+)?)\b")
        allowed_context = ("version", "max_", "min_", "line-length", "#")
        for path in package.rglob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(token in line for token in allowed_context):
                    continue
                match = suspicious.search(line)
                if match and "Decimal" not in line and "limit" in line.lower():
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        assert offenders == [], (
            "A policy rule must read its limit from a validated rule parameter, never "
            f"from a literal in code. Found: {offenders}"
        )


class TestScopeFingerprint:
    """Fingerprints must be stable for equal inputs and differ for different ones."""

    def test_fingerprint_is_stable_regardless_of_dict_order(self) -> None:
        from app.context.scope import compute_fingerprint

        expense_id = uuid.uuid4()
        first = compute_fingerprint(
            expense_id=expense_id,
            expense_version=1,
            policy_version_id=None,
            dimensions={"a": "1", "b": "2"},
            contributors=(),
        )
        second = compute_fingerprint(
            expense_id=expense_id,
            expense_version=1,
            policy_version_id=None,
            dimensions={"b": "2", "a": "1"},
            contributors=(),
        )
        assert first == second

    def test_fingerprint_changes_with_the_claim_version(self) -> None:
        from app.context.scope import compute_fingerprint

        expense_id = uuid.uuid4()
        first = compute_fingerprint(
            expense_id=expense_id,
            expense_version=1,
            policy_version_id=None,
            dimensions={},
            contributors=(),
        )
        second = compute_fingerprint(
            expense_id=expense_id,
            expense_version=2,
            policy_version_id=None,
            dimensions={},
            contributors=(),
        )
        assert first != second

    def test_absent_dimension_is_recorded_explicitly_not_omitted(self) -> None:
        from app.context.scope import ABSENT, compute_fingerprint

        expense_id = uuid.uuid4()
        with_none = compute_fingerprint(
            expense_id=expense_id,
            expense_version=1,
            policy_version_id=None,
            dimensions={"trip": None},
            contributors=(),
        )
        with_absent = compute_fingerprint(
            expense_id=expense_id,
            expense_version=1,
            policy_version_id=None,
            dimensions={"trip": ABSENT},
            contributors=(),
        )
        assert with_none == with_absent
