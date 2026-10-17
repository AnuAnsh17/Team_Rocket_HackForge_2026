"""Remove the synthetic demo dataset.

Usage:
    cd backend
    ./.venv/Scripts/python scripts/dev_reset.py

Removes only the fixed demo organization and demo-provider users. Non-demo data is not
reachable from this operation, and the script refuses to run outside a local
environment. Audit events are append-only and survive the reset; the reset itself is
recorded as an audit event.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, session_scope
from app.services import demo_service
from app.storage.factory import build_receipt_storage

logger = get_logger("proofline.scripts.dev_reset")

# Explicit allowlist rather than "not production": a new environment name must not
# silently gain the ability to delete data.
_PERMITTED_ENVIRONMENTS = frozenset({"development", "test"})


def main() -> int:
    configure_logging()
    if settings.app_env not in _PERMITTED_ENVIRONMENTS:
        print(
            f"Refusing to reset: APP_ENV is {settings.app_env!r}.\n"
            f"This script only runs in {sorted(_PERMITTED_ENVIRONMENTS)}.",
            file=sys.stderr,
        )
        return 1
    if not settings.demo_mode:
        print(
            "Refusing to reset: DEMO_MODE is not enabled, so this is not a demo dataset.",
            file=sys.stderr,
        )
        return 1

    storage = build_receipt_storage(settings)
    object_keys: tuple[str, ...] = ()
    try:
        with session_scope() as session:
            object_keys = demo_service.demo_receipt_object_keys(session)
            result = demo_service.reset_demo_dataset(session, actor_label="dev_reset script")
        for object_key in object_keys:
            storage.delete(object_key)
    finally:
        dispose_engine()

    print(f"\nDataset: {result.dataset}")
    print(f"Organizations removed: {result.organizations_removed}")
    print(f"Users removed:         {result.users_removed}")
    for note in result.notes:
        print(f"  - {note}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
