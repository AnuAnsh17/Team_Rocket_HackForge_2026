"""Integration tests for the corporate demo database.

These run against real PostgreSQL through the project's own fixtures, seed through the real
workflow services, and store receipts through the real private storage abstraction.

A three-sample dataset is built in ``tmp_path`` rather than pointing at the full 250-image
benchmark folder: the full import takes about twenty seconds and writes 250 objects, which
would make the suite slow without testing anything the small set does not already cover.
The full-folder run is a validation script, not a unit test.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from app.core.enums import PolicyReviewState  # noqa: F401  (documents intent in assertions)
from app.models.expense import Expense
from app.models.identity import OrganizationMembership, User
from app.models.organization import AllowanceProfile, Department, OfficeLocation
from app.models.receipt import Receipt
from app.services import corporate_demo_service, demo_service
from app.services.corporate_demo_service import seed_corporate_demo
from app.storage.local import LocalPrivateReceiptStorage
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

BENCHMARK_ROOT = Path.home() / "Desktop" / "ProoflineReceiptBenchmark"
SAMPLE_IDS = ("sample-0101", "sample-0102", "sample-0151")


def _benchmark_available() -> bool:
    return (BENCHMARK_ROOT / "manifest.json").is_file()


requires_benchmark = pytest.mark.skipif(
    not _benchmark_available(), reason="the benchmark dataset folder is not present"
)


@pytest.fixture
def tiny_dataset(tmp_path: Path) -> Path:
    """A three-sample dataset with a real manifest, ground truth and images."""
    manifest = json.loads((BENCHMARK_ROOT / "manifest.json").read_text(encoding="utf-8"))
    by_id = {sample["id"]: sample for sample in manifest["samples"]}
    root = tmp_path / "dataset"
    (root / "images").mkdir(parents=True)
    (root / "ground_truth").mkdir(parents=True)
    kept = []
    for sample_id in SAMPLE_IDS:
        sample = by_id[sample_id]
        for relative in (sample["image"], sample["ground_truth"]):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(BENCHMARK_ROOT / relative, root / relative)
        kept.append(sample)
    manifest["samples"] = kept
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture
def corporate(
    db: Session, tiny_dataset: Path, tmp_path: Path
) -> corporate_demo_service.CorporateSeedResult:
    """Base demo seed plus the corporate extension, inside the test's transaction."""
    demo_service.seed_demo_dataset(db)
    storage = LocalPrivateReceiptStorage(root=tmp_path / "private-receipts")
    return seed_corporate_demo(db, dataset_root=tiny_dataset, storage=storage, duplicate_budget=2)


def _memberships(db: Session) -> list[OrganizationMembership]:
    organization = demo_service._ensure_organization(db)
    return list(
        db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization.id
            )
        )
        .scalars()
        .all()
    )


@requires_benchmark
def test_thirty_accounts_with_complete_profiles(corporate, db: Session) -> None:
    memberships = _memberships(db)
    assert len(memberships) == 30, f"expected 30 accounts, found {len(memberships)}"

    for membership in memberships:
        user = db.get(User, membership.user_id)
        assert user is not None
        assert user.display_name
        assert user.email and user.email.endswith("@proofline-demo.test")
        assert membership.employee_code and membership.employee_code.startswith("PL-")
        assert membership.department_id is not None
        assert membership.office_location_id is not None
        assert membership.cost_center_id is not None
        assert membership.job_grade_id is not None
        assert membership.joined_on is not None

    codes = [m.employee_code for m in memberships]
    assert len(set(codes)) == len(codes), "employee codes must be unique"
    emails = [db.get(User, m.user_id).email for m in memberships]
    assert len(set(emails)) == len(emails), "corporate e-mail addresses must be unique"


@requires_benchmark
def test_structure_spans_departments_and_cities(corporate, db: Session) -> None:
    organization = demo_service._ensure_organization(db)
    departments = db.execute(
        select(func.count())
        .select_from(Department)
        .where(Department.organization_id == organization.id)
    ).scalar_one()
    offices = db.execute(
        select(func.count())
        .select_from(OfficeLocation)
        .where(OfficeLocation.organization_id == organization.id)
    ).scalar_one()
    assert departments >= 8, "the demo company must span several departments"
    assert offices >= 6, "the demo company must span several office locations"

    used_departments = {m.department_id for m in _memberships(db)}
    used_offices = {m.office_location_id for m in _memberships(db)}
    assert len(used_departments) >= 6
    assert len(used_offices) >= 5


@requires_benchmark
def test_every_sample_becomes_a_claim_with_a_readable_receipt(
    corporate, db: Session, tiny_dataset: Path, tmp_path: Path
) -> None:
    organization = demo_service._ensure_organization(db)
    receipts = (
        db.execute(
            select(Receipt).where(
                Receipt.organization_id == organization.id,
                Receipt.parent_receipt_id.is_(None),
            )
        )
        .scalars()
        .all()
    )
    by_sample = {r.original_filename.rsplit(".", 1)[0]: r for r in receipts if r.original_filename}

    for sample_id in SAMPLE_IDS:
        assert sample_id in by_sample, f"{sample_id} has no receipt row"
        receipt = by_sample[sample_id]
        expense = db.get(Expense, receipt.expense_id)
        assert expense is not None, "a receipt must belong to a claim"
        assert expense.organization_id == organization.id

    # The stored bytes must be the benchmark image, byte for byte.
    storage = LocalPrivateReceiptStorage(root=tmp_path / "private-receipts")
    for sample_id in SAMPLE_IDS:
        receipt = by_sample[sample_id]
        data = storage.read(receipt.object_key)
        assert hashlib.sha256(data).hexdigest() == receipt.sha256
        source = tiny_dataset / f"images/public_real/{sample_id}.jpg"
        if source.is_file():
            assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt.sha256


@requires_benchmark
def test_seed_is_idempotent(db: Session, tiny_dataset: Path, tmp_path: Path) -> None:
    demo_service.seed_demo_dataset(db)
    storage = LocalPrivateReceiptStorage(root=tmp_path / "private-receipts")
    seed_corporate_demo(db, dataset_root=tiny_dataset, storage=storage, duplicate_budget=2)

    organization = demo_service._ensure_organization(db)

    def counts() -> tuple[int, int, int, int]:
        return (
            db.execute(
                select(func.count())
                .select_from(Expense)
                .where(Expense.organization_id == organization.id)
            ).scalar_one(),
            db.execute(
                select(func.count())
                .select_from(Receipt)
                .where(Receipt.organization_id == organization.id)
            ).scalar_one(),
            db.execute(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(OrganizationMembership.organization_id == organization.id)
            ).scalar_one(),
            db.execute(
                select(func.count())
                .select_from(AllowanceProfile)
                .where(AllowanceProfile.organization_id == organization.id)
            ).scalar_one(),
        )

    before = counts()
    second = seed_corporate_demo(db, dataset_root=tiny_dataset, storage=storage, duplicate_budget=2)
    after = counts()

    assert before == after, f"a second seed run changed the data: {before} -> {after}"
    assert second.claims_created == 0
    assert second.receipts_created == 0
    assert second.people_created == 0


@requires_benchmark
def test_allowance_profiles_are_demo_only_and_cannot_govern(corporate, db: Session) -> None:
    organization = demo_service._ensure_organization(db)
    profiles = (
        db.execute(
            select(AllowanceProfile).where(AllowanceProfile.organization_id == organization.id)
        )
        .scalars()
        .all()
    )
    assert profiles, "the demo company should ship illustrative allowance profiles"
    for profile in profiles:
        assert "DEMO ONLY" in profile.name.upper()
        assert "FICTIONAL" in profile.name.upper()
        # Draft and unattached: a profile that is neither approved nor bound to a policy
        # version cannot influence a real evaluation.
        assert profile.review_state == "draft"
        assert profile.policy_version_id is None


@requires_benchmark
def test_receipt_content_is_authorized_per_actor(
    client, corporate, db: Session, tmp_path: Path
) -> None:
    """View Bill: the right actor gets the bytes, everyone else gets nothing."""
    organization = demo_service._ensure_organization(db)
    receipts = (
        db.execute(
            select(Receipt)
            .where(
                Receipt.organization_id == organization.id,
                Receipt.parent_receipt_id.is_(None),
            )
            .order_by(Receipt.original_filename)
        )
        .scalars()
        .all()
    )
    assert receipts, "expected seeded receipts"

    target = receipts[0]
    owner = db.get(Expense, target.expense_id).membership_id

    # An employee who does not own the claim must not be able to fetch its content.
    other = next(m for m in _memberships(db) if m.id != owner)
    outsider_headers = {"X-Demo-Actor-Id": str(db.get(User, other.user_id).external_subject)}
    denied = client.get(f"/api/v1/receipts/{target.id}/content", headers=outsider_headers)
    assert denied.status_code in (403, 404), (
        f"an unrelated employee must not read this receipt, got {denied.status_code}"
    )

    # The owner can.
    owner_headers = {
        "X-Demo-Actor-Id": str(
            db.get(User, db.get(OrganizationMembership, owner).user_id).external_subject
        )
    }
    allowed = client.get(f"/api/v1/receipts/{target.id}/content", headers=owner_headers)
    assert allowed.status_code == 200
    assert hashlib.sha256(allowed.content).hexdigest() == target.sha256

    # A finance administrator can, because reviewing requires seeing the bill.
    finance = db.execute(
        select(User)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(
            OrganizationMembership.organization_id == organization.id,
            User.external_subject == demo_service.demo_identity_subject("finance.admin"),
        )
    ).scalar_one()
    finance_headers = {"X-Demo-Actor-Id": str(finance.external_subject)}
    reviewed = client.get(f"/api/v1/receipts/{target.id}/content", headers=finance_headers)
    assert reviewed.status_code == 200
    assert hashlib.sha256(reviewed.content).hexdigest() == target.sha256


@requires_benchmark
def test_view_bill_end_to_end_expense_to_bytes(
    client, corporate, db: Session, tmp_path: Path
) -> None:
    """The full chain: claim -> receipt record -> authorized content -> exact image bytes."""
    organization = demo_service._ensure_organization(db)
    approved = db.execute(
        select(Expense, Receipt)
        .join(Receipt, Receipt.expense_id == Expense.id)
        .where(
            Expense.organization_id == organization.id,
            Expense.status == "approved",
            Receipt.parent_receipt_id.is_(None),
        )
        .order_by(Expense.id)
        .limit(1)
    ).first()
    assert approved is not None, "the demo data should contain an approved claim"
    expense, receipt = approved

    membership = db.get(OrganizationMembership, expense.membership_id)
    user = db.get(User, membership.user_id)
    headers = {"X-Demo-Actor-Id": str(user.external_subject)}

    # The claim is reachable through the endpoint the portal uses.
    detail = client.get(f"/api/v1/expenses/{expense.id}", headers=headers)
    assert detail.status_code == 200, detail.text

    # Its receipt is the one we expect, and the content route returns its exact bytes.
    listed = client.get(f"/api/v1/expenses/{expense.id}/receipts", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    items = body.get("items", body) if isinstance(body, dict) else body
    receipt_ids = {item.get("id") for item in items}
    assert str(receipt.id) in receipt_ids or receipt.id in receipt_ids, (
        "the claim's own receipt must be listed against it"
    )

    content = client.get(f"/api/v1/receipts/{receipt.id}/content", headers=headers)
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/")
    assert hashlib.sha256(content.content).hexdigest() == receipt.sha256, (
        "View Bill must return the stored image itself, not a substitute"
    )


@requires_benchmark
def test_uncertain_receipts_are_never_approved(corporate, db: Session) -> None:
    """Special benchmark cases must stay in review, not be approved to pad a chart."""
    organization = demo_service._ensure_organization(db)
    manifest = json.loads((BENCHMARK_ROOT / "manifest.json").read_text(encoding="utf-8"))
    special = [s["id"] for s in manifest["samples"] if s.get("special_case")]

    for sample_id in special:
        receipt = (
            db.execute(
                select(Receipt).where(
                    Receipt.organization_id == organization.id,
                    Receipt.original_filename.like(f"{sample_id}.%"),
                )
            )
            .scalars()
            .first()
        )
        if receipt is None:
            continue
        expense = db.get(Expense, receipt.expense_id)
        assert expense.status != "approved", (
            f"{sample_id} carries an inconsistent or illegible total and must not be approved"
        )
        assert expense.status in {"in_review", "needs_info", "submitted", "draft"}
