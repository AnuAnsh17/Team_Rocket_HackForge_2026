"""The deterministic evaluation pipeline.

Implements the nine ordered steps from PROOFLINE_BUILD_PLAN.md section 6.4. The
order matters and is not cosmetic: provenance is established before arithmetic,
and the policy scope is resolved before any rule runs, so a rule never evaluates
against context it has not been authorised to use.

Steps 8 and 9 (persistence and audit) live in
``app/services/policy_service.py`` so that all database writes for one evaluation
share a single transaction with their audit event. This module is pure: it reads,
decides, and returns drafts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import InvalidOperation

from sqlalchemy.orm import Session

from app.core.enums import (
    FindingResult,
    FindingSeverity,
    FindingType,
    RecommendedAction,
)
from app.core.logging import get_logger
from app.models.expense import Expense
from app.policy.base import (
    ClaimView,
    EvaluationScope,
    FindingDraft,
    RuleContext,
)
from app.policy.registry import RegistryLoad, load_registry
from app.policy.resolution import ResolvedPolicy, resolve_effective_policy
from app.schemas.common import SourceReference

logger = get_logger(__name__)

EVALUATION_STEPS: tuple[str, ...] = (
    "validate_claim_invariants",
    "establish_field_provenance",
    "run_arithmetic_and_date_sanity_checks",
    "resolve_policy_scope",
    "run_individual_expense_rules",
    "apply_currency_normalisation_if_required",
    "run_aggregate_rules_and_generate_duplicate_candidates",
    "persist_findings_and_transition_status",
    "record_audit_events_and_enqueue_reevaluation",
)

# Structural checks that do not depend on a policy clause. They are deliberately
# few: anything that encodes a reimbursement rule belongs in the registry.
STRUCTURAL_RULES = (
    "claim_has_receipt",
    "claim_has_reliable_amount",
    "claim_has_reliable_date",
    "required_business_context_present",
)


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    """Everything one evaluation produced, without having written anything."""

    expense_id: uuid.UUID
    expense_version: int
    scope_fingerprint: str
    steps_performed: tuple[str, ...]
    resolved_policy: ResolvedPolicy
    registry: RegistryLoad
    findings: tuple[FindingDraft, ...]
    unresolved_reasons: tuple[str, ...] = field(default_factory=tuple)
    duplicate_signal_pairs: tuple[tuple[uuid.UUID, uuid.UUID], ...] = ()

    @property
    def has_blocking(self) -> bool:
        return any(
            item.result is not FindingResult.PASS and item.severity is FindingSeverity.BLOCKING
            for item in self.findings
        )

    def counts(self) -> dict[str, int]:
        return {
            "pass": sum(1 for f in self.findings if f.result is FindingResult.PASS),
            "fail": sum(1 for f in self.findings if f.result is FindingResult.FAIL),
            "unknown": sum(1 for f in self.findings if f.result is FindingResult.UNKNOWN),
        }


def _structural_findings(claim: ClaimView) -> list[FindingDraft]:
    """Checks that are true regardless of the policy document.

    Each returns PASS when there is enough information, and UNKNOWN when there is
    not. Note the absence of any automatic FAIL: a missing receipt is an
    incomplete claim, not a breach, and this scaffold does not accuse anyone.
    """
    drafts: list[FindingDraft] = []

    drafts.append(
        FindingDraft(
            rule_id=STRUCTURAL_RULES[0],
            finding_type=FindingType.REQUIRED_FIELD_MISSING,
            result=FindingResult.PASS if claim.receipt_count > 0 else FindingResult.UNKNOWN,
            severity=FindingSeverity.WARNING
            if claim.receipt_count > 0
            else FindingSeverity.BLOCKING,
            message=(
                f"{claim.receipt_count} receipt(s) attached."
                if claim.receipt_count > 0
                else "No receipt is attached to this claim yet."
            ),
            employee_message=(
                None
                if claim.receipt_count > 0
                else "Add a photo of the receipt so finance can verify this claim."
            ),
            recommended_action=(
                RecommendedAction.NONE
                if claim.receipt_count > 0
                else RecommendedAction.REQUEST_CORRECTION
            ),
            evidence={"receipt_count": claim.receipt_count},
        )
    )

    amount_usable = claim.amount.usable and claim.amount.value_decimal is not None
    drafts.append(
        FindingDraft(
            rule_id=STRUCTURAL_RULES[1],
            finding_type=FindingType.FIELD_UNCERTAIN,
            result=FindingResult.PASS if amount_usable else FindingResult.UNKNOWN,
            severity=FindingSeverity.INFO if amount_usable else FindingSeverity.BLOCKING,
            message=(
                "The claim amount is present with usable provenance."
                if amount_usable
                else "The claim amount is missing, unreadable or has no reviewed provenance."
            ),
            employee_message=(
                None if amount_usable else "Confirm the total amount and currency on this claim."
            ),
            recommended_action=(
                RecommendedAction.NONE if amount_usable else RecommendedAction.REQUEST_CORRECTION
            ),
            evidence={
                "amount_present": claim.amount.value_decimal is not None,
                "source": claim.amount.source.value if claim.amount.source else None,
                "reviewed": claim.amount.reviewed,
                "uncertainty_reason": claim.amount.uncertainty_reason,
            },
        )
    )

    date_usable = claim.expense_date.usable and claim.expense_date.value_date is not None
    drafts.append(
        FindingDraft(
            rule_id=STRUCTURAL_RULES[2],
            finding_type=FindingType.FIELD_UNCERTAIN,
            result=FindingResult.PASS if date_usable else FindingResult.UNKNOWN,
            severity=FindingSeverity.INFO if date_usable else FindingSeverity.BLOCKING,
            message=(
                "The transaction date is present with usable provenance."
                if date_usable
                else "The transaction date is missing, unreadable or has no reviewed provenance."
            ),
            employee_message=(None if date_usable else "Confirm the date printed on the receipt."),
            recommended_action=(
                RecommendedAction.NONE if date_usable else RecommendedAction.REQUEST_CORRECTION
            ),
            evidence={
                "date_present": claim.expense_date.value_date is not None,
                "source": claim.expense_date.source.value if claim.expense_date.source else None,
                "reviewed": claim.expense_date.reviewed,
            },
        )
    )

    # Business context is a POLICY question ("which categories require a client
    # name?"). Without the policy document this check can only report that it
    # cannot be answered - never that context is missing for a specific category.
    drafts.append(
        FindingDraft(
            rule_id=STRUCTURAL_RULES[3],
            finding_type=FindingType.MISSING_POLICY_CONTEXT,
            result=FindingResult.UNKNOWN,
            severity=FindingSeverity.INFO,
            message=(
                "Whether this category requires a client name, attendee count or business "
                "purpose is not yet known: no approved policy document has been supplied, so "
                "no context requirement has been verified."
            ),
            employee_message=(
                "We cannot yet confirm which additional details this expense type needs."
            ),
            recommended_action=RecommendedAction.NONE,
            evidence={
                "category": claim.category,
                "client_name_present": claim.client_name is not None,
                "attendee_count": claim.attendee_count,
                "business_purpose_present": claim.business_purpose is not None,
            },
        )
    )
    return drafts


def _no_policy_finding(resolved: ResolvedPolicy, scope: EvaluationScope) -> FindingDraft:
    """The UNKNOWN finding raised when no verified rule could run.

    This finding is the honest answer for the entire current state of the product:
    zero active rules means every claim is UNKNOWN, never PASS. It exists so that
    the absence of policy coverage is visible in the UI instead of looking like a
    clean claim.
    """
    reasons = list(resolved.unresolved_reasons) or list(scope.unresolved_reasons)
    return FindingDraft(
        rule_id="policy_coverage",
        finding_type=FindingType.MISSING_POLICY_CONTEXT,
        result=FindingResult.UNKNOWN,
        severity=FindingSeverity.BLOCKING,
        message=(
            "No approved policy rule was evaluated for this claim. "
            + (" ".join(reasons) if reasons else "No approved policy version is assigned.")
            + " This is reported as UNKNOWN, never as PASS, so it cannot be mistaken for a "
            "compliant claim."
        ),
        employee_message=(
            "This claim has been received. Our policy checks are not active yet, so a finance "
            "reviewer will review it manually."
        ),
        recommended_action=RecommendedAction.REVIEW,
        evidence={
            "resolved": resolved.resolved,
            "policy_version_id": str(resolved.policy_version_id)
            if resolved.policy_version_id
            else None,
            "unresolved_reasons": reasons,
            "scope_dimensions": scope.dimensions,
            "evaluation_steps": list(EVALUATION_STEPS),
        },
    )


def evaluate_expense(
    session: Session,
    expense: Expense,
    *,
    claim: ClaimView,
    scope: EvaluationScope,
    policy_period: tuple[date | None, date | None] = (None, None),
    include_structural_checks: bool = True,
) -> EvaluationOutcome:
    """Run the evaluation pipeline and return drafts. Writes nothing."""
    steps: list[str] = [EVALUATION_STEPS[0], EVALUATION_STEPS[1]]

    # Step 3 - deterministic sanity checks. An arithmetic check requires the
    # receipt's own subtotal/tax/total breakdown, which only exists once a
    # provider has extracted it; with no provider the check cannot run and is not
    # reported as a pass.
    arithmetic_unknown_reason: str | None = None
    if claim.amount.value_decimal is None:
        arithmetic_unknown_reason = "no amount is available to check"

    steps.append(EVALUATION_STEPS[2])

    # Steps 4 and 5 - resolve the policy scope, then the governing version.
    resolved = resolve_effective_policy(
        session,
        organization_id=expense.organization_id,
        scope=scope,
        on_date=claim.expense_date.value_date,
    )
    steps.append(EVALUATION_STEPS[3])

    findings: list[FindingDraft] = []
    if include_structural_checks:
        findings.extend(_structural_findings(claim))

    registry = RegistryLoad()
    if resolved.resolved and resolved.policy_version_id is not None:
        registry = load_registry(session, policy_version_id=resolved.policy_version_id)
        for registered in registry.rules:
            context = RuleContext(
                claim=claim,
                scope=scope,
                policy_version_id=resolved.policy_version_id,
                policy_version_label=resolved.version_label or "",
                rule_parameters=registered.parameters,
                source_clause=registered.source_clause,
                source_excerpt=registered.source_excerpt,
            )
            try:
                draft = registered.implementation.evaluate(context)
            except (InvalidOperation, ArithmeticError, ValueError) as exc:
                # A rule that cannot complete must not crash evaluation and must
                # not be treated as a pass.
                logger.warning(
                    "rule evaluation raised; recording UNKNOWN",
                    extra={"rule_id": registered.rule_id, "error": type(exc).__name__},
                )
                draft = FindingDraft(
                    rule_id=registered.rule_id,
                    finding_type=FindingType.MISSING_POLICY_CONTEXT,
                    result=FindingResult.UNKNOWN,
                    severity=FindingSeverity.WARNING,
                    message=(
                        f"Rule {registered.rule_id} could not complete against the available "
                        "evidence. The claim is reported as UNKNOWN for this rule."
                    ),
                    recommended_action=RecommendedAction.REVIEW,
                    evidence={"error_type": type(exc).__name__},
                )
            if draft.source_reference is None and registered.source_clause:
                draft = FindingDraft(
                    **{
                        **draft.__dict__,
                        "source_reference": SourceReference(
                            clause=registered.source_clause,
                            text_excerpt=registered.source_excerpt,
                        ),
                    }
                )
            findings.append(draft)

    steps.append(EVALUATION_STEPS[4])

    # Step 6 - currency normalisation happens only when the approved policy
    # requires it. No rate source has been approved, so this step is skipped and
    # that fact is recorded rather than a rate being invented.
    currency_note: str | None = None
    if resolved.resolved:
        currency_note = (
            "currency normalisation was not attempted: no approved rate source or rate date "
            "has been supplied"
        )
    steps.append(EVALUATION_STEPS[5])

    if registry.is_empty:
        findings.append(_no_policy_finding(resolved, scope))
        if arithmetic_unknown_reason:
            findings.append(
                FindingDraft(
                    rule_id="arithmetic_consistency",
                    finding_type=FindingType.ARITHMETIC_MISMATCH,
                    result=FindingResult.UNKNOWN,
                    severity=FindingSeverity.INFO,
                    message=(
                        "Arithmetic consistency between line items, tax, discount and total could "
                        f"not be checked: {arithmetic_unknown_reason}."
                    ),
                    recommended_action=RecommendedAction.NONE,
                )
            )

    # Step 7 is aggregate rules (none active) plus duplicate candidate generation,
    # delegated to app/duplicates. Candidate generation is a write, so it is
    # performed by the service inside the same transaction.
    steps.append(EVALUATION_STEPS[6])

    unresolved = tuple(
        dict.fromkeys(
            (
                *resolved.unresolved_reasons,
                *scope.unresolved_reasons,
                *((currency_note,) if currency_note else ()),
                *registry.warnings,
            )
        )
    )

    return EvaluationOutcome(
        expense_id=expense.id,
        expense_version=expense.version,
        scope_fingerprint=scope.fingerprint,
        steps_performed=tuple(steps),
        resolved_policy=resolved,
        registry=registry,
        findings=tuple(findings),
        unresolved_reasons=unresolved,
    )
