"""Read-only policy pre-flight.

Answers "what would the policy say about this claim?" without touching the database. The
whole module is a read: it resolves context, runs the deterministic evaluator, and maps
the result. It creates no claim, writes no finding, records no audit event and transitions
no status, which is what makes it safe to call from a form as the employee types.

Two inputs are supported by the existing ``PolicyCheckRequest`` contract:

* an existing ``expense_id``, where the actor must already be authorised to read the claim;
* inline preview fields, evaluated against the actor's own authoritative context.

Neither path lets the caller choose the organization, membership, roles or policy version.
An inline preview takes its organization and membership from the authenticated actor, and
the policy version is always whatever the resolver finds for that context.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.context.scope import build_claim_view, resolve_scope
from app.core.enums import ExpenseChannel, ExpenseStatus, FieldSource
from app.core.errors import Forbidden, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import Permission
from app.core.security import Actor
from app.models.expense import Expense, Trip
from app.models.policy import PolicyDocument, PolicyRule, PolicyVersion
from app.policy.base import ClaimView, EvaluationScope, FieldSnapshot, FindingDraft
from app.policy.evaluator import EvaluationOutcome, evaluate_expense
from app.schemas.policy import PolicyCheckRequest, PolicyCheckResponse, PolicyVersionSummary
from app.services.scope_service import require_expense_read

logger = get_logger(__name__)

# Says plainly what the result is. Present on every response so a client cannot present a
# demo-policy answer as a company decision.
ADVISORY_NOTE = (
    "Advisory only. This pre-flight is a demonstration of the policy engine and does not "
    "approve, reject or reimburse anything. A human reviewer decides."
)


def _finding_payload(draft: FindingDraft) -> dict[str, object]:
    """The pre-flight finding shape: the same fields a persisted finding carries."""
    return {
        "rule_id": draft.rule_id,
        "finding_type": draft.finding_type.value,
        "result": draft.result.value,
        "severity": draft.severity.value,
        "message": draft.message,
        "employee_message": draft.employee_message,
        "recommended_action": draft.recommended_action.value,
        "calculation": draft.calculation,
        "expected": draft.expected,
        "observed": draft.observed,
        "evidence": draft.evidence,
        "source_reference": (
            draft.source_reference.model_dump(mode="json") if draft.source_reference else None
        ),
    }


def _version_summary(session: Session, version_id: uuid.UUID) -> PolicyVersionSummary | None:
    version = session.get(PolicyVersion, version_id)
    if version is None:
        return None
    document = session.get(PolicyDocument, version.policy_document_id)
    total = session.execute(
        select(func.count())
        .select_from(PolicyRule)
        .where(PolicyRule.policy_version_id == version.id)
    ).scalar_one()
    active = session.execute(
        select(func.count())
        .select_from(PolicyRule)
        .where(
            PolicyRule.policy_version_id == version.id,
            PolicyRule.is_active.is_(True),
        )
    ).scalar_one()
    return PolicyVersionSummary(
        id=version.id,
        version_label=version.version_label,
        document_title=document.title if document else "",
        document_sha256=document.source_file_sha256 if document else None,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        review_state=version.review_state,
        approved_at=version.approved_at,
        rule_count=int(total),
        active_rule_count=int(active),
    )


def _ephemeral_preview(
    session: Session, actor: Actor, request: PolicyCheckRequest
) -> tuple[Expense, ClaimView, EvaluationScope]:
    """Build an unsaved claim from the request, scoped to the actor's own context.

    The returned ``Expense`` is a transient object: it is never added to the session, so no
    row is written and no primary key is allocated. It exists only so the same
    ``resolve_scope`` path used for a stored claim can be reused, which is what keeps the
    preview's context semantics identical to a real evaluation.
    """
    # Asking about a claim you are entitled to create. This is deliberately the create
    # permission rather than a read permission: no stored claim exists yet.
    actor.require(Permission.EXPENSE_CREATE_OWN)
    if actor.active_organization_id is None or actor.active_membership_id is None:
        raise Forbidden("An active organization membership is required for a policy preview.")

    # A trip may only narrow the preview to a trip the actor actually owns. Without this,
    # a client could pass another employee's trip id and pull in trip-scoped policy context
    # it has no claim to.
    if request.trip_id is not None:
        trip = session.get(Trip, request.trip_id)
        if (
            trip is None
            or str(trip.organization_id) != str(actor.active_organization_id)
            or str(trip.membership_id) != str(actor.active_membership_id)
        ):
            raise Forbidden("The trip is not available to this actor.")

    amount: Decimal | None = None
    if request.amount is not None:
        try:
            amount = Decimal(str(request.amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationFailed("The amount is not a usable decimal value.") from exc
        if not amount.is_finite():
            raise ValidationFailed("The amount must be a finite value.")

    expense = Expense(
        id=uuid.uuid4(),  # never persisted; a placeholder so scope and claim views can form
        organization_id=uuid.UUID(str(actor.active_organization_id)),
        membership_id=uuid.UUID(str(actor.active_membership_id)),
        trip_id=request.trip_id,
        version=1,
        status=ExpenseStatus.DRAFT.value,
        channel=ExpenseChannel.WEB.value,
        merchant=None,
        expense_date=request.expense_date,
        amount=amount,
        currency=request.currency,
        category=request.category,
        business_purpose=request.business_purpose,
        client_name=request.client_name,
        attendee_count=request.attendee_count,
    )

    # Values a preview is given are employee-declared, and are labelled as such. They are
    # never presented as receipt evidence, so a preview cannot launder a guess into proof.
    claim = ClaimView(
        expense_id=expense.id,
        version=1,
        status=ExpenseStatus.DRAFT,
        channel=ExpenseChannel.WEB,
        merchant=FieldSnapshot(),
        expense_date=(
            FieldSnapshot(value_date=request.expense_date, source=FieldSource.EMPLOYEE_INPUT)
            if request.expense_date is not None
            else FieldSnapshot()
        ),
        amount=(
            FieldSnapshot(
                value_decimal=amount, currency=request.currency, source=FieldSource.EMPLOYEE_INPUT
            )
            if amount is not None
            else FieldSnapshot()
        ),
        currency=request.currency,
        category=request.category,
        business_purpose=request.business_purpose,
        client_name=request.client_name,
        attendee_count=request.attendee_count,
        line_item_count=0,
        receipt_count=0,
        has_failed_extraction=False,
    )
    scope = resolve_scope(session, expense)
    return expense, claim, scope


def check_policy(
    session: Session, actor: Actor, request: PolicyCheckRequest
) -> PolicyCheckResponse:
    """Evaluate a claim or preview against the governing policy. Writes nothing."""
    if request.expense_id is not None:
        # Reuses the same authorization path the expense endpoints use, so a pre-flight
        # cannot be used to probe for another employee's claim: an inaccessible id is
        # rejected exactly as a read would be, before any policy detail is assembled.
        expense = require_expense_read(session, actor, request.expense_id)
        claim = build_claim_view(session, expense)
        scope = resolve_scope(session, expense)
    else:
        expense, claim, scope = _ephemeral_preview(session, actor, request)

    outcome: EvaluationOutcome = evaluate_expense(session, expense, claim=claim, scope=scope)

    version_summary = (
        _version_summary(session, outcome.resolved_policy.policy_version_id)
        if outcome.resolved_policy.resolved and outcome.resolved_policy.policy_version_id
        else None
    )

    findings = [_finding_payload(draft) for draft in outcome.findings]

    unresolved = list(outcome.unresolved_reasons)
    if not outcome.resolved_policy.resolved and not unresolved:
        unresolved.append(
            "no approved policy version could be resolved for this context, so no rule was "
            "evaluated"
        )

    logger.info(
        "policy pre-flight evaluated",
        extra={
            "expense_id": str(expense.id),
            "resolved": outcome.resolved_policy.resolved,
            "finding_count": len(findings),
        },
    )

    return PolicyCheckResponse(
        advisory=True,
        resolved=outcome.resolved_policy.resolved,
        unresolved_reasons=unresolved,
        policy_version=version_summary,
        findings=findings,
        advisory_note=ADVISORY_NOTE,
    )
