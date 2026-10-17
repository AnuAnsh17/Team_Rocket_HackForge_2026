"""Load the deterministic synthetic demo dataset.

Usage:
    cd backend
    ./.venv/Scripts/python scripts/dev_seed.py

Requires demo mode to be enabled. The dataset is fictional and deterministic: every
identifier is derived with uuid5 from a fixed namespace, so the same ids appear on every
machine and after every reset. It creates one organization, fictional people,
memberships, role grants, reporting edges and one *draft, empty* policy version - and
deliberately no job grades, no allowance limits, no policy rules and no claims. See
docs/demo-runbook.md for why.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, session_scope
from app.services import demo_service

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

    try:
        with session_scope() as session:
            result = demo_service.seed_demo_dataset(session, actor_label="dev_seed script")
    finally:
        dispose_engine()

    print(f"\nDataset:  {result.dataset} (synthetic)")
    print(f"Users:    {result.users}")
    print(f"Memberships: {result.memberships}")
    print(f"Policy rules activated: {result.policy_rules_activated}")
    print("\nNotes:")
    for note in result.notes:
        print(f"  - {note}")
    print("\nUse an id above as the X-Demo-Actor-Id header.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
