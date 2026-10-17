from __future__ import annotations

from app.extraction.validation import validate_extraction
from app.schemas.extraction import ReceiptExtractionPayload


def test_arithmetic_review_is_deterministic_and_never_rewrites_fields() -> None:
    payload = ReceiptExtractionPayload(
        merchant={"value": "Cafe", "status": "extracted"},
        transaction_date={"value": "2026-10-02", "status": "extracted"},
        currency={"value": "INR", "status": "extracted"},
        subtotal={"value": "10.00", "status": "extracted"},
        tax_total={"value": "1.80", "status": "extracted"},
        tip={"value": None, "status": "not_applicable"},
        discount={"value": None, "status": "not_applicable"},
        grand_total={"value": "15.00", "status": "extracted"},
    )
    result = validate_extraction(payload)
    assert "TOTAL_COMPONENTS_DO_NOT_RECONCILE" in result.review_reasons
    assert payload.grand_total.value is not None
    assert str(payload.grand_total.value) == "15.00"
    assert result.human_review_required is True


def test_missing_component_stays_unknown_without_an_arithmetic_claim() -> None:
    payload = ReceiptExtractionPayload(
        grand_total={"value": "15.00", "status": "extracted"},
    )
    result = validate_extraction(payload)
    assert "TOTAL_COMPONENTS_DO_NOT_RECONCILE" not in result.review_reasons
    assert "MERCHANT_MISSING" in result.review_reasons
    assert payload.subtotal.status == "missing"
