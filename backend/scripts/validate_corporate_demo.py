"""Independently verify the seeded corporate demo database.

Reads only the database and the benchmark dataset; it does not trust the seeder's own
summary. Every check below is a query.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.db.session import dispose_engine, session_scope
from app.models.expense import Expense
from app.models.identity import (
    OrganizationMembership,
    ReportingRelationship,
    RoleAssignment,
    User,
)
from app.models.organization import (
    AllowanceProfile,
    AllowanceProfileItem,
    CostCenter,
    Department,
    JobGrade,
    OfficeLocation,
    Organization,
)
from app.models.receipt import Receipt
from app.services.demo_service import DEMO_ORG_SLUG
from sqlalchemy import func, select

DEFAULT_DATASET = Path.home() / "Desktop" / "ProoflineReceiptBenchmark"
EXPECTED_SAMPLES = 250
EXPECTED_ACCOUNTS = 30
DEMO_MARKERS = ("DEMO ONLY", "FICTIONAL")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--json-out")
    args = parser.parse_args()

    dataset_root = Path(args.dataset)
    manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
    samples = {s["id"]: s for s in manifest["samples"]}

    findings: dict[str, Any] = {}
    problems: list[str] = []

    with session_scope() as session:
        org = session.execute(
            select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
        ).scalar_one_or_none()
        if org is None:
            print("FAIL: demo organization not found", file=sys.stderr)
            return 1

        memberships = (
            session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == org.id
                )
            )
            .scalars()
            .all()
        )
        users = {
            u.id: u
            for u in session.execute(select(User).where(User.primary_organization_id == org.id))
            .scalars()
            .all()
        }

        findings["organisation"] = {
            "slug": org.slug,
            "name": org.name,
            "is_demo": org.is_demo,
            "reporting_currency": org.reporting_currency,
            "timezone": org.timezone,
        }
        findings["accounts"] = len(memberships)
        if len(memberships) != EXPECTED_ACCOUNTS:
            problems.append(f"expected {EXPECTED_ACCOUNTS} accounts, found {len(memberships)}")

        # --- employee profile completeness ---
        incomplete = []
        emails: collections.Counter[str] = collections.Counter()
        codes: collections.Counter[str] = collections.Counter()
        for membership in memberships:
            user = users.get(membership.user_id)
            missing = [
                name
                for name, value in (
                    ("employee_code", membership.employee_code),
                    ("department", membership.department_id),
                    ("office", membership.office_location_id),
                    ("cost_centre", membership.cost_center_id),
                    ("job_grade", membership.job_grade_id),
                    ("joined_on", membership.joined_on),
                    ("status", membership.status),
                    ("email", user.email if user else None),
                    ("display_name", user.display_name if user else None),
                )
                if value is None
            ]
            if missing:
                incomplete.append({"membership": str(membership.id), "missing": missing})
            if user and user.email:
                emails[user.email] += 1
            if membership.employee_code:
                codes[membership.employee_code] += 1
        findings["incomplete_profiles"] = incomplete
        if incomplete:
            problems.append(f"{len(incomplete)} accounts have incomplete profiles")
        duplicate_emails = {e: c for e, c in emails.items() if c > 1}
        duplicate_codes = {c: n for c, n in codes.items() if n > 1}
        findings["duplicate_emails"] = duplicate_emails
        findings["duplicate_employee_codes"] = duplicate_codes
        if duplicate_emails:
            problems.append(f"duplicate e-mail addresses: {duplicate_emails}")
        if duplicate_codes:
            problems.append(f"duplicate employee codes: {duplicate_codes}")

        # --- roles and reporting ---
        membership_ids = {m.id for m in memberships}
        role_counts: collections.Counter[str] = collections.Counter()
        for role, count in session.execute(
            select(RoleAssignment.role, func.count())
            .where(RoleAssignment.organization_id == org.id)
            .group_by(RoleAssignment.role)
        ).all():
            role_counts[str(role)] = int(count)
        findings["roles"] = dict(role_counts)

        edges = (
            session.execute(
                select(ReportingRelationship).where(ReportingRelationship.organization_id == org.id)
            )
            .scalars()
            .all()
        )
        broken_edges = [
            str(e.id)
            for e in edges
            if e.manager_membership_id not in membership_ids
            or e.employee_membership_id not in membership_ids
        ]
        managers_with_reports = collections.Counter(str(e.manager_membership_id) for e in edges)
        findings["reporting_edges"] = len(edges)
        findings["managers_with_reports"] = len(managers_with_reports)
        findings["broken_reporting_edges"] = broken_edges
        if broken_edges:
            problems.append(f"{len(broken_edges)} reporting edges reference a missing manager")

        # --- structure ---
        for label, model in (
            ("departments", Department),
            ("offices", OfficeLocation),
            ("cost_centres", CostCenter),
            ("job_grades", JobGrade),
        ):
            findings[label] = int(
                session.execute(
                    select(func.count()).select_from(model).where(model.organization_id == org.id)
                ).scalar_one()
            )

        # --- allowance profiles must be unmistakably demo data ---
        profiles = (
            session.execute(
                select(AllowanceProfile).where(AllowanceProfile.organization_id == org.id)
            )
            .scalars()
            .all()
        )
        unmarked = [
            p.code
            for p in profiles
            if not any(marker in (p.name or "").upper() for marker in DEMO_MARKERS)
        ]
        attached_to_policy = [p.code for p in profiles if p.policy_version_id is not None]
        findings["allowance_profiles"] = len(profiles)
        findings["allowance_items"] = int(
            session.execute(
                select(func.count())
                .select_from(AllowanceProfileItem)
                .join(
                    AllowanceProfile,
                    AllowanceProfile.id == AllowanceProfileItem.allowance_profile_id,
                )
                .where(AllowanceProfile.organization_id == org.id)
            ).scalar_one()
        )
        findings["allowance_profile_review_states"] = {p.code: p.review_state for p in profiles}
        findings["allowance_profiles_not_marked_demo"] = unmarked
        findings["allowance_profiles_attached_to_policy"] = attached_to_policy
        if unmarked:
            problems.append(f"allowance profiles not marked DEMO ONLY: {unmarked}")
        if attached_to_policy:
            problems.append(f"demo allowances attached to a policy version: {attached_to_policy}")

        # --- receipts and claims ---
        expense_ids = set(
            session.execute(select(Expense.id).where(Expense.organization_id == org.id))
            .scalars()
            .all()
        )
        receipts = (
            session.execute(select(Receipt).where(Receipt.organization_id == org.id))
            .scalars()
            .all()
        )
        orphan_receipts = [str(r.id) for r in receipts if r.expense_id not in expense_ids]
        receipts_by_expense = collections.Counter(str(r.expense_id) for r in receipts)
        findings["claims"] = len(expense_ids)
        findings["receipts"] = len(receipts)
        findings["orphan_receipts"] = orphan_receipts
        if orphan_receipts:
            problems.append(f"{len(orphan_receipts)} receipts point at a missing claim")

        expenses_without_receipt = [
            str(i) for i in expense_ids if str(i) not in receipts_by_expense
        ]
        findings["claims_without_receipt"] = len(expenses_without_receipt)

        # every benchmark sample must be present exactly once as a canonical receipt
        canonical = {
            r.original_filename.rsplit(".", 1)[0]: r
            for r in receipts
            if r.parent_receipt_id is None and r.original_filename
        }
        missing = [sid for sid in samples if sid not in canonical]
        findings["samples_expected"] = len(samples)
        findings["samples_mapped"] = len(canonical)
        findings["samples_missing"] = missing[:20]
        if missing:
            problems.append(f"{len(missing)} benchmark samples are not in the database")

        # storage objects must exist on disk and match their recorded digest
        import hashlib

        from app.storage.factory import build_receipt_storage

        storage = build_receipt_storage()
        missing_objects = []
        digest_mismatch = []
        for receipt in receipts:
            try:
                data = storage.read(receipt.object_key)
            except Exception:
                missing_objects.append(receipt.original_filename or str(receipt.id))
                continue
            if hashlib.sha256(data).hexdigest() != receipt.sha256:
                digest_mismatch.append(receipt.original_filename or str(receipt.id))
        findings["missing_storage_objects"] = missing_objects[:20]
        findings["storage_digest_mismatches"] = digest_mismatch[:20]
        if missing_objects:
            problems.append(f"{len(missing_objects)} receipt objects are unreadable")
        if digest_mismatch:
            problems.append(f"{len(digest_mismatch)} stored objects do not match their digest")

        # --- distributions ---
        def distribution(column: Any, label: str) -> dict[str, int]:
            rows = session.execute(
                select(column, func.count())
                .where(Expense.organization_id == org.id)
                .group_by(column)
            ).all()
            values: dict[str, int] = {str(k): int(v) for k, v in rows if k is not None}
            findings[label] = values
            return values

        by_status = distribution(Expense.status, "claims_by_status")
        distribution(Expense.category, "claims_by_category")
        month_counts: collections.Counter[str] = collections.Counter()
        for (expense_date,) in session.execute(
            select(Expense.expense_date).where(Expense.organization_id == org.id)
        ).all():
            if expense_date is not None:
                month_counts[expense_date.strftime("%Y-%m")] += 1
        by_month = dict(sorted(month_counts.items()))
        findings["claims_by_month"] = by_month

        # department / office spread via membership join
        dept_rows = session.execute(
            select(Department.name, func.count(Expense.id))
            .join(OrganizationMembership, OrganizationMembership.id == Expense.membership_id)
            .join(Department, Department.id == OrganizationMembership.department_id)
            .where(Expense.organization_id == org.id)
            .group_by(Department.name)
        ).all()
        findings["claims_by_department"] = {str(k): int(v) for k, v in dept_rows}
        office_rows = session.execute(
            select(OfficeLocation.city, func.count(Expense.id))
            .join(OrganizationMembership, OrganizationMembership.id == Expense.membership_id)
            .join(OfficeLocation, OfficeLocation.id == OrganizationMembership.office_location_id)
            .where(Expense.organization_id == org.id)
            .group_by(OfficeLocation.city)
        ).all()
        findings["claims_by_city"] = {str(k): int(v) for k, v in office_rows}
        employee_rows = session.execute(
            select(Expense.membership_id, func.count())
            .where(Expense.organization_id == org.id)
            .group_by(Expense.membership_id)
        ).all()
        findings["distinct_employees_with_claims"] = len(employee_rows)

        if len(by_status) < 4:
            problems.append(f"claim status distribution is too narrow: {by_status}")
        if len(findings["claims_by_department"]) < 5:
            problems.append("claims do not span at least five departments")
        if len(findings["claims_by_city"]) < 4:
            problems.append("claims do not span at least four cities")

        # --- three-month window ---
        window = session.execute(
            select(func.count())
            .select_from(Expense)
            .where(
                Expense.organization_id == org.id,
                Expense.expense_date >= dt.date(2026, 7, 1),
                Expense.expense_date <= dt.date(2026, 9, 30),
            )
        ).scalar_one()
        findings["claims_in_target_window_jul_sep_2026"] = int(window)
        # Check the three months individually. A total alone would pass even if one month
        # were empty, which is exactly the failure a dashboard would expose.
        monthly = {month: by_month.get(month, 0) for month in ("2026-07", "2026-08", "2026-09")}
        findings["claims_per_target_month"] = monthly
        thin = {month: count for month, count in monthly.items() if count < 25}
        if thin:
            problems.append(
                f"the three-month window is not usable: month(s) with fewer than 25 claims: {thin}"
            )
        if int(window) < 75:
            problems.append(
                f"only {window} claims fall inside Jul-Sep 2026; the brief expects a usable "
                "three-month window"
            )

        # --- workflow ordering ---
        bad_order = 0
        approved_without_decision = 0
        for expense in (
            session.execute(select(Expense).where(Expense.organization_id == org.id))
            .scalars()
            .all()
        ):
            if (
                expense.submitted_at
                and expense.created_at
                and expense.submitted_at < expense.created_at
            ):
                bad_order += 1
            if (
                expense.decided_at
                and expense.submitted_at
                and expense.decided_at < expense.submitted_at
            ):
                bad_order += 1
            if expense.status == "approved" and expense.decided_at is None:
                approved_without_decision += 1
        findings["workflow_ordering_violations"] = bad_order
        findings["approved_without_decision"] = approved_without_decision
        if bad_order:
            problems.append(f"{bad_order} claims have timestamps out of order")
        if approved_without_decision:
            problems.append(f"{approved_without_decision} approved claims have no decision time")

        # --- monetary cross-check against the benchmark annotations ---
        checked = 0
        mismatched = []
        for sample_id, sample in samples.items():
            canonical_receipt = canonical.get(sample_id)
            if canonical_receipt is None:
                continue
            gt = json.loads((dataset_root / sample["ground_truth"]).read_text(encoding="utf-8"))
            cell = gt["fields"]["grand_total"]
            if cell["annotation"] != "verified_value":
                continue
            expected = Decimal(str(cell["value"]))
            receipt_expense = session.get(Expense, canonical_receipt.expense_id)
            actual = receipt_expense.amount if receipt_expense else None
            if actual is None:
                mismatched.append({"sample": sample_id, "expected": str(expected), "actual": None})
            else:
                checked += 1
                if actual != expected:
                    mismatched.append(
                        {"sample": sample_id, "expected": str(expected), "actual": str(actual)}
                    )
        findings["monetary_values_checked"] = checked
        findings["monetary_mismatches"] = mismatched[:20]
        if mismatched:
            problems.append(f"{len(mismatched)} claim amounts disagree with the receipt annotation")

    findings["problems"] = problems
    findings["status"] = "PASS" if not problems else "FAIL"

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(findings, indent=1, default=str), encoding="utf-8"
        )
    else:
        dispose_engine()

    print(json.dumps(findings, indent=1, default=str))
    print("\n" + ("PASS" if not problems else f"FAIL ({len(problems)} problems)"))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
