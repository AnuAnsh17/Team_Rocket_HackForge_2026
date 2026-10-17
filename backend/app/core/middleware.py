"""Request correlation and access logging."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger("proofline.request")

REQUEST_ID_HEADER = "x-request-id"

# Paths whose access log lines add noise without adding information.
_QUIET_PATHS = frozenset({"/api/v1/health", "/health", "/favicon.ico"})


def _sanitise_request_id(value: str | None) -> str:
    """Accept a client correlation id only if it is short and printable.

    A client-supplied value reaches log files and audit events, so it is
    constrained rather than echoed blindly.
    """
    if not value:
        return uuid.uuid4().hex
    candidate = value.strip()
    if not candidate or len(candidate) > 128:
        return uuid.uuid4().hex
    if not all(character.isprintable() and character not in "\r\n\t" for character in candidate):
        return uuid.uuid4().hex
    return candidate


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id, log one line per request, echo the id back.

    The correlation id is what lets a reviewer tie a dashboard action to an
    audit event and to the server log line for that action.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _sanitise_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = correlation_id_ctx.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            correlation_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id

        if request.url.path not in _QUIET_PATHS:
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response
