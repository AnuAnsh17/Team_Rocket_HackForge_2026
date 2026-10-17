from __future__ import annotations

import os
import struct
import uuid
import zlib

import pytest
from app.api.deps import get_receipt_extractor, get_receipt_storage, get_settings_dep
from app.core.config import Settings
from app.core.enums import ExtractionStatus
from app.extraction.factory import build_receipt_extractor
from app.extraction.worker import ExtractionJobWorker
from app.models.receipt import ExtractionRun
from app.storage.local import LocalPrivateReceiptStorage
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _png() -> bytes:
    glyphs = {
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
        "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
        "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
        "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
        "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
        "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
        "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
        "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
        "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
        "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
        "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
        "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
        ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
        "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
        " ": ("00000",) * 7,
    }
    lines = ("PROOF CAFE", "RECEIPT", "DATE 2026-10-18", "COFFEE 1 3.50", "TAX 0.35", "TOTAL 3.85")
    scale = 4
    width, height = 500, 280
    pixels = bytearray([255]) * (width * height)
    for line_number, line in enumerate(lines):
        for char_number, char in enumerate(line):
            glyph = glyphs[char]
            left = 18 + char_number * 7 * scale
            top = 15 + line_number * 40
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        for sy in range(scale):
                            start = (top + gy * scale + sy) * width + left + gx * scale
                            pixels[start : start + scale] = bytes([0]) * scale
    scanlines = b"".join(b"\x00" + pixels[y * width : (y + 1) * width] for y in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return (
            struct.pack(">I", len(payload))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(scanlines))
        + chunk(b"IEND", b"")
    )


@pytest.mark.skipif(
    os.environ.get("RUN_OPENCODE_GO_INTEGRATION") != "1",
    reason=(
        "Opt-in live OpenCode Go request; set RUN_OPENCODE_GO_INTEGRATION=1 and "
        "OPENCODE_GO_API_KEY."
    ),
)
def test_live_opencode_go_upload_to_structured_persistence(
    client: TestClient,
    employee_headers: dict[str, str],
    db: Session,
    tmp_path,
) -> None:
    # Settings reads the ignored root .env as well as the process environment.
    key = Settings().opencode_go_api_key
    if not key:
        pytest.fail(
            "RUN_OPENCODE_GO_INTEGRATION=1 requires OPENCODE_GO_API_KEY in the local environment."
        )
    config = Settings(
        _env_file=None,
        APP_ENV="test",
        EXTRACTION_PROVIDER="opencode_go",
        OPENCODE_GO_API_KEY=key,
        EXTRACTION_MAX_ATTEMPTS=1,
        EXTRACTION_TIMEOUT_SECONDS=90,
    )
    extractor = build_receipt_extractor(config)
    storage = LocalPrivateReceiptStorage(root=tmp_path)
    client.app.dependency_overrides[get_receipt_extractor] = lambda: extractor
    client.app.dependency_overrides[get_receipt_storage] = lambda: storage
    client.app.dependency_overrides[get_settings_dep] = lambda: config
    try:
        draft = client.post(
            "/api/v1/expenses",
            headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
            json={"channel": "web"},
        )
        assert draft.status_code == 201, draft.text
        uploaded = client.post(
            f"/api/v1/expenses/{draft.json()['id']}/receipts",
            headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
            files={"file": ("synthetic-receipt.png", _png(), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        receipt = uploaded.json()["receipt"]
        assert receipt["extraction_status"] == ExtractionStatus.PENDING.value
        run_id = uuid.UUID(receipt["extraction_runs"][0]["id"])
        worker = ExtractionJobWorker(
            session_factory=lambda: Session(
                bind=db.connection(), join_transaction_mode="create_savepoint"
            ),
            storage=storage,
            extractor=extractor,
            concurrency=1,
            max_attempts=1,
            timeout_seconds=90,
            retry_backoff_seconds=0,
        )
        worker._process_run(run_id)
        run = db.execute(select(ExtractionRun).where(ExtractionRun.id == run_id)).scalar_one()
        if run.status not in {ExtractionStatus.SUCCESS.value, ExtractionStatus.PARTIAL.value}:
            pytest.fail(
                "OpenCode Go synthetic receipt extraction failed: "
                f"status={run.status}, code={run.error_code}, message={run.error_message}"
            )
        assert run.status in {ExtractionStatus.SUCCESS.value, ExtractionStatus.PARTIAL.value}
        assert run.structured_result is not None
        assert run.provider == "opencode_go"
        assert run.model == "deepseek-v4.1-flash"
        assert run.raw_text_sha256 is None
        assert (
            "structured_result"
            in client.get(f"/api/v1/receipts/{receipt['id']}", headers=employee_headers).text
        )
        assert "raw_text" not in uploaded.text
    finally:
        extractor.close()
        client.app.dependency_overrides.pop(get_receipt_extractor, None)
        client.app.dependency_overrides.pop(get_receipt_storage, None)
        client.app.dependency_overrides.pop(get_settings_dep, None)
