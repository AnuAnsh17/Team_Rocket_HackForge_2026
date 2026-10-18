"""Shared fixtures for integration tests that need the analytics dataset.

The dataset is defined once here rather than per module: `GET /analytics/spend` and
`GET /analytics/spend-matrix` are asserted against the *same* synthetic rows, including
the consistency test that sums the matrix back to the single-dimension totals. A second,
independently written dataset would let the two endpoints agree with each other's tests
while disagreeing in production.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.enums import (
    DerivationType,
    ExpenseFieldName,
    ExpenseStatus,
    ExtractionStatus,
    FieldSource,
    MembershipStatus,
    StorageBackend,
)
from app.models.expense import Expense, ExpenseFieldEvidence
from app.models.identity import OrganizationMembership, User
from app.models.organization import Department, Organization
from app.models.receipt import ExtractionRun, Receipt
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def analytics_dataset(db: Session, seeded: dict[str, object]) -> dict[str, uuid.UUID]:
    org_id = db.execute(select(Organization.id)).scalar_one()

    def membership(display_prefix: str) -> OrganizationMembership:
        return db.execute(
            select(OrganizationMembership)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(User.display_name.startswith(display_prefix))
        ).scalar_one()

    asha = membership("Asha Menon")
    rohit = membership("Rohit Verma")
    nisha = membership("Nisha Kapoor")
    vikram = membership("Vikram Das")
    leela = membership("Leela Sen")
    engineering = db.execute(
        select(Department.id).where(Department.organization_id == org_id, Department.code == "ENG")
    ).scalar_one()

    specs = (
        ("approved-inr", asha, ExpenseStatus.APPROVED, date(2026, 1, 15), "100.10", "INR", "meal"),
        (
            "submitted-usd",
            asha,
            ExpenseStatus.SUBMITTED,
            date(2026, 2, 10),
            "200.20",
            "USD",
            "local_transport",
        ),
        ("rejected-inr", rohit, ExpenseStatus.REJECTED, date(2026, 3, 31), "300.00", "INR", "meal"),
        (
            "review-inr",
            nisha,
            ExpenseStatus.IN_REVIEW,
            date(2026, 4, 1),
            "400.00",
            "INR",
            "office_supplies",
        ),
        ("missing-amount", leela, ExpenseStatus.DRAFT, date(2026, 5, 31), None, None, None),
        ("unknown-date", vikram, ExpenseStatus.NEEDS_INFO, None, "50.00", "INR", "meal"),
    )
    expenses: dict[str, Expense] = {}
    for key, owner, status, expense_date, amount, currency, category in specs:
        row = Expense(
            id=uuid.uuid4(),
            organization_id=org_id,
            membership_id=owner.id,
            channel="web",
            status=status.value,
            version=1,
            merchant=None if key == "unknown-date" else f"Synthetic {key}",
            expense_date=expense_date,
            amount=Decimal(amount) if amount is not None else None,
            currency=currency,
            category=category,
            created_by_user_id=owner.user_id,
        )
        db.add(row)
        expenses[key] = row
    db.flush()

    # One expense has multiple receipts and extraction runs. The analytics queries
    # must still count and sum the parent expense exactly once.
    for index in range(2):
        receipt_id = uuid.uuid4()
        receipt = Receipt(
            id=receipt_id,
            organization_id=org_id,
            expense_id=expenses["approved-inr"].id,
            storage_backend=StorageBackend.LOCAL.value,
            object_key=f"analytics-fixture/{receipt_id}.png",
            original_filename=f"synthetic-{index}.png",
            detected_mime_type="image/png",
            declared_mime_type="image/png",
            byte_size=20,
            sha256=hashlib.sha256(f"synthetic-{index}".encode()).hexdigest(),
            derivation_type=DerivationType.ORIGINAL.value,
            extraction_status=ExtractionStatus.PENDING.value,
            uploaded_by_user_id=asha.user_id,
        )
        db.add(receipt)
        db.flush()
        db.add(
            ExtractionRun(
                id=uuid.uuid4(),
                receipt_id=receipt.id,
                provider="test-fixture",
                status=ExtractionStatus.PENDING.value,
                attempt_count=0,
                created_by_user_id=asha.user_id,
            )
        )
    db.add(
        ExpenseFieldEvidence(
            id=uuid.uuid4(),
            expense_id=expenses["approved-inr"].id,
            expense_version=1,
            field_name=ExpenseFieldName.MERCHANT.value,
            source=FieldSource.EMPLOYEE_INPUT.value,
            is_current=True,
            reviewed=False,
            uncertainty_reason="Synthetic fixture marks the merchant for review.",
            created_by_user_id=asha.user_id,
        )
    )

    other_org_id = uuid.uuid4()
    other_org = Organization(
        id=other_org_id,
        name="Analytics Other Tenant",
        slug=f"analytics-other-{other_org_id.hex[:12]}",
        is_demo=False,
        is_active=True,
    )
    other_user = User(id=uuid.uuid4(), display_name="Other Tenant Employee", is_active=True)
    db.add_all((other_org, other_user))
    db.flush()
    other_department = Department(
        id=uuid.uuid4(),
        organization_id=other_org_id,
        code="OTHER",
        name="Other Tenant Department",
        is_active=True,
    )
    db.add(other_department)
    db.flush()
    other_membership = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=other_org_id,
        user_id=other_user.id,
        status=MembershipStatus.ACTIVE.value,
        department_id=other_department.id,
        is_primary=True,
    )
    db.add(other_membership)
    db.flush()
    db.add(
        Expense(
            id=uuid.uuid4(),
            organization_id=other_org_id,
            membership_id=other_membership.id,
            channel="web",
            status=ExpenseStatus.APPROVED.value,
            version=1,
            merchant="Other tenant expense",
            expense_date=date(2026, 1, 15),
            amount=Decimal("999999.99"),
            currency="INR",
            category="meal",
            created_by_user_id=other_user.id,
        )
    )
    db.flush()
    return {
        "organization_id": org_id,
        "department_id": engineering,
        "asha_membership_id": asha.id,
        "foreign_department_id": other_department.id,
        "foreign_membership_id": other_membership.id,
        **{f"expense_{key}": row.id for key, row in expenses.items()},
    }
