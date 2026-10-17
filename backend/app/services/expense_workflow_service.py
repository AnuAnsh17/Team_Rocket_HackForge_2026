"""Shared claim write paths used by API routes and deterministic demo fixtures."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ExpenseFieldName, ExpenseStatus, FieldSource, ReviewAction
from app.core.errors import Conflict, Forbidden, NotFound, StaleVersion, ValidationFailed
from app.core.security import Actor
from app.models.expense import Expense, ExpenseFieldEvidence, Trip
from app.models.receipt import Receipt
from app.models.review import ReviewDecision
from app.schemas.expense import CreateExpenseRequest
from app.schemas.review import DecisionRequest
from app.services.audit_service import audit_for_actor
from app.services.scope_service import is_own_claim


def create_draft_claim(
    session: Session,
    actor: Actor,
    body: CreateExpenseRequest,
    *,
    expense_id: uuid.UUID | None = None,
) -> Expense:
    """Create an own-member draft and its first-version field evidence."""
    if actor.active_membership_id is None or actor.active_organization_id is None:
        raise Forbidden("An active organization membership is required to create a draft.")
    if body.employee_membership_id not in (None, uuid.UUID(actor.active_membership_id)):
        raise Forbidden("Draft creation is limited to the caller's active membership.")
    if body.channel.value not in {"web", "android"}:
        raise ValidationFailed("Employees may create drafts only from web or android channels.")
    if (body.amount is None) != (body.currency is None):
        raise ValidationFailed("Amount and currency must be supplied together.")
    if body.trip_id is not None:
        trip = session.get(Trip, body.trip_id)
        if (
            trip is None
            or str(trip.organization_id) != actor.active_organization_id
            or str(trip.membership_id) != actor.active_membership_id
        ):
            raise Forbidden("The trip is not available to this employee.")

    expense = Expense(
        id=expense_id or uuid.uuid4(),
        organization_id=uuid.UUID(actor.active_organization_id),
        membership_id=uuid.UUID(actor.active_membership_id),
        trip_id=body.trip_id,
        channel=body.channel.value,
        status=ExpenseStatus.DRAFT.value,
        version=1,
        merchant=body.merchant,
        expense_date=body.expense_date,
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        business_purpose=body.business_purpose,
        client_name=body.client_name,
        attendee_count=body.attendee_count,
        created_by_user_id=uuid.UUID(actor.user_id),
    )
    session.add(expense)
    session.flush()
    values: tuple[tuple[str, object | None], ...] = (
        (ExpenseFieldName.MERCHANT.value, body.merchant),
        (ExpenseFieldName.EXPENSE_DATE.value, body.expense_date),
        (ExpenseFieldName.AMOUNT.value, body.amount),
        (ExpenseFieldName.CURRENCY.value, body.currency),
        (ExpenseFieldName.CATEGORY.value, body.category),
        (ExpenseFieldName.BUSINESS_PURPOSE.value, body.business_purpose),
        (ExpenseFieldName.CLIENT_NAME.value, body.client_name),
        (ExpenseFieldName.ATTENDEE_COUNT.value, body.attendee_count),
        (ExpenseFieldName.TRIP_ID.value, body.trip_id),
    )
    for field_name, value in values:
        if value is None:
            continue
        evidence = ExpenseFieldEvidence(
            expense_id=expense.id,
            expense_version=expense.version,
            field_name=field_name,
            source=FieldSource.EMPLOYEE_INPUT.value,
            is_current=True,
            reviewed=False,
            created_by_user_id=uuid.UUID(actor.user_id),
        )
        if field_name in {
            ExpenseFieldName.MERCHANT.value,
            ExpenseFieldName.CATEGORY.value,
            ExpenseFieldName.BUSINESS_PURPOSE.value,
            ExpenseFieldName.CLIENT_NAME.value,
        }:
            evidence.value_text = str(value)
        elif field_name == ExpenseFieldName.EXPENSE_DATE.value:
            evidence.value_date = body.expense_date
        elif field_name == ExpenseFieldName.AMOUNT.value:
            evidence.value_decimal = body.amount
            evidence.currency = body.currency
        elif field_name == ExpenseFieldName.CURRENCY.value:
            evidence.value_text = body.currency
        elif field_name == ExpenseFieldName.ATTENDEE_COUNT.value:
            evidence.value_integer = body.attendee_count
        elif field_name == ExpenseFieldName.TRIP_ID.value:
            evidence.value_text = str(body.trip_id)
        session.add(evidence)
    audit_for_actor(
        session,
        actor,
        action="expense.draft_created",
        entity_type="expense",
        entity_id=expense.id,
        before=None,
        after={"version": 1, "status": expense.status, "channel": expense.channel},
    )
    return expense


def submit_claim(session: Session, actor: Actor, expense: Expense, expected_version: int) -> None:
    if not is_own_claim(actor, expense):
        raise NotFound("That expense was not found.")
    if expense.version != expected_version:
        raise StaleVersion()
    if expense.status not in (ExpenseStatus.DRAFT.value, ExpenseStatus.NEEDS_INFO.value):
        raise Conflict("Only a draft or needs-information claim can be submitted.")
    if (
        not expense.merchant
        or expense.expense_date is None
        or expense.amount is None
        or expense.currency is None
    ):
        raise ValidationFailed(
            "Merchant, expense date, amount and currency are required to submit."
        )
    if (
        session.execute(select(Receipt.id).where(Receipt.expense_id == expense.id).limit(1)).first()
        is None
    ):
        raise ValidationFailed("At least one receipt must be attached before submission.")
    previous = expense.status
    expense.status = ExpenseStatus.SUBMITTED.value
    expense.submitted_at = datetime.now(UTC)
    expense.version += 1
    audit_for_actor(
        session,
        actor,
        action="expense.submitted",
        entity_type="expense",
        entity_id=expense.id,
        before={"status": previous, "version": expected_version},
        after={"status": expense.status, "version": expense.version},
    )


def record_claim_decision(
    session: Session,
    actor: Actor,
    expense: Expense,
    body: DecisionRequest,
    *,
    manager_scope_used: bool = False,
) -> ReviewDecision:
    if expense.version != body.expected_version:
        raise StaleVersion()
    if expense.status not in (ExpenseStatus.SUBMITTED.value, ExpenseStatus.IN_REVIEW.value):
        raise Conflict("Only submitted or in-review claims can receive a review decision.")
    previous = expense.status
    status_by_action = {
        ReviewAction.APPROVE: ExpenseStatus.APPROVED.value,
        ReviewAction.REJECT: ExpenseStatus.REJECTED.value,
        ReviewAction.REQUEST_CORRECTION: ExpenseStatus.NEEDS_INFO.value,
        ReviewAction.ESCALATE: ExpenseStatus.IN_REVIEW.value,
    }
    new_status = status_by_action[body.action]
    if body.action == ReviewAction.ESCALATE and previous == ExpenseStatus.IN_REVIEW.value:
        raise Conflict("The claim is already in review.")
    now = datetime.now(UTC)
    expense.status = new_status
    expense.version += 1
    expense.decided_at = now if body.action in (ReviewAction.APPROVE, ReviewAction.REJECT) else None
    decision = ReviewDecision(
        organization_id=expense.organization_id,
        expense_id=expense.id,
        actor_user_id=uuid.UUID(actor.user_id),
        delegation_basis="active_reporting_relationship" if manager_scope_used else None,
        action=body.action.value,
        reason_code=body.reason_code,
        reason=body.reason.strip() if body.reason else None,
        notes=body.notes,
        previous_status=previous,
        new_status=new_status,
        expense_version=expense.version,
        policy_version_id=expense.evaluated_policy_version_id,
    )
    session.add(decision)
    session.flush()
    audit_for_actor(
        session,
        actor,
        action=f"expense.{body.action.value}",
        entity_type="expense",
        entity_id=expense.id,
        before={"status": previous, "version": body.expected_version},
        after={"status": new_status, "version": expense.version, "decision_id": str(decision.id)},
        reason=decision.reason,
    )
    return decision
