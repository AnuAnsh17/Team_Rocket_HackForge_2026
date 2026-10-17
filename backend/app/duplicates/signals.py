"""Duplicate candidate signal generation.

What this module produces: **candidates**. What it must never produce: a confirmed
duplicate, an automatic rejection, or a fraud claim.

Independent signals, kept separate so a reviewer can see why a pair was surfaced:

1. ``exact_hash`` - byte-identical file content. Deterministic and reliable.
2. ``perceptual_similarity`` - NOT IMPLEMENTED. It requires an image pipeline
   (decode, orientation normalisation, rescale, hash) plus a threshold tuned
   against real positive and negative pairs. Reporting ``matched=False`` with an
   explanatory ``detail`` is the honest representation; inventing a score here
   would be the most damaging possible shortcut, because a reviewer would trust it.
3. ``normalized_field_match`` - merchant, date, amount and currency agreement.
   Implemented, and explicitly documented as *not sufficient* on its own: two
   different meals can share a total and a date.
4. ``channel_context`` - cross-channel metadata. A secondary signal only.

``ranking_score`` is a queue-ordering convenience. It is not a probability and is
not calibrated against any labelled set, which is why the DTO says so.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Bumping this invalidates stored candidates. It must change whenever a signal's
# behaviour or weighting changes, so a reviewer can tell which version produced a
# candidate.
ALGORITHM_VERSION = "duplicate-signals/0.1.0"

# Field-agreement tolerance: amounts must be exactly equal after decimal
# normalisation. A date tolerance window is a POLICY decision (how many days apart
# may two receipts of the same amount be?) and is recorded as an open question in
# docs/policy-assumptions.md rather than guessed here.
DATE_TOLERANCE_DAYS = 0

# Signal weights, used only to order a review queue.
_SIGNAL_WEIGHTS: dict[str, float] = {"exact_hash": 1.0, "normalized_field_match": 0.4}


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    """One independent signal's verdict for a candidate pair."""

    signal_type: str
    matched: bool
    score: float | None = None
    detail: str | None = None
    implemented: bool = True


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    """The assembled signals for one expense pair."""

    expense_a_id: object
    expense_b_id: object
    algorithm_version: str = ALGORITHM_VERSION
    signals: tuple[SignalOutcome, ...] = ()
    ranking_score: float | None = None
    cross_channel: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def any_strong_signal(self) -> bool:
        """Whether a signal warrants putting this pair in front of a reviewer.

        Only the implemented signals that are strong on their own can make this
        true. Field agreement deliberately cannot.
        """
        return any(signal.matched and signal.signal_type == "exact_hash" for signal in self.signals)


def canonical_pair(a: object, b: object) -> tuple[object, object]:
    """Order a pair deterministically.

    Stored pairs are ordered so that (A,B) and (B,A) cannot both exist; a unique
    index on the ordered pair enforces it in the database.
    """
    return (a, b) if str(a) <= str(b) else (b, a)


def exact_hash_signal(sha256_a: str | None, sha256_b: str | None) -> SignalOutcome:
    """Byte-identical file content."""
    if not sha256_a or not sha256_b:
        return SignalOutcome(
            signal_type="exact_hash",
            matched=False,
            detail="at least one receipt has no content hash recorded",
        )
    matched = sha256_a == sha256_b
    return SignalOutcome(
        signal_type="exact_hash",
        matched=matched,
        score=1.0 if matched else 0.0,
        detail=(
            "the two receipt files are byte-identical"
            if matched
            else "the two receipt files have different content hashes"
        ),
    )


def perceptual_similarity_signal() -> SignalOutcome:
    """Image similarity after orientation normalisation. NOT IMPLEMENTED."""
    return SignalOutcome(
        signal_type="perceptual_similarity",
        matched=False,
        score=None,
        implemented=False,
        detail=(
            "not implemented: requires image decode, orientation normalisation and a threshold "
            "tuned against labelled positive and negative pairs. No score is reported because a "
            "fabricated one would be acted on."
        ),
    )


def normalized_field_match_signal(
    *,
    merchant_a: str | None,
    merchant_b: str | None,
    date_a: date | None,
    date_b: date | None,
    amount_a: Decimal | None,
    amount_b: Decimal | None,
    currency_a: str | None,
    currency_b: str | None,
) -> SignalOutcome:
    """Agreement across normalized claim fields.

    Explicitly a weak signal on its own. Reported with its components so a reviewer
    can judge it, and it never makes ``any_strong_signal`` true.
    """
    components: dict[str, bool] = {}
    available = 0

    if merchant_a and merchant_b:
        components["merchant"] = merchant_a.strip().casefold() == merchant_b.strip().casefold()
        available += 1
    if date_a and date_b:
        components["date"] = abs((date_a - date_b).days) <= DATE_TOLERANCE_DAYS
        available += 1
    if amount_a is not None and amount_b is not None:
        components["amount"] = amount_a == amount_b
        available += 1
    if currency_a and currency_b:
        components["currency"] = currency_a.upper() == currency_b.upper()
        available += 1

    if available == 0:
        return SignalOutcome(
            signal_type="normalized_field_match",
            matched=False,
            score=None,
            detail="no comparable fields were available on both claims",
        )

    agreements = sum(1 for value in components.values() if value)
    return SignalOutcome(
        signal_type="normalized_field_match",
        matched=False,
        score=round(agreements / available, 4),
        detail=(
            "field agreement is a ranking signal only and never confirms a duplicate: "
            + ", ".join(
                f"{name}={'match' if value else 'differ'}"
                for name, value in sorted(components.items())
            )
        ),
    )


def channel_context_signal(channel_a: str | None, channel_b: str | None) -> SignalOutcome:
    """Cross-channel metadata. Secondary signal only."""
    if not channel_a or not channel_b:
        return SignalOutcome(
            signal_type="channel_context",
            matched=False,
            detail="channel metadata unavailable for one or both claims",
        )
    different = channel_a != channel_b
    return SignalOutcome(
        signal_type="channel_context",
        matched=False,
        score=None,
        detail=(
            f"the two submissions arrived through different channels ({channel_a} vs "
            f"{channel_b}); this is corroborating context, not evidence of duplication"
            if different
            else f"both submissions arrived through the {channel_a} channel"
        ),
    )


def assemble_candidate(
    *,
    expense_a_id: object,
    expense_b_id: object,
    signals: tuple[SignalOutcome, ...],
    cross_channel: bool = False,
) -> CandidateAssessment:
    """Combine signals into one candidate assessment.

    The ranking score is a weighted sum over the signals that are actually
    implemented. It orders a review queue and nothing else.
    """
    implemented = [signal for signal in signals if signal.implemented and signal.score is not None]
    weight_total = sum(_SIGNAL_WEIGHTS.get(signal.signal_type, 0.0) for signal in implemented)
    if weight_total > 0:
        ranking = (
            sum(
                _SIGNAL_WEIGHTS.get(signal.signal_type, 0.0) * float(signal.score or 0.0)
                for signal in implemented
            )
            / weight_total
        )
        ranking_score: float | None = round(ranking, 4)
    else:
        ranking_score = None

    notes = [
        "A candidate is a review prompt, not a finding of duplication and not an accusation. "
        "Confirmation requires a human decision with a reason.",
    ]
    unimplemented = [signal for signal in signals if not signal.implemented]
    if unimplemented:
        notes.append(
            "Unavailable signals in this build: "
            + ", ".join(sorted(signal.signal_type for signal in unimplemented))
        )

    return CandidateAssessment(
        expense_a_id=expense_a_id,
        expense_b_id=expense_b_id,
        signals=tuple(signals),
        ranking_score=ranking_score,
        cross_channel=cross_channel,
        notes=tuple(notes),
    )


def signal_fingerprint(assessment: CandidateAssessment) -> str:
    """Stable hash of a candidate's signals, for dedupe and change detection."""
    payload = "|".join(
        f"{signal.signal_type}:{signal.matched}:{signal.score}:{signal.implemented}"
        for signal in sorted(assessment.signals, key=lambda item: item.signal_type)
    )
    return hashlib.sha256(f"{assessment.algorithm_version}::{payload}".encode()).hexdigest()
