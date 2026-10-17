"""Authorized receipt upload, metadata and private content routes."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_actor,
    get_receipt_extractor,
    get_receipt_storage,
    get_session,
    require,
)
from app.audit.writer import record_audit_event
from app.core.enums import DerivationType, ExtractionStatus, StorageBackend
from app.core.errors import (
    Forbidden,
    NotFound,
    PayloadTooLarge,
    UnsupportedMediaType,
    ValidationFailed,
)
from app.core.logging import get_logger
from app.core.permissions import Permission
from app.core.security import Actor
from app.extraction.base import ExtractionResult, ReceiptExtractor
from app.models.expense import Expense
from app.models.receipt import ExtractionRun, Receipt
from app.schemas.receipt import (
    ExtractionRunSummary,
    ReceiptResponse,
    ReceiptUploadResponse,
)
from app.services import idempotency_service
from app.services.scope_service import is_own_claim, require_expense_read, require_expense_write
from app.storage.base import ReceiptStorage, StorageError, sanitise_filename, validate_upload

logger = get_logger(__name__)
router = APIRouter(tags=["receipts"])


def _receipt_response(session: Session, receipt: Receipt) -> ReceiptResponse:
    runs = (
        session.execute(
            select(ExtractionRun)
            .where(ExtractionRun.receipt_id == receipt.id)
            .order_by(ExtractionRun.created_at.asc())
        )
        .scalars()
        .all()
    )
    return ReceiptResponse(
        id=receipt.id,
        expense_id=receipt.expense_id,
        storage_backend=StorageBackend(receipt.storage_backend),
        content_url=f"/api/v1/receipts/{receipt.id}/content",
        original_filename=receipt.original_filename,
        detected_mime_type=receipt.detected_mime_type,
        byte_size=receipt.byte_size,
        sha256=receipt.sha256,
        perceptual_hash=receipt.perceptual_hash,
        image_width=receipt.image_width,
        image_height=receipt.image_height,
        page_count=receipt.page_count,
        derivation_type=DerivationType(receipt.derivation_type),
        parent_receipt_id=receipt.parent_receipt_id,
        extraction_status=ExtractionStatus(receipt.extraction_status),
        uploaded_at=receipt.created_at,
        extraction_runs=[ExtractionRunSummary.model_validate(run) for run in runs],
    )


def _read_receipt_for_actor(
    session: Session, actor: Actor, receipt_id: uuid.UUID
) -> tuple[Receipt, Expense]:
    receipt = session.get(Receipt, receipt_id)
    if receipt is None:
        raise NotFound("That receipt was not found.")
    expense = require_expense_read(session, actor, receipt.expense_id)
    actor.require(
        Permission.RECEIPT_READ_OWN
        if is_own_claim(actor, expense)
        else Permission.RECEIPT_READ_SCOPED
    )
    return receipt, expense


@router.post(
    "/expenses/{expense_id}/receipts",
    response_model=ReceiptUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "description": "The upload exceeds RECEIPT_MAX_UPLOAD_BYTES."
        },
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "The file content is not an accepted receipt format."
        },
    },
    summary="Upload and OCR a private receipt",
    description=(
        "Uploads one original receipt to a caller-owned draft, validates its content and runs "
        "the configured OCR provider synchronously. Exact duplicate files remain separate "
        "receipts and are linked only by their SHA-256 signal."
    ),
)
def upload_receipt(
    expense_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(require(Permission.RECEIPT_UPLOAD_OWN)),
    session: Session = Depends(get_session),
    storage: ReceiptStorage = Depends(get_receipt_storage),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
) -> ReceiptUploadResponse:
    expense = require_expense_write(session, actor, expense_id)
    if not is_own_claim(actor, expense):
        raise Forbidden("Receipt uploads are limited to the caller's own expense drafts.")
    if expense.status != "draft":
        raise ValidationFailed("Receipts may only be added to a draft expense.")

    data = file.file.read(request.app.state.max_receipt_bytes + 1)
    checked = validate_upload(
        data,
        declared_mime_type=file.content_type,
        max_bytes=request.app.state.max_receipt_bytes,
    )
    if not checked.accepted or checked.detected_mime_type is None:
        if checked.reason_code == "FILE_TOO_LARGE":
            raise PayloadTooLarge(checked.reason)
        if checked.reason_code == "EMPTY_FILE":
            raise ValidationFailed(checked.reason)
        raise UnsupportedMediaType(checked.reason)

    digest = hashlib.sha256(data).hexdigest()
    filename = sanitise_filename(file.filename)
    path = request.url.path
    idem = idempotency_service.begin(
        session,
        actor_user_id=uuid.UUID(actor.user_id),
        key=idempotency_key,
        method="POST",
        path=path,
        payload={
            "expense_id": str(expense_id),
            "sha256": digest,
            "declared_mime_type": file.content_type,
            "filename": filename,
        },
    )
    if idem is not None and idem.response_body is not None:
        return ReceiptUploadResponse.model_validate(idem.response_body)

    stored = storage.save(
        organization_id=expense.organization_id,
        expense_id=expense.id,
        data=data,
        content_type=checked.detected_mime_type,
    )
    callbacks = getattr(request.state, "rollback_callbacks", None)
    if callbacks is None:
        callbacks = []
        request.state.rollback_callbacks = callbacks

    cleanup_attempted = False

    def cleanup_stored_object() -> None:
        nonlocal cleanup_attempted
        if cleanup_attempted:
            return
        cleanup_attempted = True
        try:
            storage.delete(stored.object_key)
        except StorageError:
            logger.error(
                "could not remove receipt object after failed database transaction",
                extra={"error_type": "StorageError"},
            )

    callbacks.append(cleanup_stored_object)
    try:
        receipt = Receipt(
            id=uuid.uuid4(),
            organization_id=expense.organization_id,
            expense_id=expense.id,
            storage_backend=stored.storage_backend,
            object_key=stored.object_key,
            original_filename=filename,
            detected_mime_type=checked.detected_mime_type,
            declared_mime_type=file.content_type,
            byte_size=stored.byte_size,
            sha256=stored.sha256,
            derivation_type=DerivationType.ORIGINAL.value,
            parent_receipt_id=None,
            extraction_status=ExtractionStatus.RUNNING.value,
            uploaded_by_user_id=uuid.UUID(actor.user_id),
        )
        session.add(receipt)
        session.flush()

        started_at = datetime.now(UTC)
        try:
            result = extractor.extract(
                receipt_id=receipt.id,
                data=data,
                content_type=checked.detected_mime_type,
            )
        except Exception as exc:
            # Do not log provider exception text: OCR diagnostics can contain input data.
            logger.error(
                "receipt OCR provider raised",
                extra={"receipt_id": str(receipt.id), "error_type": type(exc).__name__},
            )
            result = ExtractionResult(
                status=ExtractionStatus.FAILED,
                provider=getattr(extractor, "provider_name", "unknown"),
                error_code="OCR_PROCESSING_FAILED",
                error_message="Receipt OCR could not be completed.",
            )
        finished_at = datetime.now(UTC)
        raw_text_sha256 = (
            hashlib.sha256(result.raw_text.encode("utf-8")).hexdigest()
            if result.raw_text is not None
            else None
        )
        run = ExtractionRun(
            receipt_id=receipt.id,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            status=result.status.value,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=result.latency_ms,
            raw_text_sha256=raw_text_sha256,
            raw_payload_sha256=result.raw_payload_sha256,
            error_code=result.error_code,
            error_message=result.error_message,
            is_cached_result=result.is_cached_result,
            created_by_user_id=uuid.UUID(actor.user_id),
        )
        session.add(run)
        receipt.extraction_status = result.status.value
        session.flush()

        response = ReceiptUploadResponse(
            receipt=_receipt_response(session, receipt),
            extraction_scheduled=False,
        )
        idempotency_service.complete(
            idem,
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
        )
        record_audit_event(
            session,
            action="receipt.uploaded_and_ocr_processed",
            entity_type="receipt",
            entity_id=receipt.id,
            organization_id=expense.organization_id,
            actor_user_id=uuid.UUID(actor.user_id),
            actor_type=actor.actor_type,
            after={
                "expense_id": str(expense.id),
                "sha256": receipt.sha256,
                "byte_size": receipt.byte_size,
                "detected_mime_type": receipt.detected_mime_type,
                "extraction_status": receipt.extraction_status,
            },
        )
        return response
    except Exception:
        # The get_session dependency rolls back and invokes the registered
        # cleanup, including when its final commit fails after this route returns.
        raise


@router.get(
    "/receipts/{receipt_id}",
    response_model=ReceiptResponse,
    summary="Read authorized receipt metadata and OCR status",
)
def read_receipt(
    receipt_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ReceiptResponse:
    receipt, _ = _read_receipt_for_actor(session, actor, receipt_id)
    return _receipt_response(session, receipt)


@router.get(
    "/receipts/{receipt_id}/content",
    response_class=Response,
    summary="Stream authorized private receipt content",
    description="The endpoint rechecks receipt and expense authorization on every request.",
)
def read_receipt_content(
    receipt_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
    storage: ReceiptStorage = Depends(get_receipt_storage),
) -> Response:
    receipt, _ = _read_receipt_for_actor(session, actor, receipt_id)
    try:
        data = storage.read(receipt.object_key)
    except StorageError as exc:
        raise NotFound("That receipt content was not found.") from exc
    disposition = f'attachment; filename="{quote(receipt.original_filename or "receipt")}"'
    return Response(
        content=data,
        media_type=receipt.detected_mime_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
