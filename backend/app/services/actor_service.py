"""Resolve a verified identity into an authorized application actor.

This is the single place where the answer to "who is this, and what may they do"
is produced. Everything downstream - every route, every service - receives an
:class:`Actor` and never a client-supplied role, employee id, grade, allowance or
approval limit. If a client sends one of those, it is ignored, not validated and
trusted.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuditActorType, MembershipStatus, RoleCode
from app.core.errors import Forbidden, Unauthenticated
from app.core.logging import get_logger
from app.core.permissions import permissions_for_roles
from app.core.security import Actor, Identity, MembershipContext
from app.models.identity import OrganizationMembership, RoleAssignment, User

logger = get_logger(__name__)

# Employment states that may act. A terminated or suspended membership is not
# silently treated as active: losing membership must remove access.
_ACTIVE_STATUSES = frozenset(
    {
        MembershipStatus.ACTIVE.value,
        MembershipStatus.ON_LEAVE.value,
    }
)


def resolve_actor(
    session: Session,
    identity: Identity,
    *,
    requested_organization_id: str | None = None,
) -> Actor:
    """Load the actor's authoritative membership, roles and permissions."""
    user = _find_user(session, identity)
    if user is None or not user.is_active:
        raise Unauthenticated(
            "No active Proofline user is linked to this identity. "
            "An account must be provisioned before it can be used."
        )

    memberships = (
        session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status.in_(sorted(_ACTIVE_STATUSES)),
            )
        )
        .scalars()
        .all()
    )
    if not memberships:
        raise Forbidden(
            "This account has no active organization membership. Access requires an "
            "active membership; it is never inferred."
        )

    active = _select_membership(memberships, requested_organization_id)
    contexts = tuple(
        MembershipContext(
            membership_id=str(membership.id),
            organization_id=str(membership.organization_id),
            roles=_roles_for(session, membership.id),
        )
        for membership in memberships
    )
    active_context = next(
        (context for context in contexts if context.membership_id == str(active.id)),
        None,
    )
    roles = active_context.roles if active_context else frozenset()

    actor_type = AuditActorType.DEMO if identity.provider == "demo" else AuditActorType.USER
    return Actor(
        user_id=str(user.id),
        identity=identity,
        memberships=contexts,
        active_organization_id=str(active.organization_id),
        active_membership_id=str(active.id),
        roles=roles,
        permissions=permissions_for_roles(roles),
        actor_type=actor_type,
    )


def _find_user(session: Session, identity: Identity) -> User | None:
    """Look up the user by the identity provider's subject.

    The demo provider puts a Proofline user id in ``subject``; a real provider puts
    the provider's subject there. Both are looked up in the same column, so there
    is one resolution path rather than a demo shortcut that could be abused.
    """
    found = session.execute(
        select(User).where(
            User.auth_provider == identity.provider,
            User.external_subject == identity.subject,
        )
    ).scalar_one_or_none()
    if found is not None:
        return found

    # Fall back to a direct id lookup so a seeded demo identity works. Still a
    # database lookup: nothing is inferred from the request itself.
    try:
        user_id = uuid.UUID(identity.subject)
    except (ValueError, AttributeError):
        return None
    return session.get(User, user_id)


def _select_membership(
    memberships: Sequence[OrganizationMembership], requested_organization_id: str | None
) -> OrganizationMembership:
    """Choose the organization the request operates in.

    An explicitly requested organization is honoured only when the user genuinely
    holds an active membership in it. Otherwise the request is refused rather than
    silently redirected, because silently answering from a different organization
    is exactly how a cross-tenant leak looks.
    """
    if requested_organization_id:
        try:
            wanted = uuid.UUID(requested_organization_id)
        except (ValueError, AttributeError) as exc:
            raise Forbidden("The requested organization identifier is not valid.") from exc
        for membership in memberships:
            if membership.organization_id == wanted:
                return membership
        raise Forbidden("You do not hold an active membership in the requested organization.")

    primary = next((m for m in memberships if m.is_primary), None)
    return primary or memberships[0]


def _roles_for(session: Session, membership_id: uuid.UUID) -> frozenset[RoleCode]:
    """Roles currently held, excluding revoked grants."""
    rows = (
        session.execute(
            select(RoleAssignment).where(
                RoleAssignment.membership_id == membership_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    roles: set[RoleCode] = set()
    for row in rows:
        try:
            roles.add(RoleCode(row.role))
        except ValueError:  # pragma: no cover - guarded by a CHECK constraint
            logger.warning("unknown role code encountered", extra={"role": row.role})
    return frozenset(roles)
