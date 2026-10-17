"""Resource-level scope enforcement.

Permissions answer "may this actor do this kind of thing at all". This module
answers the separate and equally important question: "may this actor do it to
*this* record".

Both must pass. A finance reviewer holds ``expense:read_org_scoped``; that does not
mean they may read any claim in any organization. A manager holds
``expense:read_team``; that means their explicit direct reports, not everyone in
their department.

Every check here fails closed. A missing relationship is a refusal, never a
default allow.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import RoleCode
from app.core.errors import Forbidden, NotFound
from app.core.logging import get_logger
from app.core.security import Actor
from app.models.expense import Expense
from app.models.identity import OrganizationMembership, ReportingRelationship

logger = get_logger(__name__)


def _as_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def require_same_organization(actor: Actor, organization_id: uuid.UUID) -> None:
    """The actor must be acting inside the organization that owns the record.

    This is the tenant boundary. Without it, a valid permission from one
    organization would authorise access to another's data.
    """
    active = _as_uuid(actor.active_organization_id)
    if active is None or active != organization_id:
        raise Forbidden("This record belongs to an organization you are not acting within.")


def is_own_claim(actor: Actor, expense: Expense) -> bool:
    return str(expense.membership_id) == (actor.active_membership_id or "")


def is_direct_report(session: Session, actor: Actor, expense: Expense) -> bool:
    """Whether the actor manages this claim's owner through an active edge.

    Only ``primary`` and ``secondary`` reporting edges count. A ``dotted``
    relationship is recorded for display and context but does not confer approval
    authority.
    """
    manager_id = _as_uuid(actor.active_membership_id)
    if manager_id is None:
        return False
    today = date.today()
    edge = (
        session.execute(
            select(ReportingRelationship.id).where(
                ReportingRelationship.organization_id == expense.organization_id,
                ReportingRelationship.manager_membership_id == manager_id,
                ReportingRelationship.employee_membership_id == expense.membership_id,
                ReportingRelationship.relationship_type.in_(("primary", "secondary")),
                ReportingRelationship.effective_from <= today,
            )
        )
        .scalars()
        .first()
    )
    if edge is None:
        return False
    # Confirm the window is still open.
    open_edge = (
        session.execute(
            select(ReportingRelationship.id).where(
                ReportingRelationship.organization_id == expense.organization_id,
                ReportingRelationship.manager_membership_id == manager_id,
                ReportingRelationship.employee_membership_id == expense.membership_id,
                ReportingRelationship.relationship_type.in_(("primary", "secondary")),
                ReportingRelationship.effective_from <= today,
                (ReportingRelationship.effective_to.is_(None))
                | (ReportingRelationship.effective_to >= today),
            )
        )
        .scalars()
        .first()
    )
    return open_edge is not None


def require_expense_read(session: Session, actor: Actor, expense_id: uuid.UUID) -> Expense:
    """Load a claim the actor is allowed to read, or refuse.

    A missing record and a forbidden record both raise, and the caller's route
    maps them to the same response so that a claim's existence is not disclosed to
    an unauthorised caller.
    """
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise NotFound("That expense was not found.")

    require_same_organization(actor, expense.organization_id)
    owner_membership = session.get(OrganizationMembership, expense.membership_id)
    if owner_membership is None or owner_membership.organization_id != expense.organization_id:
        raise NotFound("That expense was not found.")

    if is_own_claim(actor, expense):
        return expense
    if any(
        role in actor.roles
        for role in (
            RoleCode.FINANCE_REVIEWER,
            RoleCode.FINANCE_ADMIN,
            RoleCode.HR_REVIEWER,
            RoleCode.AUDITOR,
        )
    ):
        # Permission checks remain a separate route-level gate. Scope this read
        # to the active organization; queue/department narrowing awaits an
        # approved workflow configuration.
        return expense
    if RoleCode.MANAGER in actor.roles and is_direct_report(session, actor, expense):
        return expense
    if RoleCode.EMPLOYEE not in actor.roles and actor.permissions:
        # Any other privileged role still requires an explicit relationship above.
        logger.info(
            "scoped expense read refused",
            extra={"actor_roles": sorted(role.value for role in actor.roles)},
        )
    raise NotFound("That expense was not found.")


def require_expense_write(session: Session, actor: Actor, expense_id: uuid.UUID) -> Expense:
    """Load a claim the actor is allowed to correct."""
    expense = require_expense_read(session, actor, expense_id)
    if not is_own_claim(actor, expense) and not (
        RoleCode.FINANCE_REVIEWER in actor.roles or RoleCode.FINANCE_ADMIN in actor.roles
    ):
        raise Forbidden(
            "Only the claim owner or an authorized finance reviewer may change this claim."
        )
    return expense


def teammate_membership_ids(session: Session, actor: Actor) -> tuple[uuid.UUID, ...]:
    """Memberships the actor may read through a reporting relationship."""
    manager_id = _as_uuid(actor.active_membership_id)
    if manager_id is None:
        return ()
    today = date.today()
    rows = (
        session.execute(
            select(ReportingRelationship.employee_membership_id).where(
                ReportingRelationship.organization_id == _as_uuid(actor.active_organization_id),
                ReportingRelationship.manager_membership_id == manager_id,
                ReportingRelationship.relationship_type.in_(("primary", "secondary")),
                ReportingRelationship.effective_from <= today,
                (ReportingRelationship.effective_to.is_(None))
                | (ReportingRelationship.effective_to >= today),
            )
        )
        .scalars()
        .all()
    )
    return tuple(rows)


def membership_or_refuse(session: Session, membership_id: uuid.UUID) -> OrganizationMembership:
    membership = session.get(OrganizationMembership, membership_id)
    if membership is None:
        raise NotFound("That employee record was not found.")
    return membership
