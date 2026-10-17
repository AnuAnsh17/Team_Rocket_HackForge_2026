"""Authorized receipt upload, metadata and private content routes."""

from __future__ import annotations

import hashlib
import uuid
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
    get_settings_dep,
    require,
)
from app.audit.writer import record_audit_event
from app.core.config import Settings
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
from app.extraction.base import ReceiptExtractor
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
_EXTRACTION_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}


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


def _queue_receipt_extraction(
    *,
    request: Request,
    session: Session,
    storage: ReceiptStorage,
    extractor: ReceiptExtractor,
    config: Settings,
    expense: Expense,
    actor: Actor,
    data: bytes,
    detected_mime_type: str,
    declared_mime_type: str | None,
    filename: str | None,
    idempotency_key: str,
    idempotency_path: str,
    batch_index: int | None = None,
) -> ReceiptUploadResponse:
    """Persist one validated receipt and pending run in the request transaction."""
    digest = hashlib.sha256(data).hexdigest()
    idem = idempotency_service.begin(
        session,
        actor_user_id=uuid.UUID(actor.user_id),
        key=idempotency_key,
        method="POST",
        path=idempotency_path,
        payload={
            "expense_id": str(expense.id),
            "sha256": digest,
            "declared_mime_type": declared_mime_type,
            "filename": filename,
        },
    )
    if idem is not None and idem.response_body is not None:
        return ReceiptUploadResponse.model_validate(idem.response_body)

    stored = storage.save(
        organization_id=expense.organization_id,
        expense_id=expense.id,
        data=data,
        content_type=detected_mime_type,
    )
    callbacks = getattr(request.state, "rollback_callbacks", None)
    if callbacks is None:
        callbacks = []
        request.state.rollback_callbacks = callbacks

    def cleanup_stored_object() -> None:
        try:
            storage.delete(stored.object_key)
        except StorageError:
            logger.error(
                "could not remove receipt object after failed database transaction",
                extra={"error_type": "StorageError"},
            )

    callbacks.append(cleanup_stored_object)
    receipt = Receipt(
        id=uuid.uuid4(),
        organization_id=expense.organization_id,
        expense_id=expense.id,
        storage_backend=stored.storage_backend,
        object_key=stored.object_key,
        original_filename=filename,
        detected_mime_type=detected_mime_type,
        declared_mime_type=declared_mime_type,
        byte_size=stored.byte_size,
        sha256=stored.sha256,
        derivation_type=DerivationType.ORIGINAL.value,
        parent_receipt_id=None,
        extraction_status=ExtractionStatus.PENDING.value,
        uploaded_by_user_id=uuid.UUID(actor.user_id),
    )
    session.add(receipt)
    session.flush()

    provider = getattr(extractor, "provider_name", "unavailable")
    model = (
        config.opencode_go_model
        if provider == "opencode_go"
        else ("bodhan-ai/indic-ocr" if provider == "indicocr" else None)
    )
    run = ExtractionRun(
        receipt_id=receipt.id,
        provider=provider,
        model=model,
        prompt_version="receipt-extraction-v1" if provider == "opencode_go" else None,
        status=ExtractionStatus.PENDING.value,
        attempt_count=0,
        created_by_user_id=uuid.UUID(actor.user_id),
    )
    session.add(run)
    session.flush()

    response = ReceiptUploadResponse(
        receipt=_receipt_response(session, receipt),
        extraction_scheduled=True,
    )
    idempotency_service.complete(
        idem,
        status_code=status.HTTP_201_CREATED,
        body=response.model_dump(mode="json"),
    )
    audit_after: dict[str, object] = {
        "expense_id": str(expense.id),
        "sha256": receipt.sha256,
        "byte_size": receipt.byte_size,
        "detected_mime_type": receipt.detected_mime_type,
        "extraction_status": receipt.extraction_status,
        "extraction_run_id": str(run.id),
    }
    if batch_index is not None:
        audit_after["batch_index"] = batch_index
    record_audit_event(
        session,
        action="receipt.uploaded_extraction_queued",
        entity_type="receipt",
        entity_id=receipt.id,
        organization_id=expense.organization_id,
        actor_user_id=uuid.UUID(actor.user_id),
        actor_type=actor.actor_type,
        after=audit_after,
    )
    return response


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
    summary="Upload a private receipt and queue extraction",
    description=(
        "Uploads one original receipt to a caller-owned draft, validates its content and "
        "persists a pending extraction run for background processing. Exact duplicate files "
        "remain separate receipts and are linked only by their SHA-256 signal."
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
    config: Settings = Depends(get_settings_dep),
) -> ReceiptUploadResponse:
    expense = require_expense_write(session, actor, expense_id)
    if not is_own_claim(actor, expense):
        raise Forbidden("Receipt uploads are limited to the caller's own expense drafts.")
    if expense.status not in {"draft", "needs_info"}:
        raise ValidationFailed(
            "Receipts may only be added to a draft or needs-information expense."
        )

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
    if checked.detected_mime_type not in _EXTRACTION_MEDIA_TYPES:
        raise UnsupportedMediaType(
            "Receipt extraction currently accepts JPEG, PNG and WebP images only."
        )

    filename = sanitise_filename(file.filename)
    return _queue_receipt_extraction(
        request=request,
        session=session,
        storage=storage,
        extractor=extractor,
        config=config,
        expense=expense,
        actor=actor,
        data=data,
        detected_mime_type=checked.detected_mime_type,
        declared_mime_type=file.content_type,
        filename=filename,
        idempotency_key=idempotency_key,
        idempotency_path=request.url.path,
    )


@router.post(
    "/expenses/{expense_id}/receipts/batch",
    response_model=list[ReceiptUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a batch of up to 20 independent receipts",
    description=(
        "Stores each validated receipt and creates its own persisted pending extraction run. "
        "A batch is limited to 20 files; each receipt is processed independently."
    ),
)
def upload_receipt_batch(
    expense_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., max_length=20),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(require(Permission.RECEIPT_UPLOAD_OWN)),
    session: Session = Depends(get_session),
    storage: ReceiptStorage = Depends(get_receipt_storage),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
    config: Settings = Depends(get_settings_dep),
) -> list[ReceiptUploadResponse]:
    """Use a distinct deterministic idempotency scope per file in the request."""
    if not files or len(files) > 20:
        raise ValidationFailed("A receipt batch must contain between 1 and 20 files.")
    expense = require_expense_write(session, actor, expense_id)
    if not is_own_claim(actor, expense):
        raise Forbidden("Receipt uploads are limited to the caller's own expense drafts.")
    if expense.status not in {"draft", "needs_info"}:
        raise ValidationFailed(
            "Receipts may only be added to a draft or needs-information expense."
        )
    outputs: list[ReceiptUploadResponse] = []
    for index, file in enumerate(files):
        data = file.file.read(request.app.state.max_receipt_bytes + 1)
        checked = validate_upload(
            data,
            declared_mime_type=file.content_type,
            max_bytes=request.app.state.max_receipt_bytes,
        )
        if not checked.accepted or checked.detected_mime_type is None:
            if checked.reason_code == "FILE_TOO_LARGE":
                raise PayloadTooLarge(f"File {index + 1}: {checked.reason}")
            if checked.reason_code == "EMPTY_FILE":
                raise ValidationFailed(f"File {index + 1}: {checked.reason}")
            raise UnsupportedMediaType(f"File {index + 1}: {checked.reason}")
        if checked.detected_mime_type not in _EXTRACTION_MEDIA_TYPES:
            raise UnsupportedMediaType(
                f"File {index + 1}: receipt extraction accepts JPEG, PNG and WebP images only."
            )
        filename = sanitise_filename(file.filename)
        per_file_key = hashlib.sha256(f"{idempotency_key}:{index}".encode()).hexdigest()
        outputs.append(
            _queue_receipt_extraction(
                request=request,
                session=session,
                storage=storage,
                extractor=extractor,
                config=config,
                expense=expense,
                actor=actor,
                data=data,
                detected_mime_type=checked.detected_mime_type,
                declared_mime_type=file.content_type,
                filename=filename,
                idempotency_key=per_file_key,
                idempotency_path=f"{request.url.path}:{index}",
                batch_index=index,
            )
        )
    return outputs


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
    "/expenses/{expense_id}/receipts",
    response_model=list[ReceiptResponse],
    summary="List authorized receipts and extraction runs for an expense",
)
def list_expense_receipts(
    expense_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> list[ReceiptResponse]:
    expense = require_expense_read(session, actor, expense_id)
    actor.require(
        Permission.RECEIPT_READ_OWN
        if is_own_claim(actor, expense)
        else Permission.RECEIPT_READ_SCOPED
    )
    receipts = (
        session.execute(
            select(Receipt)
            .where(Receipt.expense_id == expense.id)
            .order_by(Receipt.created_at, Receipt.id)
        )
        .scalars()
        .all()
    )
    return [_receipt_response(session, receipt) for receipt in receipts]


@router.post(
    "/receipts/{receipt_id}/extractions",
    response_model=ReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry extraction for an authorized receipt",
    description=(
        "Appends a new extraction run for a receipt owned by the caller. Previous run "
        "results are preserved and never overwritten."
    ),
)
def retry_receipt_extraction(
    receipt_id: uuid.UUID,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(require(Permission.RECEIPT_REEXTRACT_OWN)),
    session: Session = Depends(get_session),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
    config: Settings = Depends(get_settings_dep),
) -> ReceiptResponse:
    receipt, expense = _read_receipt_for_actor(session, actor, receipt_id)
    if not is_own_claim(actor, expense):
        raise Forbidden("Extraction retries are limited to the caller's own receipts.")
    idem = idempotency_service.begin(
        session,
        actor_user_id=uuid.UUID(actor.user_id),
        key=idempotency_key,
        method="POST",
        path=request.url.path,
        payload={"receipt_id": str(receipt.id)},
    )
    if idem is not None and idem.response_body is not None:
        return ReceiptResponse.model_validate(idem.response_body)
    active = session.execute(
        select(ExtractionRun.id).where(
            ExtractionRun.receipt_id == receipt.id,
            ExtractionRun.status.in_(
                (ExtractionStatus.PENDING.value, ExtractionStatus.RUNNING.value)
            ),
        )
    ).scalar_one_or_none()
    if active is not None:
        raise ValidationFailed("An extraction is already pending or running for this receipt.")
    provider = getattr(extractor, "provider_name", "unavailable")
    run = ExtractionRun(
        receipt_id=receipt.id,
        provider=provider,
        model=config.opencode_go_model
        if provider == "opencode_go"
        else ("bodhan-ai/indic-ocr" if provider == "indicocr" else None),
        prompt_version="receipt-extraction-v1" if provider == "opencode_go" else None,
        status=ExtractionStatus.PENDING.value,
        attempt_count=0,
        created_by_user_id=uuid.UUID(actor.user_id),
    )
    session.add(run)
    receipt.extraction_status = ExtractionStatus.PENDING.value
    session.flush()
    response = _receipt_response(session, receipt)
    idempotency_service.complete(idem, status_code=202, body=response.model_dump(mode="json"))
    record_audit_event(
        session,
        action="receipt.extraction_retry_queued",
        entity_type="extraction_run",
        entity_id=run.id,
        organization_id=expense.organization_id,
        actor_user_id=uuid.UUID(actor.user_id),
        actor_type=actor.actor_type,
        after={"receipt_id": str(receipt.id), "provider": provider},
    )
    return response


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
