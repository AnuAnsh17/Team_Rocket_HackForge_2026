"""Append-only audit events and idempotency records.

``audit_events`` is the spine of the product's explainability claim: which actor
did what, to which entity, when, with what before/after values, under which
policy version, and under which request correlation id.

Append-only is enforced, not merely intended. The initial migration installs a
PostgreSQL trigger that raises on UPDATE or DELETE against this table, so an
accidental ORM update or a manual data fix fails loudly instead of silently
rewriting history. There is deliberately no update or delete method anywhere in
app/audit.

``idempotency_keys`` makes a retried create/submit/decision safe: the first
response is stored and replayed, and a retry with a different payload is refused
with IDEMPOTENCY_CONFLICT instead of creating a second effect.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditActorType
from app.db.base import (
    Base,
    CreatedAtMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
)


class AuditEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One immutable application audit event.

    WHY THIS TABLE HAS NO FOREIGN KEYS
    ----------------------------------
    An append-only table must not participate in cascading referential actions.
    Every ``ON DELETE SET NULL`` / ``ON DELETE CASCADE`` on a parent row makes
    PostgreSQL issue an ``UPDATE`` or ``DELETE`` against this table, which the
    append-only trigger then refuses - correctly, but with a confusing failure at
    the point of deleting an unrelated record (deleting an organization failed
    because it tried to null out an audit column).

    The columns are therefore retained as plain UUIDs and are deliberately NOT
    constrained:

    * The audit log is the record of what happened. It must survive the deletion or
      deactivation of the organization, user or policy version it refers to; a
      historical event that vanishes with its subject is not an audit trail.
    * ``organization_id`` remains indexed, so scoped reads stay fast.
    * Referential integrity for these columns is checked at write time by
      app/audit/writer.py, which only ever receives ids of rows the caller has
      already loaded.

    This is a record-keeping decision, not an oversight. The guarantee provided is
    database-enforced append-only behaviour (a trigger that refuses UPDATE and
    DELETE); it is explicitly NOT cryptographic immutability, and this docstring
    should not be read as claiming otherwise.
    """

    __tablename__ = "audit_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    actor_type: Mapped[str] = enum_column(AuditActorType)
    # Human-readable actor label captured at event time so history stays readable
    # even if the user row is later deactivated or renamed.
    actor_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    before: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        in_enum("actor_type", AuditActorType),
        CheckConstraint(
            "actor_type = 'system' OR actor_user_id IS NOT NULL OR actor_type = 'demo'",
            name="actor_identified",
        ),
    )


class IdempotencyKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A stored first response for a retried state-changing request."""

    __tablename__ = "idempotency_keys"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_method: Mapped[str] = mapped_column(String(10), nullable=False)
    request_path: Mapped[str] = mapped_column(String(400), nullable=False)
    # Hash of the normalised request body. A retry with the same key but a
    # different body is refused rather than silently applied.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("actor_user_id", "idempotency_key"),
        CheckConstraint("length(btrim(idempotency_key)) > 0", name="key_not_blank"),
    )
