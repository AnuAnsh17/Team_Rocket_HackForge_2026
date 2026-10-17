"""Select the configured receipt storage backend."""

from __future__ import annotations

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.storage.base import ReceiptStorage
from app.storage.local import LocalPrivateReceiptStorage
from app.storage.supabase import SupabaseReceiptStorage


def build_receipt_storage(config: Settings | None = None) -> ReceiptStorage:
    """Return the storage backend named by configuration.

    ``supabase`` and ``s3`` raise at construction time, so a misconfiguration
    surfaces at startup rather than at the moment an employee tries to upload a
    receipt.
    """
    config = config or default_settings
    if config.receipt_storage_backend == "supabase":
        return SupabaseReceiptStorage(config)
    if config.receipt_storage_backend == "s3":
        raise NotImplementedError(
            "The S3 receipt storage adapter is not implemented. "
            "Use RECEIPT_STORAGE_BACKEND=local for development or supabase for the hosted adapter."
        )
    return LocalPrivateReceiptStorage(config)
