from __future__ import annotations

import hashlib
import json
import sys
import uuid
from io import StringIO

import pytest
from app.core.enums import ExtractionStatus
from app.extraction.indicocr import IndicOCRExtractor


class FakeWorker:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def extract_page(self, *, data: bytes, content_type: str) -> dict[str, object]:
        del data, content_type
        if self.error:
            raise self.error
        assert isinstance(self.result, dict)
        return self.result

    def close(self) -> None:
        return None


def page() -> dict[str, object]:
    return {
        "image": "page.png",
        "width": 100,
        "height": 200,
        "blocks": [{"order": 0, "bbox_xyxy": [1, 2, 3, 4], "text": "receipt"}],
        "markdown": "receipt text",
    }


def test_valid_page_is_hash_only_evidence_and_does_not_extract_fields() -> None:
    payload = page()
    result = IndicOCRExtractor(FakeWorker({"page": payload, "latency_ms": 20})).extract(
        receipt_id=uuid.uuid4(), data=b"image", content_type="image/png"
    )

    assert result.status is ExtractionStatus.SUCCESS
    assert result.fields == {}
    assert result.line_items == ()
    assert result.raw_text == "receipt text"
    assert (
        result.raw_payload_sha256
        == hashlib.sha256(
            b'{"blocks":[{"bbox_xyxy":[1,2,3,4],"order":0,"text":"receipt"}],"height":200,"image":"page.png","markdown":"receipt text","width":100}'
        ).hexdigest()
    )


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (TimeoutError(), ExtractionStatus.FAILED, "OCR_TIMEOUT"),
        (RuntimeError(), ExtractionStatus.FAILED, "OCR_PROCESSING_FAILED"),
        (ValueError(), ExtractionStatus.FAILED, "OCR_INVALID_OUTPUT"),
    ],
)
def test_provider_errors_are_truthful(
    error: Exception, status: ExtractionStatus, code: str
) -> None:
    result = IndicOCRExtractor(FakeWorker(error=error)).extract(
        receipt_id=uuid.uuid4(), data=b"image", content_type="image/png"
    )
    assert result.status is status
    assert result.error_code == code
    assert result.raw_text is None


def test_unavailable_runtime_is_not_reported_as_failed_inference() -> None:
    from app.extraction.indicocr import IndicOCRRuntimeError

    result = IndicOCRExtractor(FakeWorker(error=IndicOCRRuntimeError())).extract(
        receipt_id=uuid.uuid4(), data=b"image", content_type="image/png"
    )
    assert result.status is ExtractionStatus.UNAVAILABLE
    assert result.error_code == "OCR_RUNTIME_UNAVAILABLE"


def test_pdf_is_reported_as_unsupported_by_the_verified_page_parser() -> None:
    result = IndicOCRExtractor(FakeWorker()).extract(
        receipt_id=uuid.uuid4(), data=b"%PDF-1.4", content_type="application/pdf"
    )
    assert result.status is ExtractionStatus.FAILED
    assert result.error_code == "OCR_UNSUPPORTED_MEDIA_TYPE"


def test_malformed_documented_page_is_rejected() -> None:
    result = IndicOCRExtractor(FakeWorker({"page": {"markdown": "looks plausible"}})).extract(
        receipt_id=uuid.uuid4(), data=b"image", content_type="image/png"
    )
    assert result.status is ExtractionStatus.FAILED
    assert result.error_code == "OCR_INVALID_OUTPUT"


def test_worker_protocol_escapes_unicode_for_windows_console_encoding(monkeypatch) -> None:
    from app.extraction import indicocr_worker

    output = StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    indicocr_worker._write({"markdown": "नमस्ते"})
    encoded = output.getvalue()
    assert "नमस्ते" not in encoded
    assert json.loads(encoded)["markdown"] == "नमस्ते"
