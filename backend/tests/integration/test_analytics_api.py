"""Accuracy, filtering and authorization tests for analytics routes."""

from __future__ import annotations

import uuid

import pytest
from app.core.enums import ExpenseStatus
from app.services import demo_service
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

FROM = "2026-01-01"
TO = "2026-05-31"


def _demo_headers(person_key: str) -> dict[str, str]:
    return {"X-Demo-Actor-Id": demo_service.demo_identity_subject(person_key)}


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


def test_missing_critical_fields_is_date_bounded_and_undated_claims_are_separate(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    """`claims_missing_critical_fields` must never absorb undated claims.

    Pins the result-level half of the completeness semantics. The fixture's `unknown-date` claim
    is both undated and missing a merchant, so it is missing critical fields by the field test
    alone; it must still be excluded from the period metric, because it has no transaction date
    to be in the period with, and reported through `claims_with_unknown_transaction_date`.

    Note on what this can and cannot detect: the metric is always date-bounded, so re-adding
    `expense_date IS NULL` to the field test changes no number and this test cannot fail on it.
    That is why the description is pinned separately by
    tests/contract/test_openapi_contract.py::TestAnalyticsCompletenessMetricSemantics. What this
    test guards is the invariant the query rests on: if the date bound is ever dropped (an
    "all time" mode, say), the period metric would start absorbing undated claims and this is
    what would notice.
    """
    body = client.get(
        "/api/v1/analytics/overview", headers=finance_headers, params=_params()
    ).json()

    undated_claim_id = analytics_dataset["expense_unknown-date"]
    assert undated_claim_id is not None, "sanity: the undated fixture claim exists"

    # Counted - separately, and independently of the period, having no date to fall inside it.
    assert body["claims_with_unknown_transaction_date"] == 1

    # Not part of the period metric. It must stay a subset of the period's claims; if it ever
    # absorbed an undated claim it could exceed claim_count and the two figures on screen would
    # contradict each other.
    assert body["claims_missing_critical_fields"] <= body["claim_count"], (
        "missing-critical-fields must be a subset of the period's claims"
    )
    # The only in-period claim missing a critical field is the dated one missing its amount.
    assert body["claims_missing_critical_fields"] == 1
