"""Duplicate signal behaviour.

The assertions here exist to pin down what the system refuses to claim: no
perceptual score is invented, field agreement never confirms a duplicate, and a
pair is stored canonically.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.duplicates.signals import (
    ALGORITHM_VERSION,
    assemble_candidate,
    canonical_pair,
    channel_context_signal,
    exact_hash_signal,
    normalized_field_match_signal,
    perceptual_similarity_signal,
    signal_fingerprint,
)

pytestmark = pytest.mark.unit


class TestExactHashSignal:
    def test_identical_hashes_match(self) -> None:
        outcome = exact_hash_signal("a" * 64, "a" * 64)
        assert outcome.matched is True
        assert outcome.score == 1.0

    def test_different_hashes_do_not_match(self) -> None:
        assert exact_hash_signal("a" * 64, "b" * 64).matched is False

    def test_missing_hash_is_reported_not_assumed(self) -> None:
        outcome = exact_hash_signal(None, "b" * 64)
        assert outcome.matched is False
        assert outcome.detail and "no content hash" in outcome.detail


class TestPerceptualSignalIsHonestlyAbsent:
    def test_perceptual_similarity_reports_not_implemented(self) -> None:
        outcome = perceptual_similarity_signal()
        assert outcome.implemented is False
        assert outcome.score is None, "no fabricated similarity score may be produced"
        assert outcome.matched is False

    def test_unimplemented_signal_cannot_make_a_pair_strong(self) -> None:
        assessment = assemble_candidate(
            expense_a_id=uuid.uuid4(),
            expense_b_id=uuid.uuid4(),
            signals=(perceptual_similarity_signal(),),
        )
        assert assessment.any_strong_signal is False
        assert assessment.ranking_score is None


class TestFieldMatchIsWeakByDesign:
    def test_identical_fields_still_do_not_match_the_signal(self) -> None:
        outcome = normalized_field_match_signal(
            merchant_a="Cafe One",
            merchant_b="cafe one",
            date_a=date(2026, 10, 14),
            date_b=date(2026, 10, 14),
            amount_a=Decimal("1400.00"),
            amount_b=Decimal("1400.00"),
            currency_a="INR",
            currency_b="INR",
        )
        assert outcome.matched is False, "field agreement must never confirm a duplicate"
        assert outcome.score == 1.0

    def test_two_different_meals_with_the_same_total_are_not_called_duplicates(self) -> None:
        """The documented hard-negative case."""
        outcome = normalized_field_match_signal(
            merchant_a="Cafe One",
            merchant_b="Diner Two",
            date_a=date(2026, 10, 14),
            date_b=date(2026, 10, 14),
            amount_a=Decimal("1400.00"),
            amount_b=Decimal("1400.00"),
            currency_a="INR",
            currency_b="INR",
        )
        assessment = assemble_candidate(
            expense_a_id=uuid.uuid4(),
            expense_b_id=uuid.uuid4(),
            signals=(outcome,),
        )
        assert assessment.any_strong_signal is False

    def test_no_comparable_fields_is_reported(self) -> None:
        outcome = normalized_field_match_signal(
            merchant_a=None,
            merchant_b=None,
            date_a=None,
            date_b=None,
            amount_a=None,
            amount_b=None,
            currency_a=None,
            currency_b=None,
        )
        assert outcome.score is None
        assert outcome.detail and "no comparable fields" in outcome.detail


class TestChannelContext:
    def test_cross_channel_is_corroborating_not_conclusive(self) -> None:
        outcome = channel_context_signal("android", "email_simulated")
        assert outcome.matched is False
        assert outcome.detail and "not evidence of duplication" in outcome.detail


class TestPairCanonicalisation:
    def test_pair_order_is_stable(self) -> None:
        high, low = uuid.UUID(int=2), uuid.UUID(int=1)
        assert canonical_pair(high, low) == canonical_pair(low, high)

    def test_fingerprint_is_stable_and_versioned(self) -> None:
        pair = (uuid.uuid4(), uuid.uuid4())
        first = assemble_candidate(
            expense_a_id=pair[0],
            expense_b_id=pair[1],
            signals=(exact_hash_signal("a" * 64, "a" * 64),),
        )
        second = assemble_candidate(
            expense_a_id=pair[0],
            expense_b_id=pair[1],
            signals=(exact_hash_signal("a" * 64, "a" * 64),),
        )
        assert signal_fingerprint(first) == signal_fingerprint(second)
        assert first.algorithm_version == ALGORITHM_VERSION


class TestCandidateNotes:
    def test_notes_state_that_a_candidate_is_not_an_accusation(self) -> None:
        assessment = assemble_candidate(
            expense_a_id=uuid.uuid4(),
            expense_b_id=uuid.uuid4(),
            signals=(perceptual_similarity_signal(),),
        )
        joined = " ".join(assessment.notes)
        assert "not an accusation" in joined
        assert "perceptual_similarity" in joined
