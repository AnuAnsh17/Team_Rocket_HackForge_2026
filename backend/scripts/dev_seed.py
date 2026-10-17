"""Load the deterministic synthetic demo dataset.

Usage:
    cd backend
    ./.venv/Scripts/python scripts/dev_seed.py

Requires demo mode to be enabled. The dataset is fictional and deterministic: every
identifier is derived with uuid5 from a fixed namespace, so the same ids appear on every
machine and after every reset. It creates the organization/identity graph and lifecycle
claims through the same application services used by the API. Receipts are synthetic and
remain pending; no OCR result is fabricated. A fictional policy fixture is optional and
requires the guarded DEMO_SYNTHETIC_POLICY_ENABLED setting. See docs/demo-runbook.md.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, session_scope
from app.services import demo_service
from app.storage.factory import build_receipt_storage

logger = get_logger("proofline.scripts.dev_seed")


def main() -> int:
    configure_logging()
    if not settings.demo_routes_enabled:
        print(
            "Refusing to seed: demo mode is not enabled.\n"
            "Set DEMO_MODE=true and APP_ENV to a development value in .env, then retry.\n"
            "Seeding is never permitted outside a local environment.",
            file=sys.stderr,
        )
        return 1

    storage = build_receipt_storage(settings)
    rollback_callbacks: list[Callable[[], None]] = []
    try:
        with session_scope() as session:
            result = demo_service.seed_demo_dataset(
                session,
                actor_label="dev_seed script",
                include_claim_scenarios=True,
                storage=storage,
                rollback_callbacks=rollback_callbacks,
            )
    except Exception:
        for callback in rollback_callbacks:
            callback()
        raise
    finally:
        dispose_engine()

    print(f"\nDataset:  {result.dataset} (synthetic)")
    print(f"Users:    {result.users}")
    print(f"Memberships: {result.memberships}")
    print("Claim scenarios: draft, submitted, in_review, needs_info, approved, rejected")
    print(f"Policy rules activated: {result.policy_rules_activated}")
    print("\nNotes:")
    for note in result.notes:
        print(f"  - {note}")
    print("\nUse an id above as the X-Demo-Actor-Id header.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
