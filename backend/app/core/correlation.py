"""Helpers for reading and propagating the request correlation id."""

from __future__ import annotations

import uuid

from app.core.logging import correlation_id_ctx


def current_correlation_id() -> str:
    """Return the correlation id for the current request/task.

    Falls back to a fresh id so background work (a re-evaluation job, a CLI
    script) still produces auditable, traceable events.
    """
    return correlation_id_ctx.get() or uuid.uuid4().hex
