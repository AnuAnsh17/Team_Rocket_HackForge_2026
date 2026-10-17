"""Receipt and extraction DTOs.

No DTO in this module ever carries a bucket name, object key, signed URL or any
other storage coordinate. The only way to obtain receipt content is the
authorized ``GET /api/v1/receipts/{receipt_id}/content`` endpoint, which performs
the same ownership and scope checks as the parent claim.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.core.enums import (
    DerivationType,
    ExpenseChannel,
    ExpenseStatus,
    ExtractionStatus,
    StorageBackend,
)
from app.schemas.common import ApiModel
from app.schemas.extraction import ReceiptExtractionData, ReceiptValidationResult


class ReceiptSummary(ApiModel):
    """Receipt reference embedded in an expense response."""

    id: uuid.UUID
    content_url: str = Field(
        ...,
        description=(
            "Relative URL of the authorized content endpoint. Not a storage path, not public, "
            "and not permanent: the endpoint re-checks authorization on every request."
        ),
    )
    extraction_status: ExtractionStatus
    detected_mime_type: str | None = None
    byte_size: int | None = Field(default=None, ge=0)
    derivation_type: DerivationType = DerivationType.ORIGINAL
    uploaded_at: datetime | None = None


class ExtractionRunSummary(ApiModel):
    """One historical extraction attempt. Past runs are never rewritten."""

    id: uuid.UUID
    provider: str
    model: str | None = None
    prompt_version: str | None = None
    status: ExtractionStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    structured_result: ReceiptExtractionData | None = None
    validation_result: ReceiptValidationResult | None = None
    is_cached_result: bool = Field(
        False,
        description=(
            "True when the result came from a verified cache rather than live inference. "
            "A cached result is never presented as live extraction."
        ),
    )


class ReceiptResponse(ApiModel):
    """Receipt metadata and extraction history."""

    id: uuid.UUID
    expense_id: uuid.UUID
    storage_backend: StorageBackend
    content_url: str
    original_filename: str | None = None
    detected_mime_type: str
    byte_size: int = Field(..., ge=0)
    sha256: str = Field(..., description="Byte hash. Used as an exact-duplicate signal.")
    perceptual_hash: str | None = Field(
        default=None,
        description=(
            "Image similarity signal, valid only after orientation normalisation. Present only "
            "when a perceptual hash was actually computed."
        ),
    )
    image_width: int | None = None
    image_height: int | None = None
    page_count: int | None = None
    derivation_type: DerivationType
    parent_receipt_id: uuid.UUID | None = None
    extraction_status: ExtractionStatus
    uploaded_at: datetime | None = None
    extraction_runs: list[ExtractionRunSummary] = Field(default_factory=list)


class ReceiptUploadResponse(ApiModel):
    """Receipt metadata and its initial persisted extraction state."""

    receipt: ReceiptResponse
    extraction_scheduled: bool = Field(
        ...,
        description="True when a persisted extraction run was queued for background processing.",
    )


class DraftExpenseResponse(ApiModel):
    """Minimal response needed to attach a receipt to an employee-owned draft."""

    id: uuid.UUID
    organization_id: uuid.UUID
    channel: ExpenseChannel
    status: ExpenseStatus
    version: int
    created_at: datetime
