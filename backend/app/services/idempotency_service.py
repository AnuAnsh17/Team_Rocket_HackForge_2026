"""Idempotent mutation support.

A retried state-changing request must not create a second effect. The mechanism:

1. The first request with a given ``Idempotency-Key`` for a given actor is
   processed and its response stored.
2. A retry with the same key, method, path and normalised body replays the stored
   response.
3. Reusing a key with a different method, path or body is refused with
   ``IDEMPOTENCY_CONFLICT``. Silently applying the second body would be worse than
   failing: the caller would believe one thing happened while another did.
4. The same key from a *different* actor is a different key. Keys are scoped per
   actor so one user cannot consume or replay another's.

Expense creation, correction, submission, review decisions and receipt mutation
routes use this boundary.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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


def _find_existing(session: Session, actor_user_id: uuid.UUID, key: str) -> IdempotencyKey | None:
    """The stored record for this actor and key, if one has been committed."""
    return session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.actor_user_id == actor_user_id,
            IdempotencyKey.idempotency_key == key,
        )
    ).scalar_one_or_none()


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
    caller inspects ``response_body`` on the returned record: when it is set, the
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
    existing = _find_existing(session, actor_user_id, key)

    if existing is None:
        record_id = uuid.uuid4()
        inserted_id = session.execute(
            pg_insert(IdempotencyKey)
            .values(
                id=record_id,
                actor_user_id=actor_user_id,
                idempotency_key=key,
                request_method=method,
                request_path=path,
                request_hash=request_hash,
                expires_at=datetime.now(UTC) + DEFAULT_TTL,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["actor_user_id", "idempotency_key"])
            .returning(IdempotencyKey.id)
        ).scalar_one_or_none()

        if inserted_id is not None:
            claim = session.get(IdempotencyKey, record_id)
            if claim is None:  # pragma: no cover - we just inserted this row
                raise RuntimeError("The idempotency key row vanished within its own transaction.")
            return claim

        # The insert did nothing, so a concurrent request with the same key committed
        # between our lookup and this statement. This is a fast client retry, not a
        # caller error: the generating dependency in app/api/deps.py commits after the
        # response has been sent, so a retry that arrives promptly can run this lookup
        # before the original request's transaction has committed and therefore miss
        # it.
        #
        # The winner is authoritative, so replay its stored response - which is what
        # the key was supplied for. Failing the retry with a 500 would be the worst
        # outcome, because the original effect did happen and the client would have no
        # way to learn that.
        #
        # ON CONFLICT DO NOTHING is used rather than catching the unique violation so
        # that no failed statement is left in the transaction: a caught IntegrityError
        # leaves the session unusable until it is rolled back, which would discard the
        # rest of the request.
        existing = _find_existing(session, actor_user_id, key)
        if existing is None:  # pragma: no cover - the index guarantees otherwise
            raise RuntimeError("An idempotency key conflict could not be resolved.")

    if (
        existing.request_hash != request_hash
        or existing.request_method != method
        or existing.request_path != path
    ):
        raise IdempotencyConflict(
            "This Idempotency-Key was already used for a different request. "
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
