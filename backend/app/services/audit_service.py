"""Service-layer audit helpers.

A thin wrapper over :func:`app.audit.writer.record_audit_event` that also builds
events from an :class:`~app.core.security.Actor`, so routes and services do not
each re-derive actor type, user id and label. There is no update or delete helper
here, and there never should be.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.writer import record_audit_event
from app.core.enums import AuditActorType
from app.core.security import Actor
from app.models.audit import AuditEvent


def audit(
    session: Session,
    *,
    action: str,
    entity_type: str,
    actor_type: AuditActorType,
    entity_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    policy_version_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> AuditEvent:
    """Append an audit event to the caller's transaction."""
    return record_audit_event(
        session,
        action=action,
        entity_type=entity_type,
        actor_type=actor_type,
        entity_id=entity_id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        before=before,
        after=after,
        policy_version_id=policy_version_id,
        reason=reason,
    )


def audit_for_actor(
    session: Session,
    actor: Actor,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    policy_version_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> AuditEvent:
    """Append an audit event attributed to the authenticated actor."""
    return record_audit_event(
        session,
        action=action,
        entity_type=entity_type,
        actor_type=actor.actor_type,
        entity_id=entity_id,
        organization_id=organization_id or _as_uuid(actor.active_organization_id),
        actor_user_id=_as_uuid(actor.user_id),
        actor_label=actor.identity.email or actor.user_id,
        before=before,
        after=after,
        policy_version_id=policy_version_id,
        reason=reason,
    )


def _as_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
