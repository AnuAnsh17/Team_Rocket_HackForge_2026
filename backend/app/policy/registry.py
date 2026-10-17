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
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import PolicyReviewState
from app.core.logging import get_logger
from app.models.policy import PolicyRule as PolicyRuleRow
from app.policy.base import PolicyRule

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


def register_rule(implementation: PolicyRule) -> None:
    """Register one executable rule implementation."""
    if implementation.evaluator_type in _RULE_IMPLEMENTATIONS:
        raise ValueError(f"evaluator_type {implementation.evaluator_type!r} is already registered")
    _RULE_IMPLEMENTATIONS[implementation.evaluator_type] = implementation


def registered_evaluator_types() -> tuple[str, ...]:
    return tuple(sorted(_RULE_IMPLEMENTATIONS))


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
