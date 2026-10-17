"""Duplicate candidate generation. Candidates only, never fraud findings."""

from app.duplicates.signals import (
    ALGORITHM_VERSION,
    CandidateAssessment,
    SignalOutcome,
    assemble_candidate,
    canonical_pair,
    channel_context_signal,
    exact_hash_signal,
    normalized_field_match_signal,
    perceptual_similarity_signal,
    signal_fingerprint,
)

__all__ = [
    "ALGORITHM_VERSION",
    "CandidateAssessment",
    "SignalOutcome",
    "assemble_candidate",
    "canonical_pair",
    "channel_context_signal",
    "exact_hash_signal",
    "normalized_field_match_signal",
    "perceptual_similarity_signal",
    "signal_fingerprint",
]
