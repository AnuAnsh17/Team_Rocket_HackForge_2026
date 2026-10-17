from __future__ import annotations

import pytest
from app.schemas.extraction import ReceiptExtractionPayload
from pydantic import ValidationError


def test_receipt_payload_defaults_to_explicit_missing_and_not_applicable() -> None:
    payload = ReceiptExtractionPayload()
    assert payload.merchant.value is None and payload.merchant.status == "missing"
    assert payload.tip.value is None and payload.tip.status == "not_applicable"


def test_receipt_payload_requires_null_for_non_extracted_fields() -> None:
    with pytest.raises(ValidationError):
        ReceiptExtractionPayload(merchant={"value": "Cafe", "status": "ambiguous"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("transaction_date", {"value": "10/02/2026", "status": "extracted"}),
        ("transaction_date", {"value": "2026-02-30", "status": "extracted"}),
        ("grand_total", {"value": 12.5, "status": "extracted"}),
        ("grand_total", {"value": "-12.50", "status": "extracted"}),
        ("grand_total", {"value": "999999999999999999999.00", "status": "extracted"}),
    ],
)
def test_receipt_payload_rejects_invalid_date_and_money(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ReceiptExtractionPayload(**{field: value})


def test_receipt_payload_limits_line_items_and_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ReceiptExtractionPayload(line_items=[{}] * 101)
    with pytest.raises(ValidationError):
        ReceiptExtractionPayload(merchant={"value": None, "status": "guessed"})
