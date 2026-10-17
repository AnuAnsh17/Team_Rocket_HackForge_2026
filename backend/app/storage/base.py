"""The receipt storage boundary.

Two rules drive this module:

1. **Private by construction.** The interface exposes no way to obtain a public
   URL, because no implementation should be able to hand one out. Content is
   streamed only through an authorized application endpoint.
2. **Validation before persistence.** The declared upload header is recorded but
   never trusted; the real type is sniffed from the file's magic bytes, and a
   file that does not look like an accepted image or PDF is refused.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol, runtime_checkable

# MIME types the pipeline accepts today. Kept deliberately short and explicit.
ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "application/pdf",
    }
)

# Magic-byte signatures, written as explicit byte values so the intent is
# unambiguous and no escape sequence can be misread.
_JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])
_PNG_MAGIC = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
_PDF_MAGIC = b"%PDF-"
_RIFF_MAGIC = b"RIFF"
_WEBP_MAGIC = b"WEBP"
_FTYP_MAGIC = b"ftyp"

# HEIC/HEIF brands that appear in the ISO base media file type box.
_HEIC_BRANDS = (b"heic", b"heix", b"hevc", b"heim", b"heis")
_HEIF_BRANDS = (b"mif1", b"msf1")

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class StorageError(Exception):
    """Raised when an object cannot be stored or read."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """A persisted private object.

    ``object_key`` is server-generated and opaque. It is never returned to a
    client by any DTO.
    """

    object_key: str
    byte_size: int
    sha256: str
    detected_mime_type: str
    storage_backend: str


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    """Result of validating an upload before it is persisted."""

    accepted: bool
    detected_mime_type: str | None
    declared_mime_type: str | None
    reason_code: str | None = None
    reason: str | None = None


@runtime_checkable
class ReceiptStorage(Protocol):
    """Backend-agnostic private object storage.

    Note what is absent: there is no ``public_url`` and no ``signed_url`` member.
    Where a short-lived URL is genuinely needed, it is produced by the route
    after an authorization check, not exposed as a general storage capability.
    """

    backend_name: str

    def save(
        self,
        *,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        """Persist an object privately and return its coordinates."""
        ...

    def read(self, object_key: str) -> bytes:
        """Read an object. Authorization is the caller's responsibility."""
        ...

    def delete(self, object_key: str) -> None:
        """Delete an object. Used by demo reset and erasure workflows only."""
        ...

    def exists(self, object_key: str) -> bool: ...


def sniff_mime_type(head: bytes) -> str | None:
    """Determine a file's real type from its leading bytes.

    Returns ``None`` when the signature is not recognised, which callers must
    treat as a rejection rather than falling back to the declared type.
    """
    if head.startswith(_PDF_MAGIC):
        return "application/pdf"
    if head.startswith(_PNG_MAGIC):
        return "image/png"
    if head.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    # RIFF container: WEBP is "RIFF" + size + "WEBP".
    if head[:4] == _RIFF_MAGIC and head[8:12] == _WEBP_MAGIC:
        return "image/webp"
    # ISO base media container: the brand appears inside the "ftyp" box.
    if head[4:8] == _FTYP_MAGIC:
        brand = head[8:12]
        if brand in _HEIC_BRANDS:
            return "image/heic"
        if brand in _HEIF_BRANDS:
            return "image/heif"
    return None


def sanitise_filename(filename: str | None) -> str | None:
    """Reduce a client filename to a safe display label.

    The result is stored only as a label. Object keys are generated separately,
    so a hostile filename can never influence a storage path.
    """
    if not filename:
        return None
    leaf = PurePosixPath(filename.replace(chr(92), "/")).name
    cleaned = _SAFE_FILENAME.sub("_", leaf).strip("._-")
    return cleaned[:200] or None


def validate_upload(
    data: bytes,
    *,
    declared_mime_type: str | None,
    max_bytes: int,
) -> ValidationOutcome:
    """Validate an upload before it is stored.

    Checks, in order: non-empty, within the size cap, and a recognised magic-byte
    signature that is in the accepted set.
    """
    if not data:
        return ValidationOutcome(
            accepted=False,
            detected_mime_type=None,
            declared_mime_type=declared_mime_type,
            reason_code="EMPTY_FILE",
            reason="The uploaded file was empty.",
        )
    if len(data) > max_bytes:
        return ValidationOutcome(
            accepted=False,
            detected_mime_type=None,
            declared_mime_type=declared_mime_type,
            reason_code="FILE_TOO_LARGE",
            reason=f"The uploaded file exceeds the {max_bytes} byte limit.",
        )
    detected = sniff_mime_type(data[:32])
    if detected is None:
        return ValidationOutcome(
            accepted=False,
            detected_mime_type=None,
            declared_mime_type=declared_mime_type,
            reason_code="UNRECOGNISED_FILE_TYPE",
            reason=(
                "The file content is not a recognised JPEG, PNG, WEBP, HEIC or PDF. "
                "The declared content type is not trusted."
            ),
        )
    if detected not in ALLOWED_IMAGE_MIME_TYPES:
        return ValidationOutcome(
            accepted=False,
            detected_mime_type=detected,
            declared_mime_type=declared_mime_type,
            reason_code="UNSUPPORTED_FILE_TYPE",
            reason=f"{detected} is not an accepted receipt format.",
        )
    return ValidationOutcome(
        accepted=True,
        detected_mime_type=detected,
        declared_mime_type=declared_mime_type,
    )
