"""Receipt extraction adapters. Evidence only, never policy authority."""

from app.extraction.base import (
    EXTRACTABLE_FIELDS,
    ExtractedLineItem,
    ExtractionResult,
    FieldEvidence,
    ReceiptExtractor,
)
from app.extraction.unavailable import UnavailableExtractor

__all__ = [
    "EXTRACTABLE_FIELDS",
    "ExtractedLineItem",
    "ExtractionResult",
    "FieldEvidence",
    "ReceiptExtractor",
    "UnavailableExtractor",
]
