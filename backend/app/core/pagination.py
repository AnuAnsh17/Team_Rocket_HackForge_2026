"""Cursor pagination, matching the envelope in docs/api-contract.md section 4.

    {"items": [...], "page": {"limit": 50, "next_cursor": null, "total": 0}}

The contract names ``next_cursor``, so a cursor is what clients receive. The
implementation is currently an opaque, integrity-checked offset cursor: stable,
cheap, and sufficient for the review tables. It is deliberately opaque so the
storage strategy can become a true keyset cursor later without a contract change
and without any client modification.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import ValidationFailed

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# Cursors are integrity-checked so a hand-edited cursor cannot silently change
# which page a reviewer is looking at. This is not a secret: it is a
# tamper-evidence check over the cursor payload.
_CURSOR_KEY = b"proofline-cursor-v1"


class PageInfo(BaseModel):
    """The ``page`` object of the envelope."""

    limit: int = Field(..., ge=1, le=MAX_LIMIT)
    next_cursor: str | None = None
    total: int | None = Field(
        default=None,
        description=(
            "Total matching rows. Implementations may omit it for expensive counts, "
            "but the choice must be consistent across every list endpoint."
        ),
    )


class Page[T](BaseModel):
    """The full list envelope."""

    items: list[T]
    page: PageInfo


@dataclass(frozen=True, slots=True)
class Pagination:
    """Parsed pagination inputs."""

    limit: int
    offset: int
    cursor: str | None

    def next_cursor(self) -> str | None:
        return encode_cursor(self.offset + self.limit)


def _sign(payload: bytes) -> str:
    return hmac.new(_CURSOR_KEY, payload, sha256).hexdigest()[:16]


def encode_cursor(offset: int) -> str:
    """Encode an offset as an opaque, tamper-evident cursor."""
    payload = json.dumps({"o": offset}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{token}.{_sign(payload)}"


def decode_cursor(cursor: str) -> int:
    """Decode a cursor, rejecting anything tampered with or malformed."""
    try:
        token, _, signature = cursor.partition(".")
        if not token or not signature:
            raise ValueError("malformed cursor")
        padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii"))
        if not hmac.compare_digest(_sign(payload), signature):
            raise ValueError("cursor signature mismatch")
        data: Any = json.loads(payload.decode("utf-8"))
        offset = int(data["o"])
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValidationFailed(
            "The pagination cursor is not valid. Request the first page without a cursor.",
            details=[{"field": "cursor"}],
        ) from exc
    if offset < 0:
        raise ValidationFailed("The pagination cursor is not valid.", details=[{"field": "cursor"}])
    return offset


def build_page[T](items: list[T], pagination: Pagination, total: int | None) -> Page[T]:
    """Assemble the response envelope.

    ``next_cursor`` is emitted only when another page actually exists, so a
    client never loops on an empty trailing page.
    """
    has_more = False
    if total is not None:
        has_more = pagination.offset + len(items) < total
    else:
        # Without a total, a full page implies there may be more.
        has_more = len(items) == pagination.limit
    return Page[T](
        items=items,
        page=PageInfo(
            limit=pagination.limit,
            next_cursor=pagination.next_cursor() if has_more and items else None,
            total=total,
        ),
    )
