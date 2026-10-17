"""Receipt upload validation and private storage behaviour."""

from __future__ import annotations

import uuid

import pytest
from app.storage.base import (
    ALLOWED_IMAGE_MIME_TYPES,
    StorageError,
    sanitise_filename,
    sniff_mime_type,
    validate_upload,
)
from app.storage.local import LocalPrivateReceiptStorage

pytestmark = pytest.mark.unit

PNG_BYTES = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A]) + b"\x00" * 32
JPEG_BYTES = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 32
PDF_BYTES = b"%PDF-1.7\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + (36).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 24


class TestMimeSniffing:
    def test_recognises_png_jpeg_pdf_webp(self) -> None:
        assert sniff_mime_type(PNG_BYTES) == "image/png"
        assert sniff_mime_type(JPEG_BYTES) == "image/jpeg"
        assert sniff_mime_type(PDF_BYTES) == "application/pdf"
        assert sniff_mime_type(WEBP_BYTES) == "image/webp"

    def test_recognises_heic_brand(self) -> None:
        heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16
        assert sniff_mime_type(heic) == "image/heic"

    def test_unknown_content_is_not_guessed(self) -> None:
        assert sniff_mime_type(b"this is not an image") is None
        assert sniff_mime_type(b"") is None


class TestUploadValidation:
    def test_valid_png_is_accepted(self) -> None:
        outcome = validate_upload(PNG_BYTES, declared_mime_type="image/png", max_bytes=1024)
        assert outcome.accepted is True
        assert outcome.detected_mime_type == "image/png"

    def test_declared_type_is_never_trusted(self) -> None:
        """A text file claiming to be a JPEG must be rejected."""
        outcome = validate_upload(
            b"#!/bin/sh\nrm -rf /", declared_mime_type="image/jpeg", max_bytes=1024
        )
        assert outcome.accepted is False
        assert outcome.reason_code == "UNRECOGNISED_FILE_TYPE"
        assert outcome.declared_mime_type == "image/jpeg"

    def test_empty_file_is_rejected(self) -> None:
        outcome = validate_upload(b"", declared_mime_type="image/png", max_bytes=1024)
        assert outcome.accepted is False
        assert outcome.reason_code == "EMPTY_FILE"

    def test_oversized_file_is_rejected(self) -> None:
        outcome = validate_upload(PNG_BYTES, declared_mime_type="image/png", max_bytes=4)
        assert outcome.accepted is False
        assert outcome.reason_code == "FILE_TOO_LARGE"

    def test_allowed_set_contains_no_executable_format(self) -> None:
        forbidden = {"application/x-msdownload", "application/zip", "text/x-shellscript"}
        assert not (ALLOWED_IMAGE_MIME_TYPES & forbidden)


class TestFilenameSanitisation:
    def test_path_components_are_stripped(self) -> None:
        assert sanitise_filename("/etc/passwd") == "passwd"
        assert sanitise_filename("C:/Users/x/../../secret.png") == "secret.png"

    def test_traversal_only_name_is_rejected(self) -> None:
        assert sanitise_filename("../..") is None
        assert sanitise_filename("   ") is None
        assert sanitise_filename(None) is None

    def test_unsafe_characters_are_replaced(self) -> None:
        assert sanitise_filename('a";rm -rf;.jpg') == "a_rm_-rf_.jpg"


class TestLocalPrivateStorage:
    @pytest.fixture
    def storage(self, tmp_path) -> LocalPrivateReceiptStorage:
        return LocalPrivateReceiptStorage(root=tmp_path / "receipts")

    def test_save_and_read_round_trip(self, storage) -> None:
        organization_id, expense_id = uuid.uuid4(), uuid.uuid4()
        stored = storage.save(
            organization_id=organization_id,
            expense_id=expense_id,
            data=PNG_BYTES,
            content_type="image/png",
        )
        assert stored.byte_size == len(PNG_BYTES)
        assert storage.read(stored.object_key) == PNG_BYTES
        assert stored.object_key.startswith(f"{organization_id}/{expense_id}/")

    def test_object_key_refuses_path_traversal(self, storage) -> None:
        for hostile in ("../../etc/passwd", "/etc/passwd", "a/../../b"):
            with pytest.raises(StorageError):
                storage.read(hostile)

    def test_delete_expense_objects_removes_only_that_claim(self, storage) -> None:
        org = uuid.uuid4()
        keep, drop = uuid.uuid4(), uuid.uuid4()
        kept = storage.save(
            organization_id=org, expense_id=keep, data=PNG_BYTES, content_type="image/png"
        )
        storage.save(organization_id=org, expense_id=drop, data=PNG_BYTES, content_type="image/png")
        removed = storage.delete_expense_objects(org, drop)
        assert removed == 1
        assert storage.exists(kept.object_key) is True
