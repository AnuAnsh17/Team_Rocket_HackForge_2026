"""Deterministic validation of normalized extraction; contains no policy decisions."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.extraction import (
    ReceiptExtractionPayload,
    ReceiptFieldStatus,
    ReceiptValidationFinding,
    ReceiptValidationResult,
)

_REQUIRED_FIELDS = ("merchant", "transaction_date", "currency", "grand_total")
_ARITHMETIC_TOLERANCE = Decimal("0.0001")


def validate_extraction(
    result: ReceiptExtractionPayload,
) -> ReceiptValidationResult:
    """Return backend-owned review signals without changing any extracted value."""
    reasons: set[str] = {"EMPLOYEE_CONFIRMATION_REQUIRED"}
    findings: list[ReceiptValidationFinding] = []

    for field_name in _REQUIRED_FIELDS:
        field = getattr(result, field_name)
        if field.status is not ReceiptFieldStatus.EXTRACTED:
            reason = f"{field_name.upper()}_{field.status.value.upper()}"
            reasons.add(reason)
            findings.append(
                ReceiptValidationFinding(
                    code=reason,
                    message=f"{field_name.replace('_', ' ').title()} needs human review.",
                )
            )

    for field_name in (
        "merchant",
        "transaction_date",
        "currency",
        "subtotal",
        "tax_total",
        "tip",
        "discount",
        "grand_total",
        "receipt_number",
    ):
        field = getattr(result, field_name)
        if field.status in {ReceiptFieldStatus.AMBIGUOUS, ReceiptFieldStatus.ILLEGIBLE}:
            reason = f"{field_name.upper()}_{field.status.value.upper()}"
            reasons.add(reason)
            findings.append(
                ReceiptValidationFinding(
                    code=reason,
                    message=f"{field_name.replace('_', ' ').title()} is uncertain.",
                )
            )

    components = (result.subtotal, result.tax_total, result.tip, result.discount)
    components_accounted_for = all(
        field.status in {ReceiptFieldStatus.EXTRACTED, ReceiptFieldStatus.NOT_APPLICABLE}
        for field in components
    )
    if result.grand_total.status is ReceiptFieldStatus.EXTRACTED and components_accounted_for:
        expected_total = sum(
            (
                field.value
                if field.status is ReceiptFieldStatus.EXTRACTED and field.value is not None
                else Decimal(0)
            )
            * (Decimal(-1) if field is result.discount else Decimal(1))
            for field in components
        )
        grand_total = result.grand_total.value
        if grand_total is not None and abs(expected_total - grand_total) > _ARITHMETIC_TOLERANCE:
            reasons.add("TOTAL_COMPONENTS_DO_NOT_RECONCILE")
            findings.append(
                ReceiptValidationFinding(
                    code="TOTAL_COMPONENTS_DO_NOT_RECONCILE",
                    message=(
                        "The visible subtotal, tax, tip, discount and total do not reconcile; "
                        "verify the receipt manually."
                    ),
                )
            )

    return ReceiptValidationResult(
        human_review_required=True,
        review_reasons=sorted(reasons),
        findings=findings,
    )


def has_partial_result(
    result: ReceiptExtractionPayload, validation: ReceiptValidationResult
) -> bool:
    """Whether critical data is missing or deterministic review found a discrepancy."""
    del result
    return any(reason != "EMPLOYEE_CONFIRMATION_REQUIRED" for reason in validation.review_reasons)
