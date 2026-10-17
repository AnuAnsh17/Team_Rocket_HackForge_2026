"""Audit event DTO."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.core.enums import AuditActorType
from app.schemas.common import ApiModel, Page


class AuditEventResponse(ApiModel):
    """One append-only audit event.

    ``before``/``after`` are safe diffs: they contain the fields that changed and
    never raw receipt content, OCR text or credentials.
    """

    id: uuid.UUID
    created_at: datetime
    actor_type: AuditActorType
    actor_user_id: uuid.UUID | None = None
    actor_label: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    before: dict[str, object] | None = None
    after: dict[str, object] | None = None
    policy_version_id: uuid.UUID | None = None
    reason: str | None = None
    correlation_id: str | None = Field(
        default=None,
        description="Ties this event to the request that caused it and to the server log line.",
    )


class AuditEventListResponse(Page[AuditEventResponse]):
    pass
