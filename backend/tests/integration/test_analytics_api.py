"""Accuracy, filtering and authorization tests for analytics routes."""

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
from app.services import demo_service
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

FROM = "2026-01-01"
TO = "2026-05-31"


def _demo_headers(person_key: str) -> dict[str, str]:
    return {"X-Demo-Actor-Id": demo_service.demo_identity_subject(person_key)}


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


def _params(**values: str) -> dict[str, str]:
    return {"from": FROM, "to": TO, **values}


def test_overview_has_exact_status_currency_month_and_completeness_metrics(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    response = client.get(
        "/api/v1/analytics/overview", headers=_demo_headers("finance.reviewer"), params=_params()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["claim_count"] == 5
    assert body["claims_requiring_review"] == 2
    assert body["claims_needing_information"] == 0
    assert body["claims_missing_critical_fields"] == 1
    assert body["claims_with_uncertain_critical_fields"] == 1
    assert body["claims_with_unknown_transaction_date"] == 1
    assert {row["status"]: row["claim_count"] for row in body["status_counts"]} == {
        status.value: int(
            status
            in {
                ExpenseStatus.APPROVED,
                ExpenseStatus.SUBMITTED,
                ExpenseStatus.REJECTED,
                ExpenseStatus.IN_REVIEW,
                ExpenseStatus.DRAFT,
            }
        )
        for status in ExpenseStatus
    }
    amounts = {(row["status"], row["currency"]): row for row in body["status_amounts"]}
    assert amounts[("approved", "INR")]["amount_total"] == "100.1000"
    assert amounts[("submitted", "USD")]["amount_total"] == "200.2000"
    assert amounts[("draft", None)]["amount_total"] is None
    monthly = {(row["month"], row["currency"]): row for row in body["monthly_totals"]}
    assert monthly[("2026-01-01", "INR")]["amount_total"] == "100.1000"
    assert monthly[("2026-02-01", "USD")]["amount_total"] == "200.2000"
    assert monthly[("2026-03-01", "INR")]["amount_total"] == "300.0000"
    assert monthly[("2026-04-01", "INR")]["amount_total"] == "400.0000"
    assert monthly[("2026-05-01", None)]["amount_total"] is None
    assert not any(row["month"] == "2026-06-01" for row in body["monthly_totals"])
    approved_group = [
        row
        for row in body["by_department"]
        if row["currency"] == "INR"
        and row["department_id"] == str(analytics_dataset["department_id"])
    ]
    assert len(approved_group) == 1
    assert approved_group[0]["amount_total"] == "500.1000"
    assert approved_group[0]["claim_count"] == 2
    assert body["claim_count"] < 6  # other organization's 999999.99 never leaks in


def test_spend_filters_are_inclusive_and_group_by_supported_dimensions(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    headers = finance_headers
    response = client.get(
        "/api/v1/analytics/spend",
        headers=headers,
        params=_params(
            group_by="category",
            currency="INR",
            department_id=str(analytics_dataset["department_id"]),
        ),
    )
    assert response.status_code == 200, response.text
    rows = response.json()["results"]["items"]
    assert {(row["category"], row["currency"], row["amount_total"]) for row in rows} == {
        ("meal", "INR", "100.1000"),
        ("office_supplies", "INR", "400.0000"),
    }
    boundary = client.get(
        "/api/v1/analytics/spend",
        headers=headers,
        params={"from": "2026-01-15", "to": "2026-01-15", "group_by": "status"},
    )
    assert boundary.status_code == 200
    assert boundary.json()["results"]["items"][0]["amount_total"] == "100.1000"


@pytest.mark.parametrize(
    ("group_by", "dimension_field"),
    (("department", "department_id"), ("location", "office_location_id"), ("status", "status")),
)
def test_spend_supports_department_location_and_status_groups(
    client: TestClient,
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
    group_by: str,
    dimension_field: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(group_by=group_by),
    )
    assert response.status_code == 200, response.text
    rows = response.json()["results"]["items"]
    assert rows
    assert all(row[dimension_field] is not None for row in rows)
    assert sum(row["claim_count"] for row in rows) == 5

    employee_filter = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(
            group_by="employee",
            employee_membership_id=str(analytics_dataset["asha_membership_id"]),
        ),
    )
    assert employee_filter.status_code == 200, employee_filter.text
    employee_rows = employee_filter.json()["results"]["items"]
    assert employee_rows
    assert {row["employee_membership_id"] for row in employee_rows} == {
        str(analytics_dataset["asha_membership_id"])
    }
    assert sum(row["claim_count"] for row in employee_rows) == 2


def test_group_pagination_and_employee_detail_scope(
    client: TestClient,
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
) -> None:
    first = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(group_by="month", limit="2"),
    )
    assert first.status_code == 200
    page = first.json()["results"]
    assert page["page"]["total"] == 5
    assert page["page"]["next_cursor"]
    second = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(group_by="month", limit="2", cursor=page["page"]["next_cursor"]),
    )
    assert second.status_code == 200
    assert not {row["bucket_start"] for row in page["items"]} & {
        row["bucket_start"] for row in second.json()["results"]["items"]
    }
    assert (
        client.get(
            "/api/v1/analytics/spend",
            headers=_demo_headers("finance.reviewer"),
            params=_params(group_by="employee"),
        ).status_code
        == 403
    )
    employee_rows = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(group_by="employee"),
    )
    assert employee_rows.status_code == 200
    assert all(row["employee_membership_id"] for row in employee_rows.json()["results"]["items"])


def test_date_range_empty_period_validation_and_unknown_dates(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    empty = client.get(
        "/api/v1/analytics/overview",
        headers=finance_headers,
        params={"from": "2030-01-01", "to": "2030-01-31"},
    )
    assert empty.status_code == 200
    assert empty.json()["claim_count"] == 0
    assert all(row["claim_count"] == 0 for row in empty.json()["status_counts"])
    assert empty.json()["monthly_totals"] == []
    assert empty.json()["claims_with_unknown_transaction_date"] == 1

    reversed_range = client.get(
        "/api/v1/analytics/overview",
        headers=finance_headers,
        params={"from": "2026-06-01", "to": "2026-01-01"},
    )
    assert reversed_range.status_code == 422
    assert (
        client.get(
            "/api/v1/analytics/spend",
            headers=finance_headers,
            params=_params(group_by="paid"),
        ).status_code
        == 422
    )


def test_invalid_dimension_ids_and_tenant_filters_are_rejected(
    client: TestClient,
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
) -> None:
    foreign_department = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(
            group_by="department", department_id=str(analytics_dataset["foreign_department_id"])
        ),
    )
    assert foreign_department.status_code == 422
    foreign_membership = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(employee_membership_id=str(analytics_dataset["foreign_membership_id"])),
    )
    assert foreign_membership.status_code == 422
    invalid_uuid = client.get(
        "/api/v1/analytics/spend",
        headers=finance_headers,
        params=_params(office_location_id="not-a-uuid"),
    )
    assert invalid_uuid.status_code == 422


def test_analytics_permission_matrix_and_authentication(
    client: TestClient,
    employee_headers: dict[str, str],
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
) -> None:
    params = _params()
    assert client.get("/api/v1/analytics/overview", params=params).status_code == 401
    assert (
        client.get(
            "/api/v1/analytics/overview", headers=employee_headers, params=params
        ).status_code
        == 403
    )
    for person in ("manager.priya", "hr.reviewer", "org.admin", "policy.admin"):
        response = client.get(
            "/api/v1/analytics/overview", headers=_demo_headers(person), params=params
        )
        assert response.status_code == 403, person
    assert (
        client.get(
            "/api/v1/analytics/overview", headers=_demo_headers("finance.reviewer"), params=params
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/analytics/overview", headers=_demo_headers("auditor"), params=params
        ).status_code
        == 200
    )
    employee_filter = {
        **params,
        "employee_membership_id": str(analytics_dataset["asha_membership_id"]),
    }
    assert (
        client.get(
            "/api/v1/analytics/overview",
            headers=_demo_headers("finance.reviewer"),
            params=employee_filter,
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/analytics/overview", headers=finance_headers, params=employee_filter
        ).status_code
        == 200
    )
