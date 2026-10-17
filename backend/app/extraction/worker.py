"""Bounded, database-backed extraction worker for persisted pending runs.

Job state lives in ``extraction_runs``. The worker holds no database transaction
while reading a receipt or calling a provider. A process restart marks stale,
previously-running jobs failed rather than silently charging for a duplicate call.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.writer import record_audit_event
from app.core.enums import AuditActorType, ExtractionStatus
from app.core.logging import get_logger
from app.extraction.base import ReceiptExtractor
from app.extraction.validation import has_partial_result, validate_extraction
from app.models.receipt import ExtractionRun, Receipt
from app.schemas.extraction import ReceiptExtractionData
from app.storage.base import ReceiptStorage, StorageError

logger = get_logger(__name__)


class ExtractionJobWorker:
    """Poll and process durable ``pending`` runs with a fixed per-process bound."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | Callable[[], Session],
        storage: ReceiptStorage,
        extractor: ReceiptExtractor,
        concurrency: int,
        max_attempts: int,
        timeout_seconds: int,
        retry_backoff_seconds: float,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage
        self._extractor = extractor
        self._concurrency = max(1, concurrency)
        self._max_attempts = max(1, max_attempts)
        self._timeout_seconds = timeout_seconds
        self._retry_backoff_seconds = retry_backoff_seconds
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self, stop: asyncio.Event) -> None:
        """Process pending runs until shutdown; finish active work before returning."""
        try:
            await asyncio.to_thread(self._fail_stale_runs)
        except Exception as exc:
            logger.error(
                "extraction worker could not recover stale runs",
                extra={"error_type": type(exc).__name__},
            )
        active: set[asyncio.Task[None]] = set()
        try:
            while not stop.is_set():
                while len(active) < self._concurrency and not stop.is_set():
                    try:
                        run_id = await asyncio.to_thread(self._claim_next)
                    except Exception as exc:
                        logger.error(
                            "extraction worker could not claim a run",
                            extra={"error_type": type(exc).__name__},
                        )
                        break
                    if run_id is None:
                        break
                    active.add(asyncio.create_task(asyncio.to_thread(self._process_run, run_id)))

                if active:
                    done, active = await asyncio.wait(
                        active,
                        timeout=self._poll_interval_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        try:
                            task.result()
                        except Exception as exc:
                            logger.error(
                                "extraction worker task ended unexpectedly",
                                extra={"error_type": type(exc).__name__},
                            )
                else:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), timeout=self._poll_interval_seconds)
        finally:
            # asyncio cannot cancel a running to_thread call. Drain those calls before
            # lifespan cleanup closes the shared HTTP client or IndicOCR subprocess.
            if active:
                await asyncio.gather(*active, return_exceptions=True)

    def _claim_next(self) -> uuid.UUID | None:
        with self._sessions() as session, session.begin():
            run = session.execute(
                select(ExtractionRun)
                .where(ExtractionRun.status == ExtractionStatus.PENDING.value)
                .order_by(ExtractionRun.created_at, ExtractionRun.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None
            run.status = ExtractionStatus.RUNNING.value
            run.started_at = datetime.now(UTC)
            run.finished_at = None
            return run.id

    def _process_run(self, run_id: uuid.UUID) -> None:
        try:
            with self._sessions() as session:
                run = session.get(ExtractionRun, run_id)
                if run is None:
                    return
                receipt = session.get(Receipt, run.receipt_id)
                if receipt is None:
                    self._persist_failure(run_id, "RECEIPT_NOT_FOUND", "Receipt is unavailable.")
                    return
                object_key = receipt.object_key
                content_type = receipt.detected_mime_type
                receipt_id = receipt.id
            data = self._storage.read(object_key)
            result = self._extractor.extract(
                receipt_id=receipt_id,
                data=data,
                content_type=content_type,
            )
            structured: ReceiptExtractionData | None = None
            validation = None
            status = result.status
            error_code = result.error_code
            error_message = result.error_message
            if result.structured_data is not None:
                structured = ReceiptExtractionData.model_validate(
                    result.structured_data.model_dump(mode="python")
                )
                validation = validate_extraction(result.structured_data)
                if status in {ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL}:
                    status = (
                        ExtractionStatus.PARTIAL
                        if has_partial_result(result.structured_data, validation)
                        else ExtractionStatus.SUCCESS
                    )
            elif status is ExtractionStatus.SUCCESS:
                status = ExtractionStatus.PARTIAL
                error_code = "STRUCTURED_RESULT_MISSING"
                error_message = "The provider returned no structured receipt fields."

            now = datetime.now(UTC)
            with self._sessions() as session, session.begin():
                run = session.get(ExtractionRun, run_id)
                if run is None:
                    return
                receipt = session.get(Receipt, run.receipt_id)
                if receipt is None:
                    return
                run.provider = result.provider
                run.model = result.model
                run.prompt_version = result.prompt_version
                run.status = status.value
                run.finished_at = now
                run.latency_ms = result.latency_ms
                run.raw_text_sha256 = (
                    hashlib.sha256(result.raw_text.encode("utf-8")).hexdigest()
                    if result.raw_text is not None
                    else None
                )
                run.raw_payload_sha256 = result.raw_payload_sha256
                run.error_code = error_code
                run.error_message = error_message
                run.attempt_count = max(run.attempt_count, result.attempt_count)
                run.structured_result = (
                    structured.model_dump(mode="json") if structured is not None else None
                )
                run.validation_result = (
                    validation.model_dump(mode="json") if validation is not None else None
                )
                receipt.extraction_status = status.value
                record_audit_event(
                    session,
                    action="receipt.extraction_completed",
                    entity_type="extraction_run",
                    entity_id=run.id,
                    organization_id=receipt.organization_id,
                    actor_type=AuditActorType.SYSTEM,
                    after={
                        "receipt_id": str(receipt.id),
                        "status": status.value,
                        "provider": run.provider,
                        "schema_version": "1.0" if structured is not None else None,
                    },
                )
        except StorageError:
            self._persist_failure(
                run_id,
                "RECEIPT_STORAGE_UNAVAILABLE",
                "The stored receipt could not be read for extraction.",
            )
        except Exception as exc:
            logger.error(
                "receipt extraction worker failed",
                extra={"run_id": str(run_id), "error_type": type(exc).__name__},
            )
            self._persist_failure(
                run_id,
                "EXTRACTION_WORKER_FAILED",
                "The extraction job could not be completed.",
            )

    def _persist_failure(self, run_id: uuid.UUID, code: str, message: str) -> None:
        now = datetime.now(UTC)
        try:
            with self._sessions() as session, session.begin():
                run = session.get(ExtractionRun, run_id)
                if run is None:
                    return
                receipt = session.get(Receipt, run.receipt_id)
                run.status = ExtractionStatus.FAILED.value
                run.finished_at = now
                run.error_code = code
                run.error_message = message
                if receipt is not None:
                    receipt.extraction_status = ExtractionStatus.FAILED.value
                    record_audit_event(
                        session,
                        action="receipt.extraction_failed",
                        entity_type="extraction_run",
                        entity_id=run.id,
                        organization_id=receipt.organization_id,
                        actor_type=AuditActorType.SYSTEM,
                        after={"receipt_id": str(receipt.id), "status": "failed", "code": code},
                    )
        except Exception as exc:
            logger.error(
                "extraction failure could not be persisted",
                extra={"run_id": str(run_id), "error_type": type(exc).__name__},
            )

    def _fail_stale_runs(self) -> None:
        retry_window = sum(
            self._retry_backoff_seconds * (2**attempt)
            for attempt in range(max(0, self._max_attempts - 1))
        )
        stale_before = datetime.now(UTC) - timedelta(
            seconds=self._timeout_seconds * self._max_attempts + retry_window + 60
        )
        with self._sessions() as session, session.begin():
            runs = session.execute(
                select(ExtractionRun).where(
                    ExtractionRun.status == ExtractionStatus.RUNNING.value,
                    ExtractionRun.started_at < stale_before,
                )
            ).scalars()
            for run in runs:
                receipt = session.get(Receipt, run.receipt_id)
                run.status = ExtractionStatus.FAILED.value
                run.finished_at = datetime.now(UTC)
                run.error_code = "EXTRACTION_WORKER_RESTARTED"
                run.error_message = "The prior extraction worker stopped before completion."
                if receipt is not None:
                    receipt.extraction_status = ExtractionStatus.FAILED.value
