"""Select the configured extraction provider."""

from __future__ import annotations

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.extraction.base import ReceiptExtractor
from app.extraction.unavailable import UnavailableExtractor


def build_receipt_extractor(config: Settings | None = None) -> ReceiptExtractor:
    """Return the extractor named by configuration.

    Every provider other than ``unavailable`` raises at construction time, because
    none has been implemented or benchmarked. Returning a working-looking
    extractor here would be the single easiest way to accidentally fabricate
    receipt data.
    """
    config = config or default_settings
    if config.extraction_provider == "unavailable":
        return UnavailableExtractor()
    raise NotImplementedError(
        f"Extraction provider {config.extraction_provider!r} is not implemented. "
        "Selecting a provider requires a benchmark against the supplied receipt set; "
        "see docs/testing-strategy.md. Configuring a provider name is not enough to "
        "make extraction work, and this build refuses to pretend otherwise."
    )
