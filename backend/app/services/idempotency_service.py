"""Idempotent mutation support.

A retried create/submit/decision must not create a second effect. The mechanism:

1. The first request with a given ``Idempotency-Key`` for a given actor is
   processed and its response stored.
2. A retry with the same key and the same normalised body replays the stored
   response.
3. A retry with the same key but a *different* body is refused with
   ``IDEMPOTENCY_CONFLICT``. Silently applying the second body would be worse than
   failing: the caller would believe one thing happened while another did.
4. The same key from a *different* actor is a different key. Keys are scoped per
   actor so one user cannot consume or replay another's.

Nothing in this scaffold requires idempotency yet - no mutation route is
implemented - but the boundary exists so the first mutation route that is added
has somewhere correct to live.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import IdempotencyConflict, ValidationFailed
from app.core.logging import get_logger
from app.models.audit import IdempotencyKey

logger = get_logger(__name__)

DEFAULT_TTL = timedelta(hours=24)


def normalise_request_hash(payload: Any) -> str:
    """Stable hash of a request body.

    Canonical JSON with sorted keys so that key ordering and whitespace cannot
    make two identical requests look different.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def begin(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    key: str | None,
    method: str,
    path: str,
    payload: Any,
    required: bool = True,
) -> IdempotencyKey | None:
    """Claim an idempotency key, or replay the stored response.

    Returns ``None`` when the request should proceed and no key was supplied. The
    caller inspects ``response_status`` on the returned record: when it is set, the
    request has already been completed and the stored response must be replayed
    instead of re-executing.
    """
    if not key:
        if required:
            raise ValidationFailed(
                "This endpoint requires an Idempotency-Key header so that a retry cannot "
                "create a second effect.",
                details=[{"field": "Idempotency-Key"}],
            )
        return None

    request_hash = normalise_request_hash(payload)
    existing = session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.actor_user_id == actor_user_id,
            IdempotencyKey.idempotency_key == key,
        )
    ).scalar_one_or_none()

    if existing is None:
        record = IdempotencyKey(
            actor_user_id=actor_user_id,
            idempotency_key=key,
            request_method=method,
            request_path=path,
            request_hash=request_hash,
            expires_at=datetime.now(UTC) + DEFAULT_TTL,
        )
        session.add(record)
        session.flush()
        return record

    if existing.request_hash != request_hash:
        raise IdempotencyConflict(
            "This Idempotency-Key was already used with a different request body. "
            "Use a new key for a new request.",
            details=[{"field": "Idempotency-Key"}],
        )

    logger.info("replaying stored idempotent response", extra={"path": path})
    return existing


def complete(
    record: IdempotencyKey | None,
    *,
    status_code: int,
    body: dict[str, Any] | None,
) -> None:
    """Record the response for a completed request."""
    if record is None:
        return
    record.response_status = status_code
    record.response_body = body
    record.completed_at = datetime.now(UTC)
