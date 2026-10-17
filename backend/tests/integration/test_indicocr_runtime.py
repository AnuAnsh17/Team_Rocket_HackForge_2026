from __future__ import annotations

import os
import struct
import uuid
import zlib

import pytest
from app.api.deps import get_receipt_extractor, get_receipt_storage
from app.core.config import Settings
from app.core.enums import ExtractionStatus
from app.extraction.factory import build_receipt_extractor
from app.models.receipt import ExtractionRun, Receipt
from app.storage.local import LocalPrivateReceiptStorage
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _synthetic_png() -> bytes:
    width, height = 96, 64
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for x in range(width):
            # Synthetic black bars on white paper; no real receipt data or text.
            ink = x in range(12, 84) and y in {14, 15, 28, 29, 42, 43}
            pixels.extend((0, 0, 0) if ink else (255, 255, 255))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(pixels)))
        + _chunk(b"IEND", b"")
    )


@pytest.mark.skipif(
    os.environ.get("RUN_INDICOCR_INTEGRATION") != "1",
    reason="Set RUN_INDICOCR_INTEGRATION=1 and the isolated runtime paths to run real inference.",
)
def test_cached_indicocr_upload_to_persistence(
    client: TestClient,
    employee_headers: dict[str, str],
    db: Session,
    tmp_path,
) -> None:
    config = Settings(
        _env_file=None,
        APP_ENV="development",
        EXTRACTION_PROVIDER="local_ocr",
        EXTRACTION_MODEL=os.environ["EXTRACTION_MODEL"],
        EXTRACTION_PYTHON_EXECUTABLE=os.environ["EXTRACTION_PYTHON_EXECUTABLE"],
        EXTRACTION_TIMEOUT_SECONDS=90,
    )
    extractor = build_receipt_extractor(config)
    client.app.dependency_overrides[get_receipt_extractor] = lambda: extractor
    client.app.dependency_overrides[get_receipt_storage] = lambda: LocalPrivateReceiptStorage(
        root=tmp_path
    )
    try:
        draft = client.post(
            "/api/v1/expenses",
            headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
            json={"channel": "web"},
        )
        assert draft.status_code == 201, draft.text
        upload = client.post(
            f"/api/v1/expenses/{draft.json()['id']}/receipts",
            headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
            files={"file": ("synthetic.png", _synthetic_png(), "image/png")},
        )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        receipt_id = uuid.UUID(body["receipt"]["id"])
        assert body["receipt"]["extraction_status"] == ExtractionStatus.SUCCESS.value
        assert body["receipt"]["extraction_runs"][0]["provider"] == "indicocr"
        assert body["receipt"]["extraction_runs"][0]["error_code"] is None
        assert "raw_text" not in upload.text
        receipt = db.get(Receipt, receipt_id)
        assert receipt is not None
        run = db.execute(
            select(ExtractionRun).where(ExtractionRun.receipt_id == receipt_id)
        ).scalar_one()
        assert run.raw_text_sha256 and run.raw_payload_sha256
        assert not hasattr(run, "raw_text")
        content = client.get(body["receipt"]["content_url"], headers=employee_headers)
        assert content.status_code == 200 and content.content == _synthetic_png()
    finally:
        close = getattr(extractor, "close", None)
        if close is not None:
            close()
        client.app.dependency_overrides.pop(get_receipt_extractor, None)
        client.app.dependency_overrides.pop(get_receipt_storage, None)
