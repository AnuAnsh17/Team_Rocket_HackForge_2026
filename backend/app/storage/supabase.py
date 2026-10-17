"""Supabase Storage adapter - NOT IMPLEMENTED.

The bucket this adapter targets must be **private**. Intended implementation:

    save(organization_id, expense_id, data, content_type)
        object_key = "{organization_id}/{expense_id}/{uuid4().hex}{ext}"
        supabase.storage.from_(bucket).upload(object_key, data, {"content-type": ...})

    read(object_key)
        supabase.storage.from_(bucket).download(object_key)

Requirements that must hold when this is implemented:

* The service-role key stays server-side and is never shipped to a client.
* The bucket is private and has no public policy. A public bucket would expose
  every employee's receipts to anyone who can guess a key.
* Any signed URL is short-lived (RECEIPT_SIGNED_URL_TTL_SECONDS) and is produced
  only after the caller's authorization has been checked against the parent
  claim.
* The bucket name and object key must never appear in a response DTO.

Until it is implemented and tested, constructing it raises, so the application
cannot accidentally believe it is storing receipts when it is not.
"""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.errors import NotImplementedYet
from app.storage.base import StorageError, StoredObject

_IMPLEMENTATION_NOTE = (
    "Supabase Storage is not implemented in the scaffolding phase. "
    "Receipt objects are not being stored anywhere by this backend. "
    "Use RECEIPT_STORAGE_BACKEND=local for local development."
)


class SupabaseReceiptStorage:
    backend_name = "supabase"

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or default_settings
        raise NotImplementedYet(_IMPLEMENTATION_NOTE)

    def save(
        self,
        *,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        raise NotImplementedYet(_IMPLEMENTATION_NOTE)

    def read(self, object_key: str) -> bytes:
        raise StorageError(_IMPLEMENTATION_NOTE)

    def delete(self, object_key: str) -> None:
        raise NotImplementedYet(_IMPLEMENTATION_NOTE)

    def exists(self, object_key: str) -> bool:
        raise NotImplementedYet(_IMPLEMENTATION_NOTE)
