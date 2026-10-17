"""The only way an audit event enters the system."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.correlation import current_correlation_id
from app.core.enums import AuditActorType
from app.core.logging import get_logger, redact
from app.models.audit import AuditEvent

logger = get_logger(__name__)

# Field names that must never be copied into an audit snapshot. Even though the
# audit trail is privileged, storing receipt bytes or credentials there would
# widen the blast radius of a single leak.
_FORBIDDEN_SNAPSHOT_KEYS = frozenset(
    {
        "raw_text",
        "ocr_text",
        "extracted_text",
        "content",
        "file_bytes",
        "receipt_bytes",
        "object_key",
        "storage_key",
        "token",
        "secret",
        "password",
        "api_key",
    }
)


def _safe_snapshot(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip forbidden keys from a before/after snapshot.

    Applied on the way in, so a forbidden field cannot reach the table at all rather
    than being filtered when the event is later read.
    """
    if payload is None:
        return None
    redacted = redact(payload)
    if not isinstance(redacted, dict):
        # redact() only ever returns a mapping for a mapping input; this guard keeps the
        # return type honest without an unchecked cast.
        return None
    snapshot: dict[str, Any] = {str(key): value for key, value in redacted.items()}
    for key in list(snapshot):
        if key.lower() in _FORBIDDEN_SNAPSHOT_KEYS:
            snapshot.pop(key)
    return snapshot


def record_audit_event(
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
    correlation_id: str | None = None,
) -> AuditEvent:
    """Append one audit event to the session.

    The caller must commit. That is intentional: the caller's transaction is the
    unit of atomicity, so a state change and its audit event either both persist
    or neither does. Changing a claim status in one transaction and writing its
    audit event in another is exactly the failure mode this signature prevents.
    """
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type.value,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_safe_snapshot(before),
        after=_safe_snapshot(after),
        policy_version_id=policy_version_id,
        reason=reason,
        correlation_id=correlation_id or current_correlation_id(),
    )
    session.add(event)
    logger.info(
        "audit event recorded",
        extra={"action": action, "entity_type": entity_type, "entity_id": str(entity_id)},
    )
    return event
