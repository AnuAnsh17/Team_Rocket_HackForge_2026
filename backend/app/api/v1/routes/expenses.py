"""Employee-owned draft creation required by the receipt upload workflow."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.audit.writer import record_audit_event
from app.core.enums import ExpenseFieldName, ExpenseStatus, FieldSource
from app.core.errors import Forbidden, ValidationFailed
from app.core.permissions import Permission
from app.core.security import Actor
from app.models.expense import Expense, ExpenseFieldEvidence, Trip
from app.schemas.expense import CreateExpenseRequest
from app.schemas.receipt import DraftExpenseResponse
from app.services import idempotency_service

router = APIRouter(tags=["expenses"])


@router.post(
    "/expenses",
    response_model=DraftExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an employee-owned draft expense",
    description=(
        "Creates a draft for the caller's active membership so a receipt can be attached. "
        "This workflow slice does not support creating claims for another employee."
    ),
)
def create_draft_expense(
    body: CreateExpenseRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(require(Permission.EXPENSE_CREATE_OWN)),
    session: Session = Depends(get_session),
) -> DraftExpenseResponse:
    if actor.active_membership_id is None or actor.active_organization_id is None:
        raise Forbidden("An active organization membership is required to create a draft.")
    if body.employee_membership_id is not None and body.employee_membership_id != uuid.UUID(
        actor.active_membership_id
    ):
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

    payload = body.model_dump(mode="json", exclude={"employee_membership_id"})
    idem = idempotency_service.begin(
        session,
        actor_user_id=uuid.UUID(actor.user_id),
        key=idempotency_key,
        method="POST",
        path=request.url.path,
        payload=payload,
    )
    if idem is not None and idem.response_body is not None:
        return DraftExpenseResponse.model_validate(idem.response_body)

    expense = Expense(
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

    evidence_values: tuple[tuple[str, object | None], ...] = (
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
    for field_name, value in evidence_values:
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

    response = DraftExpenseResponse(
        id=expense.id,
        organization_id=expense.organization_id,
        channel=expense.channel,
        status=expense.status,
        version=expense.version,
        created_at=expense.created_at,
    )
    idempotency_service.complete(
        idem, status_code=status.HTTP_201_CREATED, body=response.model_dump(mode="json")
    )
    record_audit_event(
        session,
        action="expense.draft_created",
        entity_type="expense",
        entity_id=expense.id,
        organization_id=expense.organization_id,
        actor_user_id=uuid.UUID(actor.user_id),
        actor_type=actor.actor_type,
        after={"version": expense.version, "status": expense.status, "channel": expense.channel},
    )
    return response
