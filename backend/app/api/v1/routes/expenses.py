"""Employee-owned draft creation required by the receipt upload workflow."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.core.permissions import Permission
from app.core.security import Actor
from app.schemas.expense import CreateExpenseRequest
from app.schemas.receipt import DraftExpenseResponse
from app.services import idempotency_service
from app.services.expense_workflow_service import create_draft_claim

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

    expense = create_draft_claim(session, actor, body)

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
    return response
