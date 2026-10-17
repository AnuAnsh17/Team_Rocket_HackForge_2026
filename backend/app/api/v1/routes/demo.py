"""Demo-only utilities.

Registered at all only when DEMO_MODE is true and APP_ENV is not production. When
demo mode is off the router is absent, so these paths answer 404 rather than
revealing that a disabled demo surface exists.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.core.enums import AuditActorType
from app.core.permissions import Permission
from app.core.security import Actor
from app.schemas.demo import DemoResetResponse, DemoSeedResponse
from app.services import demo_service

router = APIRouter(tags=["demo"], prefix="/demo")


@router.post(
    "/seed",
    response_model=DemoSeedResponse,
    summary="Load the synthetic demo dataset (demo mode only)",
    description=(
        "Loads deterministic, clearly labelled synthetic data: one fictional organization, "
        "fictional people, memberships, role grants and reporting edges, plus an unapproved "
        "and empty policy version. Creates no policy rules and no allowance limits, because "
        "both require real organizational data and a verified policy clause."
    ),
)
def seed(
    actor: Actor = Depends(require(Permission.DEMO_SEED_RESET)),
    session: Session = Depends(get_session),
) -> DemoSeedResponse:
    return demo_service.seed_demo_dataset(
        session,
        actor_user_id=UUID(actor.user_id),
        actor_label=f"demo seed by {actor.user_id}",
    )


@router.post(
    "/reset",
    response_model=DemoResetResponse,
    summary="Remove only the synthetic demo dataset (demo mode only)",
    description=(
        "Deletes the fixed demo organization and demo-provider users. Non-demo data is not "
        "reachable from this operation. Audit events are append-only and survive the reset; "
        "the reset itself is recorded as an audit event."
    ),
)
def reset(
    actor: Actor = Depends(require(Permission.DEMO_SEED_RESET)),
    session: Session = Depends(get_session),
) -> DemoResetResponse:
    return demo_service.reset_demo_dataset(session, actor_label=f"demo reset by {actor.user_id}")


@router.post(
    "/import/email",
    status_code=501,
    summary="Simulate an email-channel submission (NOT IMPLEMENTED)",
    description=(
        "The contract describes this route for demoing a cross-channel duplicate. It is not "
        "implemented, and it must never be presented as a real email integration."
    ),
)
def simulate_email_import() -> dict[str, str]:
    from app.core.errors import NotImplementedYet

    raise NotImplementedYet(
        "Simulated email import is not implemented. It exists in the contract so the "
        "cross-channel duplicate scenario has a documented entry point; no email integration "
        "exists and none is implied."
    )


# Referenced so the audit actor type used by the seed is visible next to the routes.
DEMO_ACTOR_TYPE = AuditActorType.DEMO
