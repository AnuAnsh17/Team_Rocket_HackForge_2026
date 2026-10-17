"""Versioned, untrusted receipt extraction payload and server validation DTOs."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeVar

from pydantic import BeforeValidator, Field, PlainSerializer, WithJsonSchema, model_validator

from app.schemas.common import ApiModel

T = TypeVar("T")
_DECIMAL_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,4})?$")
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_RECEIPT_MONEY = Decimal("9999999999999999.9999")


def _decimal_from_string(value: object) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL_PATTERN.fullmatch(value):
        raise ValueError("Money must be a non-negative decimal string with at most 4 places.")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Money is not a valid decimal string.") from exc
    if not result.is_finite() or result > _MAX_RECEIPT_MONEY:
        raise ValueError("Money is outside the supported range.")
    return result


def _iso_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, str):
        return value
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
        raise ValueError("Dates must use the unambiguous ISO YYYY-MM-DD form.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date is not a valid calendar date.") from exc


ReceiptMoney = Annotated[
    Decimal,
    BeforeValidator(_decimal_from_string),
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": _DECIMAL_PATTERN.pattern}),
]
ReceiptDate = Annotated[date, BeforeValidator(_iso_date)]
ReceiptText = Annotated[str, Field(min_length=1, max_length=300)]


class ReceiptFieldStatus(StrEnum):
    EXTRACTED = "extracted"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    ILLEGIBLE = "illegible"
    NOT_APPLICABLE = "not_applicable"


class ReceiptField[T](ApiModel):
    """A value with explicit model-reported certainty state."""

    value: T | None = None
    status: ReceiptFieldStatus

    @model_validator(mode="after")
    def status_matches_value(self) -> ReceiptField[T]:
        if self.status is ReceiptFieldStatus.EXTRACTED and self.value is None:
            raise ValueError("An extracted field must contain a value.")
        if self.status is not ReceiptFieldStatus.EXTRACTED and self.value is not None:
            raise ValueError("Only an extracted field may contain a value.")
        return self


class ReceiptLineItem(ApiModel):
    description: ReceiptField[ReceiptText] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    quantity: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    unit_price: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    line_total: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )


class ReceiptExtractionPayload(ApiModel):
    """Strict payload requested from a provider; contains no trusted server metadata."""

    merchant: ReceiptField[ReceiptText] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    transaction_date: ReceiptField[ReceiptDate] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    currency: ReceiptField[Annotated[str, Field(pattern=r"^[A-Z]{3}$")]] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    subtotal: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    tax_total: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    tip: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.NOT_APPLICABLE)
    )
    discount: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.NOT_APPLICABLE)
    )
    grand_total: ReceiptField[ReceiptMoney] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    receipt_number: ReceiptField[Annotated[str, Field(max_length=120)]] = Field(
        default_factory=lambda: ReceiptField(value=None, status=ReceiptFieldStatus.MISSING)
    )
    line_items: list[ReceiptLineItem] = Field(default_factory=list, max_length=100)


class ReceiptExtractionData(ReceiptExtractionPayload):
    """Persisted/public extraction data with server-owned version metadata."""

    schema_version: Literal["1.0"] = "1.0"


class ValidationSeverity(StrEnum):
    WARNING = "warning"


class ReceiptValidationFinding(ApiModel):
    code: str
    severity: ValidationSeverity = ValidationSeverity.WARNING
    message: str


class ReceiptValidationResult(ApiModel):
    validator_version: Literal["1"] = "1"
    human_review_required: bool = True
    review_reasons: list[str] = Field(default_factory=list, max_length=30)
    findings: list[ReceiptValidationFinding] = Field(default_factory=list, max_length=30)


def payload_for_provider_json_schema() -> dict[str, Any]:
    """Return the model-only JSON schema without server-added metadata."""
    return ReceiptExtractionPayload.model_json_schema()
