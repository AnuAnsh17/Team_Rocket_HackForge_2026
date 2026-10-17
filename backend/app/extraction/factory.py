"""Select the configured extraction provider."""

from __future__ import annotations

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.extraction.base import ReceiptExtractor
from app.extraction.deepseek import DeepSeekVisionExtractor
from app.extraction.indicocr import IndicOCRExtractor, IndicOCRWorker
from app.extraction.unavailable import UnavailableExtractor


def build_receipt_extractor(config: Settings | None = None) -> ReceiptExtractor:
    """Return the extractor named by configuration.

    The local IndicOCR runtime is isolated in its own Python environment. Other
    named providers still fail closed until their adapters are implemented.
    """
    config = config or default_settings
    if config.extraction_provider == "unavailable":
        return UnavailableExtractor()
    if config.extraction_provider == "opencode_go":
        return DeepSeekVisionExtractor(
            api_key=config.opencode_go_api_key,
            model=config.opencode_go_model,
            base_url=config.opencode_go_base_url,
            timeout_seconds=config.extraction_timeout_seconds,
            max_attempts=config.extraction_max_attempts,
            retry_backoff_seconds=config.extraction_retry_backoff_seconds,
        )
    if config.extraction_provider == "local_ocr":
        if not config.extraction_model or not config.extraction_python_executable:
            return UnavailableExtractor(
                reason=(
                    "IndicOCR requires EXTRACTION_MODEL and "
                    "EXTRACTION_PYTHON_EXECUTABLE to point at the existing local model and "
                    "its isolated Python environment."
                ),
                error_code="OCR_RUNTIME_NOT_CONFIGURED",
            )
        return IndicOCRExtractor(
            IndicOCRWorker(
                python_executable=config.extraction_python_executable,
                model_path=config.extraction_model,
                timeout_seconds=config.extraction_timeout_seconds,
            )
        )
    raise NotImplementedError(
        f"Extraction provider {config.extraction_provider!r} is not implemented. "
        "Selecting a provider requires a benchmark against the supplied receipt set; "
        "see docs/testing-strategy.md. Configuring a provider name is not enough to "
        "make extraction work, and this build refuses to pretend otherwise."
    )
