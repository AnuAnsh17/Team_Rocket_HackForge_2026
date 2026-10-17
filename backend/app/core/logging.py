"""Structured logging with explicit redaction.

Two hard requirements drive this module:

1. Logs must never contain secrets, receipt bytes, extracted OCR text or
   personal data. Redaction is applied by a fixed denylist of field names rather
   than left to the discipline of whoever writes a log line.
2. Every log line in a request must carry the correlation id so an audit event
   and a log entry can be tied together.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Correlation id for the current request/task. Set by RequestContextMiddleware.
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Field names that are replaced before a record is emitted. Matching is
# case-insensitive and applied to the top level of any mapping passed via
# `extra`. Extend this list rather than adding one-off redaction call sites.
REDACTED_FIELDS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "api_key",
        "apikey",
        "service_role_key",
        "supabase_server_service_role_key",
        "extraction_api_key",
        "database_url",
        "dsn",
        "raw_text",
        "ocr_text",
        "extracted_text",
        "receipt_bytes",
        "file_content",
        "email",
        "phone",
        "national_id",
        "pan",
        "card_number",
    }
)

REDACTION_PLACEHOLDER = "[redacted]"


def redact(value: Any) -> Any:
    """Recursively replace denylisted keys with a placeholder."""
    if isinstance(value, dict):
        return {
            key: (REDACTION_PLACEHOLDER if str(key).lower() in REDACTED_FIELDS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def _make_formatter() -> logging.Formatter:
    """Return the redacting JSON formatter.

    python-json-logger is a hard dependency, so its import path is used directly: the
    version is pinned in pyproject.toml, which makes a multi-layout fallback speculative
    complexity rather than resilience.
    """
    from pythonjsonlogger.json import JsonFormatter

    class _RedactingJsonFormatter(JsonFormatter):
        def add_fields(
            self,
            log_record: dict[str, Any],
            record: logging.LogRecord,
            message_dict: dict[str, Any],
        ) -> None:
            super().add_fields(log_record, record, message_dict)
            request_id = correlation_id_ctx.get()
            if request_id:
                log_record["correlation_id"] = request_id
            for key in list(log_record.keys()):
                if key.lower() in REDACTED_FIELDS:
                    log_record[key] = REDACTION_PLACEHOLDER
            # `extra` values land on the record; move the safe ones through.
            for key in list(record.__dict__.keys()):
                if key.lower() in REDACTED_FIELDS:
                    log_record[key] = REDACTION_PLACEHOLDER

    return _RedactingJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def configure_logging() -> None:
    """Install the root handler. Safe to call more than once."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _make_formatter()
        if settings.log_json
        else logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
    )

    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    # SQLAlchemy echoes statements only when explicitly requested.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
