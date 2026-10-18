"""Policy pre-flight.

``POST /api/v1/policy/check`` was documented as deferred pending an approved policy
document. It is now implemented as a strictly advisory, read-only calculation: the
response says what the governing policy *would* say about a claim, and the endpoint writes
nothing at all - no claim, no finding, no status transition, no audit event.

That read-only property is the point. A pre-flight is called while an employee is still
filling in a form, so it must be safe to call repeatedly and must never leave a trace in
the claim's history.

The demo policy stays inert unless the explicit local flags are set. When
``DEMO_SYNTHETIC_POLICY_ENABLED`` is false the registry loads no fictional rule, and this
endpoint returns UNKNOWN findings rather than fictional ones.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_session
from app.core.security import Actor
from app.schemas.policy import PolicyCheckRequest, PolicyCheckResponse
from app.services.policy_check_service import check_policy

router = APIRouter(tags=["policy"])


@router.post(
    "/policy/check",
    response_model=PolicyCheckResponse,
    summary="Advisory policy pre-flight",
    description=(
        "Evaluate a draft claim or an inline preview against the governing policy. "
        "Advisory only: nothing is persisted, no status changes and no finding is recorded. "
        "An expense_id is subject to the same authorization as reading that claim; an inline "
        "preview is evaluated against the caller's own organization and membership."
    ),
)
def policy_check(
    body: PolicyCheckRequest,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> PolicyCheckResponse:
    return check_policy(session, actor, body)
