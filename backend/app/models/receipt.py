"""Private receipt objects and extraction run history.

Storage rules encoded here:

* The bucket/key pair is opaque. No column exists for a public URL, and none
  should ever be added - receipt content is served only through the authorized
  endpoint in app/api/v1/routes/receipts.py.
* ``sha256`` is a real duplicate-detection signal (byte-identical files) and is
  indexed but NOT unique: two identical uploads are legitimately possible and are
  precisely the case the duplicate detector must surface.
* ``extraction_runs`` keeps every run. Re-extraction appends; it never overwrites
  a previous run, and it never overwrites a reviewer-corrected field value.
* Raw extracted text is intentionally NOT stored as a column. Until the data
  retention rules in docs/policy-assumptions.md are answered, only a hash of the
  raw payload is kept, so nothing sensitive accumulates by accident.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DerivationType, ExtractionStatus, StorageBackend
from app.db.base import (
    MONEY,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    in_enum,
    non_negative,
)


class Receipt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One stored file attached to a claim, plus its derived variants."""

    __tablename__ = "receipts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    storage_backend: Mapped[str] = enum_column(StorageBackend)
    # Opaque, server-generated object key. Never a client-supplied path.
    object_key: Mapped[str] = mapped_column(String(400), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Sniffed from the file's magic bytes, not taken from the upload header.
    detected_mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    declared_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    perceptual_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    derivation_type: Mapped[str] = enum_column(DerivationType)
    parent_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=True
    )

    extraction_status: Mapped[str] = enum_column(ExtractionStatus)
    # Set only when the extractor produced a quality signal. Never invented.
    overall_confidence: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("object_key"),
        in_enum("storage_backend", StorageBackend),
        in_enum("derivation_type", DerivationType),
        in_enum("extraction_status", ExtractionStatus),
        CheckConstraint("byte_size > 0", name="byte_size_positive"),
        CheckConstraint(
            "derivation_type = 'original' OR parent_receipt_id IS NOT NULL",
            name="derivation_requires_parent",
        ),
        non_negative("image_width"),
        non_negative("image_height"),
    )


class ExtractionRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One execution of an extraction provider against one receipt.

    Keeping runs as rows - rather than updating a single status column - is what
    makes "which model, which prompt version, when, with what outcome" answerable
    for a historical decision, and it is why re-extraction cannot silently erase
    the previous result.
    """

    __tablename__ = "extraction_runs"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = enum_column(ExtractionStatus)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hashes rather than payloads, until retention rules are approved.
    raw_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cached_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        in_enum("status", ExtractionStatus),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="finish_after_start",
        ),
        non_negative("latency_ms"),
    )
