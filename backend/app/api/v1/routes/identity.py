"""Authenticated-actor endpoints.

``GET /api/v1/me`` is the smallest endpoint that proves the whole authorization
path works end to end: a verified identity is resolved to an actor, the actor's
membership and role grants are read from the database, permissions are derived
server-side, and the response is scoped to the actor's own organization.

It deliberately returns no permission list. Permissions are enforced by the
server; publishing them to a client would invite a client to rely on them,
which is precisely the trust boundary this design refuses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_session
from app.core.enums import MembershipStatus
from app.core.security import Actor
from app.models.audit import AuditEvent
from app.models.identity import OrganizationMembership, RoleAssignment
from app.schemas.audit import AuditEventListResponse, AuditEventResponse
from app.schemas.common import PageInfo
from app.schemas.identity import MembershipSummary, RoleAssignmentSummary, UserSummary
from app.services.scope_service import require_same_organization

router = APIRouter(tags=["identity"])


@router.get(
    "/me",
    response_model=MembershipSummary,
    summary="The authenticated employee's own membership",
    description=(
        "Resolves the caller's own organization membership. The actor is derived from the "
        "validated identity and server-side role grants; nothing about identity, role or "
        "scope is taken from the request body or query string."
    ),
)
def read_me(
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> MembershipSummary:
    membership = session.get(OrganizationMembership, actor.active_membership_id)
    if membership is None:  # pragma: no cover - get_actor already validated this
        raise RuntimeError("Actor resolved without a membership")
    require_same_organization(actor, membership.organization_id)

    from app.models.identity import User

    user = session.get(User, membership.user_id)
    return MembershipSummary(
        id=membership.id,
        organization_id=membership.organization_id,
        user=UserSummary(
            id=membership.user_id,
            display_name=user.display_name if user else "Unknown",
            is_active=user.is_active if user else False,
        ),
        employee_code=membership.employee_code,
        status=MembershipStatus(membership.status),
        manager_membership_id=membership.primary_manager_membership_id,
        joined_on=membership.joined_on,
    )


@router.get(
    "/me/roles",
    response_model=list[RoleAssignmentSummary],
    summary="The authenticated actor's own role grants",
    description=(
        "Returns the caller's own non-revoked role grants with the scope each applies to. "
        "Granted only through organization memberships; a client cannot request someone "
        "else's grants, because the membership is taken from the validated identity."
    ),
)
def read_my_roles(
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> list[RoleAssignmentSummary]:
    rows = (
        session.execute(
            select(RoleAssignment).where(
                RoleAssignment.membership_id == actor.active_membership_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    return [
        RoleAssignmentSummary(
            id=row.id,
            role=row.role,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            granted_at=row.granted_at.date() if row.granted_at else None,
            revoked_at=row.revoked_at.date() if row.revoked_at else None,
        )
        for row in rows
    ]


@router.get(
    "/me/audit",
    response_model=AuditEventListResponse,
    summary="Audit events attributed to the authenticated actor",
    description=(
        "An employee may read their own audit trail. Reading another actor's trail requires "
        "a scoped review permission and is not exposed here."
    ),
)
def read_my_audit(
    request: Request,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> AuditEventListResponse:
    from uuid import UUID

    rows = (
        session.execute(
            select(AuditEvent)
            .where(AuditEvent.actor_user_id == UUID(actor.user_id))
            .order_by(AuditEvent.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return AuditEventListResponse(
        items=[AuditEventResponse.model_validate(row) for row in rows],
        page=PageInfo(limit=50, next_cursor=None, total=len(rows)),
    )
