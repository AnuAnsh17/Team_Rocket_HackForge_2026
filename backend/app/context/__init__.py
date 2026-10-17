"""Evaluation context: scope resolution, fingerprints and re-evaluation planning."""

from app.context.scope import (
    ABSENT,
    DEFAULT_AGGREGATE_INCLUDED_STATUSES,
    build_claim_view,
    compute_fingerprint,
    gather_related_expenses,
    resolve_scope,
)

__all__ = [
    "ABSENT",
    "DEFAULT_AGGREGATE_INCLUDED_STATUSES",
    "build_claim_view",
    "compute_fingerprint",
    "gather_related_expenses",
    "resolve_scope",
]
