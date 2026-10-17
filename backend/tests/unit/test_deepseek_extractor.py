from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal

import httpx
from app.core.enums import ExtractionStatus
from app.extraction.deepseek import DeepSeekVisionExtractor


def valid_payload() -> dict[str, object]:
    return {
        "merchant": {"value": "Cafe", "status": "extracted"},
        "transaction_date": {"value": "2026-10-02", "status": "extracted"},
        "currency": {"value": "INR", "status": "extracted"},
        "grand_total": {"value": "25.50", "status": "extracted"},
    }


def test_deepseek_sends_private_image_data_url_and_validates_result() -> None:
    captured: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(valid_payload())},
                    }
                ]
            },
        )

    receipt_id = uuid.uuid4()
    extractor = DeepSeekVisionExtractor(
        api_key="test-key", transport=httpx.MockTransport(respond), max_attempts=1
    )
    try:
        result = extractor.extract(
            receipt_id=receipt_id, data=b"synthetic-image", content_type="image/png"
        )
    finally:
        extractor.close()

    assert result.status is ExtractionStatus.SUCCESS
    assert result.structured_data is not None
    assert result.structured_data.grand_total.value == Decimal("25.50")
    request = captured[0]
    body = json.loads(request.content)
    image = body["messages"][1]["content"][1]["image_url"]["url"]
    assert image == "data:image/png;base64," + base64.b64encode(b"synthetic-image").decode()
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["x-opencode-session"] == str(receipt_id)
    assert request.headers["user-agent"] == "Proofline/0.1"
    assert str(request.url) == "https://opencode.ai/zen/go/v1/chat/completions"
    assert body["response_format"] == {"type": "json_object"}


def test_deepseek_missing_key_and_malformed_output_are_typed_failures() -> None:
    no_key = DeepSeekVisionExtractor(api_key=None, max_attempts=1)
    try:
        unavailable = no_key.extract(
            receipt_id=uuid.uuid4(), data=b"image", content_type="image/png"
        )
    finally:
        no_key.close()
    assert unavailable.status is ExtractionStatus.UNAVAILABLE
    assert unavailable.error_code == "OPENCODE_GO_API_KEY_MISSING"

    malformed = DeepSeekVisionExtractor(
        api_key="test-key",
        max_attempts=1,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": '{"grand_total": 12.5}'}}
                    ]
                },
            )
        ),
    )
    try:
        invalid = malformed.extract(
            receipt_id=uuid.uuid4(), data=b"image", content_type="image/jpeg"
        )
    finally:
        malformed.close()
    assert invalid.status is ExtractionStatus.FAILED
    assert invalid.error_code == "OPENCODE_GO_INVALID_EXTRACTION"


def test_deepseek_retries_rate_limits_with_bounded_attempt_count() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(valid_payload())}}
                ]
            },
        )

    extractor = DeepSeekVisionExtractor(
        api_key="test-key",
        max_attempts=2,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(respond),
    )
    try:
        result = extractor.extract(
            receipt_id=uuid.uuid4(), data=b"image", content_type="image/webp"
        )
    finally:
        extractor.close()
    assert result.status is ExtractionStatus.SUCCESS
    assert result.attempt_count == 2
    assert calls == 2
