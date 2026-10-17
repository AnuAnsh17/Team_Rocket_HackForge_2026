"""The extractor used until a provider has actually been selected and verified.

This is not a mock that returns invented receipt data. It reports
``ExtractionStatus.UNAVAILABLE`` and returns no fields, so any downstream code
that assumes real extraction has happened fails visibly instead of being fed
plausible-looking fiction.
"""

from __future__ import annotations

import uuid

from app.core.enums import ExtractionStatus
from app.extraction.base import ExtractionResult

_REASON = (
    "No receipt extraction provider has been selected or verified. "
    "See docs/architecture-decisions.md, 'Extraction provider', and "
    "docs/testing-strategy.md, 'Extraction evaluation'."
)


class UnavailableExtractor:
    """Always reports that extraction has not been implemented."""

    provider_name = "unavailable"

    def __init__(
        self, *, reason: str = _REASON, error_code: str = "EXTRACTION_UNAVAILABLE"
    ) -> None:
        self._reason = reason
        self._error_code = error_code

    def extract(self, *, receipt_id: uuid.UUID, data: bytes, content_type: str) -> ExtractionResult:
        return ExtractionResult(
            status=ExtractionStatus.UNAVAILABLE,
            provider=self.provider_name,
            model=None,
            fields={},
            line_items=(),
            error_code=self._error_code,
            error_message=self._reason,
            notes=(
                self._reason,
                "No field values were produced, so no finding can be based on extraction.",
            ),
        )
