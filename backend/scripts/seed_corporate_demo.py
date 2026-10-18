"""Build the corporate demo database. Idempotent: safe to run repeatedly.

Usage:
    cd backend
    ./.venv/Scripts/python scripts/seed_corporate_demo.py \
        --dataset "$USERPROFILE/Desktop/ProoflineReceiptBenchmark"

Requires demo mode. Extends the organization created by scripts/dev_seed.py, so run that
first. Nothing is written outside the configured database and the configured receipt
storage root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, session_scope
from app.services.corporate_demo_service import seed_corporate_demo
from app.storage.factory import build_receipt_storage

logger = get_logger("proofline.scripts.seed_corporate_demo")

DEFAULT_DATASET = Path.home() / "Desktop" / "ProoflineReceiptBenchmark"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help="Benchmark dataset folder containing manifest.json",
    )
    parser.add_argument(
        "--duplicates",
        type=int,
        default=40,
        help="Number of deliberate duplicate-submission candidates to create",
    )
    args = parser.parse_args()

    configure_logging()
    if not settings.demo_routes_enabled:
        print(
            "Refusing to seed: demo mode is not enabled (set DEMO_MODE=true in .env).",
            file=sys.stderr,
        )
        return 1

    dataset_root = Path(args.dataset)
    if not (dataset_root / "manifest.json").is_file():
        print(f"No manifest.json under {dataset_root}", file=sys.stderr)
        return 1

    storage = build_receipt_storage()
    try:
        with session_scope() as session:
            result = seed_corporate_demo(
                session,
                dataset_root=dataset_root,
                storage=storage,
                duplicate_budget=args.duplicates,
            )
    finally:
        dispose_engine()

    print("\nCorporate demo dataset seeded")
    print("=" * 46)
    print(f"people created this run : {result.people_created}")
    print(f"accounts total          : {result.people_total}")
    print(f"departments             : {result.departments}")
    print(f"offices                 : {result.offices}")
    print(f"cost centres            : {result.cost_centres}")
    print(f"job grades              : {result.job_grades}")
    print(
        f"allowance profiles      : {result.allowance_profiles} ({result.allowance_items} limits)"
    )
    print(f"claims created this run : {result.claims_created}")
    print(f"claims total            : {result.claims_total}")
    print(f"receipts created        : {result.receipts_created}")
    print(f"receipts total          : {result.receipts_total}")
    print(f"benchmark samples mapped: {result.samples_imported} (skipped {result.samples_skipped})")
    print(f"duplicate candidates    : {result.duplicate_candidates}")
    print(f"by status               : {result.by_status}")
    print(f"by month                : {result.by_month}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
