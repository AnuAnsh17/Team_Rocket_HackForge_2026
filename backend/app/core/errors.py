"""The single error envelope.

Every error a client can observe passes through here, which guarantees:

  - one response shape, declared in docs/api-contract.md section 4;
  - stable machine-readable ``code`` values that clients can branch on;
  - a user-facing ``message`` that is deliberately separate from internal ids;
  - a ``request_id`` so a reviewer can quote one identifier in a bug report;
  - no stack trace, SQL fragment, provider payload or secret ever reaches a
    client, including in unexpected-error responses.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger(__name__)


class ErrorCode:
    """Canonical error codes. Values are part of the public contract."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    STALE_VERSION = "STALE_VERSION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    POLICY_CONTEXT_UNKNOWN = "POLICY_CONTEXT_UNKNOWN"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Base class for every deliberately raised application error."""

    code: str = ErrorCode.INTERNAL_ERROR
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or []
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class ValidationFailed(AppError):
    code = ErrorCode.VALIDATION_ERROR
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    default_message = "The request could not be processed."


class Unauthenticated(AppError):
    code = ErrorCode.UNAUTHENTICATED
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Authentication is required."


class Forbidden(AppError):
    code = ErrorCode.FORBIDDEN
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "You are not authorized to perform this action."


class NotFound(AppError):
    code = ErrorCode.NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "The requested resource was not found."


class Conflict(AppError):
    code = ErrorCode.CONFLICT
    status_code = status.HTTP_409_CONFLICT
    default_message = "The request conflicts with the current state."


class StaleVersion(Conflict):
    code = ErrorCode.STALE_VERSION
    default_message = "This record changed since it was loaded. Reload and retry."


class IdempotencyConflict(Conflict):
    code = ErrorCode.IDEMPOTENCY_CONFLICT
    default_message = "This Idempotency-Key was already used with a different request payload."


class PolicyContextUnknown(AppError):
    code = ErrorCode.POLICY_CONTEXT_UNKNOWN
    status_code = status.HTTP_409_CONFLICT
    default_message = (
        "The policy context for this request is not resolved. "
        "It is reported as unknown rather than assumed."
    )


class ExtractionFailed(AppError):
    code = ErrorCode.EXTRACTION_FAILED
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "Receipt extraction did not complete."


class UnsupportedMediaType(AppError):
    code = ErrorCode.UNSUPPORTED_MEDIA_TYPE
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_message = "That file type is not accepted."


class PayloadTooLarge(AppError):
    code = ErrorCode.PAYLOAD_TOO_LARGE
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    default_message = "The uploaded file is larger than the configured limit."


class NotImplementedYet(AppError):
    """Raised by deliberate scaffolding stubs.

    Production authentication, live extraction and policy evaluation are not
    implemented in this phase. They raise this instead of returning a fake
    success, so no caller can mistake a placeholder for working behaviour.
    """

    code = ErrorCode.NOT_IMPLEMENTED
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    default_message = "This capability is not implemented in the current scaffold."


class InternalError(AppError):
    code = ErrorCode.INTERNAL_ERROR
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "An unexpected error occurred."


def _envelope(
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": correlation_id_ctx.get() or "unavailable",
        }
    }


_HTTP_STATUS_TO_CODE = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.VALIDATION_ERROR,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.VALIDATION_ERROR,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    status.HTTP_422_UNPROCESSABLE_CONTENT: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every handler that can produce a client-visible error."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("application error", extra={"code": exc.code, "detail": exc.message})
        else:
            logger.info("request rejected", extra={"code": exc.code, "detail": exc.message})
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                ErrorCode.VALIDATION_ERROR, "The request could not be processed.", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be processed."
        )
        return JSONResponse(status_code=exc.status_code, content=_envelope(code, message))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the real cause server-side; never return it to the client.
        logger.exception("unhandled exception", extra={"exc_type": type(exc).__name__})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                ErrorCode.INTERNAL_ERROR,
                "An unexpected error occurred. Quote the request id when reporting it.",
            ),
        )
