"""Private local-filesystem receipt storage for development.

This backend exists so a developer can exercise the full upload and authorized
download path without cloud credentials. It is not a production option:
application configuration refuses RECEIPT_STORAGE_BACKEND=local outside local
development.

Objects are written beneath a directory that must sit outside any web root, with
server-generated keys, so no client input ever reaches the filesystem path.
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import suppress
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.storage.base import StorageError, StoredObject, sanitise_filename

_EXTENSION_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "application/pdf": ".pdf",
}


class LocalPrivateReceiptStorage:
    """Filesystem-backed private storage. Development only."""

    backend_name = "local"

    def __init__(self, config: Settings | None = None, root: str | Path | None = None) -> None:
        config = config or default_settings
        self._root = Path(root) if root is not None else Path(config.receipt_local_root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, object_key: str) -> Path:
        """Map an opaque key to a path, refusing traversal outright."""
        pure = PurePosixPath(object_key)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise StorageError("Refusing to resolve an unsafe object key.")
        candidate = (self._root / pure).resolve()
        root_resolved = self._root.resolve()
        if candidate != root_resolved and root_resolved not in candidate.parents:
            raise StorageError("Refusing to resolve a path outside the storage root.")
        return candidate

    def save(
        self,
        *,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        digest = hashlib.sha256(data).hexdigest()
        extension = _EXTENSION_BY_MIME.get(content_type, ".bin")
        # Key layout is org/expense scoped so an erasure request is a prefix
        # delete, and the leaf is a fresh UUID so identical files never collide.
        object_key = f"{organization_id}/{expense_id}/{uuid.uuid4().hex}{extension}"
        path = self._path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except OSError as exc:  # pragma: no cover - filesystem failure
            # ``write_bytes`` may create or truncate the destination before the
            # write fails. Do not leave an orphaned partial receipt behind.
            with suppress(OSError):
                path.unlink(missing_ok=True)
            raise StorageError("Could not write the receipt object.") from exc
        return StoredObject(
            object_key=object_key,
            byte_size=len(data),
            sha256=digest,
            detected_mime_type=content_type,
            storage_backend=self.backend_name,
        )

    def read(self, object_key: str) -> bytes:
        path = self._path_for(object_key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("Could not read the receipt object.") from exc

    def delete(self, object_key: str) -> None:
        path = self._path_for(object_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise StorageError("Could not delete the receipt object.") from exc

    def exists(self, object_key: str) -> bool:
        return self._path_for(object_key).is_file()

    def delete_expense_objects(self, organization_id: uuid.UUID, expense_id: uuid.UUID) -> int:
        """Remove every object stored for one claim. Used by demo reset."""
        directory = self._path_for(f"{organization_id}/{expense_id}")
        if not directory.is_dir():
            return 0
        removed = 0
        for child in directory.iterdir():
            if child.is_file():
                child.unlink()
                removed += 1
        directory.rmdir()
        return removed

    @staticmethod
    def safe_label(filename: str | None) -> str | None:
        return sanitise_filename(filename)
