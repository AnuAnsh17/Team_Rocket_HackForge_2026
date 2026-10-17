"""The provider-neutral extraction interface.

Extraction produces **evidence**, never a policy decision. Everything this module
returns is treated downstream as a claim about the document that must be
validated, not as a fact about reimbursement.

Two deliberate omissions:

* There is no ``confidence`` field on :class:`ExtractedField` that is populated
  by guesswork. A provider either reports a quality signal or the value is
  ``None``. The system must never synthesise a number that looks calibrated.
* There is no method that returns a policy result. An extractor cannot influence
  a finding.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.core.enums import ExtractionStatus
from app.schemas.extraction import ReceiptExtractionPayload

# Canonical field names an extractor may report. These map onto
# ExpenseFieldName where a field also exists on the claim.
EXTRACTABLE_FIELDS: tuple[str, ...] = (
    "merchant",
    "transaction_date",
    "transaction_time",
    "subtotal",
    "tax",
    "tip",
    "discount",
    "total",
    "currency",
    "receipt_number",
    "payment_reference",
    "line_items",
)


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    """One extracted field with its provenance and any region the provider gave.

    ``region`` is populated only when the provider genuinely reports coordinates.
    Fabricating a plausible-looking rectangle would make the "highlight the
    receipt region" feature actively misleading.
    """

    value_text: str | None = None
    value_decimal: Decimal | None = None
    value_date: date | None = None
    currency: str | None = None
    confidence: float | None = None
    page: int | None = None
    region: tuple[float, float, float, float] | None = None
    unreadable: bool = False
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedLineItem:
    line_number: int | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    tax_amount: Decimal | None = None
    discount_amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The outcome of one extraction attempt.

    ``status`` is the authoritative signal. A ``SUCCESS`` with an empty ``fields``
    mapping means the provider ran and found nothing usable - it does not mean
    the receipt was blank, and it must not be interpreted as one.
    """

    status: ExtractionStatus
    provider: str
    model: str | None = None
    prompt_version: str | None = None
    fields: dict[str, FieldEvidence] = field(default_factory=dict)
    line_items: tuple[ExtractedLineItem, ...] = ()
    structured_data: ReceiptExtractionPayload | None = None
    raw_text: str | None = None
    raw_payload_sha256: str | None = None
    latency_ms: int | None = None
    attempt_count: int = 1
    error_code: str | None = None
    error_message: str | None = None
    is_cached_result: bool = False
    notes: tuple[str, ...] = ()


@runtime_checkable
class ReceiptExtractor(Protocol):
    """Provider adapter contract.

    Implementations must be replaceable without touching the policy engine or any
    client. Selecting a real provider is an implementation-phase decision that
    depends on a benchmark against the supplied receipt set.
    """

    provider_name: str

    def extract(self, *, receipt_id: uuid.UUID, data: bytes, content_type: str) -> ExtractionResult:
        """Extract structured evidence from one receipt image."""
        ...
