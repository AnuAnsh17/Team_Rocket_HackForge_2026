"""Two-dimensional spend matrix: exactness, scoping and consistency with /spend.

The consistency test is the point of these tests. A matrix that agrees with itself but
disagrees with `GET /analytics/spend` would be a second, silently different definition
of spend. Summing the matrix over one dimension must reproduce the corresponding
single-dimension row exactly, per currency, for the same period and filters.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest
from app.core.enums import ExpenseStatus
from app.models.expense import Expense
from app.services import demo_service
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

FROM = "2026-01-01"
TO = "2026-05-31"
MATRIX = "/api/v1/analytics/spend-matrix"
SPEND = "/api/v1/analytics/spend"

# A status the fixture never uses. Analytics must not materialise it as a zero bucket.
UNUSED_STATUS = ExpenseStatus.WITHDRAWN.value


def _demo_headers(person_key: str) -> dict[str, str]:
    return {"X-Demo-Actor-Id": demo_service.demo_identity_subject(person_key)}


def _params(**values: str) -> dict[str, str]:
    return {"from": FROM, "to": TO, **values}


def test_matrix_returns_one_row_per_bucket_pair_and_currency(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    response = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(primary="month", secondary="department"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["primary"] == "month"
    assert body["secondary"] == "department"
    assert body["from_date"] == FROM
    assert body["to_date"] == TO
    assert body["claims_with_unknown_transaction_date"] == 1

    items = body["results"]["items"]
    # One row per (primary, secondary, currency): no combination is duplicated and no
    # currency is folded into another.
    cells = [(row["primary_key"], row["secondary_key"], row["currency"]) for row in items]
    assert len(set(cells)) == len(items)
    assert sum(row["claim_count"] for row in items) == 5

    january = next(row for row in items if row["primary_key"] == "2026-01-01")
    assert january["bucket_start"] == "2026-01-01"
    assert january["secondary_key"] == str(analytics_dataset["department_id"])
    assert january["department_id"] == str(analytics_dataset["department_id"])
    assert january["department_name"] == "Engineering (synthetic)"
    assert january["currency"] == "INR"
    assert january["claim_count"] == 1
    assert january["amount_claim_count"] == 1
    assert january["amount_total"] == "100.1000"

    # Descriptor fields for the dimensions that were NOT requested stay null: the
    # department value is never echoed into the location, category, employee or status
    # fields.
    assert january["office_location_id"] is None
    assert january["office_location_name"] is None
    assert january["category"] is None
    assert january["employee_membership_id"] is None
    assert january["employee_display_name"] is None
    assert january["status"] is None


def test_matrix_keeps_two_currencies_in_a_single_bucket_as_separate_rows(
    client: TestClient,
    db: Session,
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
) -> None:
    """Currency is a dimension of the row, never combined inside a bucket."""
    # February already holds Asha's USD claim. Adding an INR claim for the same person
    # and month makes one (month, department) bucket provably hold two currencies.
    db.add(
        Expense(
            id=uuid.uuid4(),
            organization_id=analytics_dataset["organization_id"],
            membership_id=analytics_dataset["asha_membership_id"],
            channel="web",
            status=ExpenseStatus.APPROVED.value,
            version=1,
            merchant="Synthetic matrix second currency",
            expense_date=date(2026, 2, 20),
            amount=Decimal("77.77"),
            currency="INR",
            category="meal",
            created_by_user_id=None,
        )
    )
    db.flush()

    body = client.get(
        MATRIX, headers=finance_headers, params=_params(primary="month", secondary="category")
    ).json()
    rows = body["results"]["items"]
    assert [
        (row["primary_key"], row["secondary_key"], row["currency"], row["amount_total"])
        for row in rows
    ] == [
        ("2026-01-01", "meal", "INR", "100.1000"),
        ("2026-02-01", "local_transport", "USD", "200.2000"),
        ("2026-02-01", "meal", "INR", "77.7700"),
        ("2026-03-01", "meal", "INR", "300.0000"),
        ("2026-04-01", "office_supplies", "INR", "400.0000"),
        ("2026-05-01", "__unassigned__", None, None),
    ]
    february = [row for row in rows if row["primary_key"] == "2026-02-01"]
    assert len(february) == 2
    assert {row["currency"] for row in february} == {"INR", "USD"}
    assert sum(row["amount_claim_count"] for row in february) == 2

    # A currency filter narrows the rows; it does not change what a row means.
    filtered = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(primary="month", secondary="category", currency="INR"),
    ).json()["results"]["items"]
    assert {row["currency"] for row in filtered} == {"INR"}
    assert "local_transport" not in {row["secondary_key"] for row in filtered}


def test_matrix_excludes_and_counts_claims_without_a_transaction_date(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    body = client.get(
        MATRIX, headers=finance_headers, params=_params(primary="status", secondary="month")
    ).json()
    # The fixture's undated claim is real and matches the filters, so it is reported
    # once - and only once, outside every bucket.
    assert body["claims_with_unknown_transaction_date"] == 1
    items = body["results"]["items"]
    assert sum(row["claim_count"] for row in items) == 5
    assert UNUSED_STATUS not in {row["primary_key"] for row in items}
    assert "needs_info" not in {row["primary_key"] for row in items}
    assert all(row["bucket_start"] is not None for row in items)


def test_matrix_date_filter_is_inclusive_on_both_boundaries(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    lower = client.get(
        MATRIX,
        headers=finance_headers,
        params={
            "from": "2026-01-15",
            "to": "2026-01-15",
            "primary": "month",
            "secondary": "category",
        },
    )
    assert lower.status_code == 200, lower.text
    assert [
        (row["primary_key"], row["amount_total"], row["claim_count"])
        for row in lower.json()["results"]["items"]
    ] == [("2026-01-01", "100.1000", 1)]

    upper = client.get(
        MATRIX,
        headers=finance_headers,
        params={
            "from": "2026-05-31",
            "to": "2026-05-31",
            "primary": "month",
            "secondary": "category",
        },
    )
    assert upper.status_code == 200, upper.text
    assert [
        (row["primary_key"], row["claim_count"], row["amount_total"], row["currency"])
        for row in upper.json()["results"]["items"]
    ] == [("2026-05-01", 1, None, None)]


def test_matrix_omits_empty_buckets_instead_of_fabricating_zero_rows(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    body = client.get(
        MATRIX,
        headers=finance_headers,
        params={
            "from": "2026-01-01",
            "to": "2026-12-31",
            "primary": "month",
            "secondary": "status",
        },
    ).json()
    items = body["results"]["items"]
    statuses = {row["secondary_key"] for row in items}
    months = {row["primary_key"] for row in items}
    # A canonical status no claim holds must not appear as a zero row, and a month with
    # no dated claims must be absent rather than present-with-zeroes.
    assert UNUSED_STATUS not in statuses
    assert statuses == {"approved", "submitted", "rejected", "in_review", "draft"}
    assert months == {"2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"}

    empty = client.get(
        MATRIX,
        headers=finance_headers,
        params={
            "from": "2030-01-01",
            "to": "2030-03-31",
            "primary": "month",
            "secondary": "department",
        },
    ).json()
    assert empty["results"]["items"] == []
    assert empty["results"]["page"]["total"] == 0
    assert empty["results"]["page"]["next_cursor"] is None


def test_matrix_ordering_is_deterministic_and_chronological_on_the_month_axis(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    params = _params(primary="category", secondary="month")
    items = client.get(MATRIX, headers=finance_headers, params=params).json()["results"]["items"]
    # Ordered by primary key (null bucket first, then the key), then the second
    # dimension, then currency.
    assert [(row["primary_key"], row["secondary_key"]) for row in items] == [
        ("__unassigned__", "2026-05-01"),
        ("local_transport", "2026-02-01"),
        ("meal", "2026-01-01"),
        ("meal", "2026-03-01"),
        ("office_supplies", "2026-04-01"),
    ]
    meals = [row["secondary_key"] for row in items if row["primary_key"] == "meal"]
    assert meals == sorted(meals), "the month axis must be chronological, not incidental"

    repeat = client.get(MATRIX, headers=finance_headers, params=params).json()["results"]["items"]
    assert repeat == items, "identical requests must produce an identically ordered page"


def test_matrix_pagination_envelope_and_second_page(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    first = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(primary="month", secondary="category", limit="2"),
    ).json()["results"]
    assert first["page"]["limit"] == 2
    assert first["page"]["total"] == 5
    assert first["page"]["next_cursor"]
    assert len(first["items"]) == 2

    second = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(
            primary="month", secondary="category", limit="2", cursor=first["page"]["next_cursor"]
        ),
    ).json()["results"]
    assert second["page"]["total"] == 5
    first_cells = {(r["primary_key"], r["secondary_key"], r["currency"]) for r in first["items"]}
    second_cells = {(r["primary_key"], r["secondary_key"], r["currency"]) for r in second["items"]}
    assert not first_cells & second_cells, "pages must not repeat a cell"

    third = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(
            primary="month", secondary="category", limit="2", cursor=second["page"]["next_cursor"]
        ),
    ).json()["results"]
    assert len(third["items"]) == 1
    assert third["page"]["next_cursor"] is None

    # The pages partition the matrix: the cursor is meaningful only because the order is.
    assert len(first["items"] + second["items"] + third["items"]) == first["page"]["total"]

    assert (
        client.get(
            MATRIX,
            headers=finance_headers,
            params=_params(primary="month", secondary="category", limit="201"),
        ).status_code
        == 422
    )


def test_matrix_rejects_identical_or_unknown_dimensions_and_reversed_ranges(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    identical = client.get(
        MATRIX, headers=finance_headers, params=_params(primary="month", secondary="month")
    )
    assert identical.status_code == 422, identical.text
    assert (
        client.get(
            MATRIX, headers=finance_headers, params=_params(primary="month", secondary="paid")
        ).status_code
        == 422
    )
    assert (
        client.get(MATRIX, headers=finance_headers, params=_params(primary="month")).status_code
        == 422
    )
    assert (
        client.get(
            MATRIX,
            headers=finance_headers,
            params={
                "from": "2026-06-01",
                "to": "2026-01-01",
                "primary": "month",
                "secondary": "department",
            },
        ).status_code
        == 422
    )
    # A degenerate matrix is a malformed request, so it is reported as such even for a
    # caller who could not have been granted employee-level access: the request is
    # unserviceable before it is unauthorized.
    assert (
        client.get(
            MATRIX,
            headers=_demo_headers("finance.reviewer"),
            params=_params(primary="employee", secondary="employee"),
        ).status_code
        == 422
    )


def test_matrix_authentication_and_employee_dimension_authorization(
    client: TestClient,
    employee_headers: dict[str, str],
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
) -> None:
    params = _params(primary="month", secondary="department")
    assert client.get(MATRIX, params=params).status_code == 401
    assert client.get(MATRIX, headers=employee_headers, params=params).status_code == 403
    for person in ("manager.priya", "hr.reviewer", "org.admin", "policy.admin"):
        assert (
            client.get(MATRIX, headers=_demo_headers(person), params=params).status_code == 403
        ), person
    # finance.reviewer holds analytics:read; that is enough for aggregates.
    assert (
        client.get(MATRIX, headers=_demo_headers("finance.reviewer"), params=params).status_code
        == 200
    )

    # Employee as either axis is employee-level analytics, so the 403 cannot be dodged by
    # putting the employee dimension on the second axis.
    employee_filter = {
        **_params(primary="month", secondary="department"),
        "employee_membership_id": str(analytics_dataset["asha_membership_id"]),
    }
    for dims in (
        {"primary": "employee", "secondary": "department"},
        {"primary": "department", "secondary": "employee"},
    ):
        assert (
            client.get(
                MATRIX,
                headers=_demo_headers("finance.reviewer"),
                params=_params(**dims),
            ).status_code
            == 403
        ), dims
        authorized = client.get(MATRIX, headers=finance_headers, params=_params(**dims))
        assert authorized.status_code == 200, dims
        assert all(row["employee_membership_id"] for row in authorized.json()["results"]["items"])
        # The auditor holds analytics:read_org, so employee dimensions succeed for it.
        assert (
            client.get(MATRIX, headers=_demo_headers("auditor"), params=_params(**dims)).status_code
            == 200
        ), dims

    # Employee-membership filtering is employee-level too, exactly as in spend.
    assert (
        client.get(
            MATRIX, headers=_demo_headers("finance.reviewer"), params=employee_filter
        ).status_code
        == 403
    )
    assert client.get(MATRIX, headers=finance_headers, params=employee_filter).status_code == 200


def test_matrix_rejects_foreign_dimension_ids_and_never_leaks_another_tenant(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    assert (
        client.get(
            MATRIX,
            headers=finance_headers,
            params=_params(
                primary="month",
                secondary="department",
                department_id=str(analytics_dataset["foreign_department_id"]),
            ),
        ).status_code
        == 422
    )
    assert (
        client.get(
            MATRIX,
            headers=finance_headers,
            params=_params(
                primary="month",
                secondary="department",
                employee_membership_id=str(analytics_dataset["foreign_membership_id"]),
            ),
        ).status_code
        == 422
    )
    body = client.get(
        MATRIX, headers=finance_headers, params=_params(primary="month", secondary="category")
    ).json()
    assert sum(row["claim_count"] for row in body["results"]["items"]) == 5
    assert all(
        (row["amount_total"] is None) or (Decimal(row["amount_total"]) < Decimal("1000000"))
        for row in body["results"]["items"]
    )


@pytest.mark.parametrize("secondary", ["category", "status", "employee", "department"])
def test_matrix_sums_reproduce_the_single_dimension_spend_rows_per_currency(
    client: TestClient,
    finance_headers: dict[str, str],
    analytics_dataset: dict[str, uuid.UUID],
    secondary: str,
) -> None:
    """The divergence guard: the matrix must be a re-partition of `spend`, not a rival.

    Summing the matrix rows for a month across the other dimension, per currency, must
    equal the corresponding `spend` row's `amount_total` and `claim_count` for the same
    month. Any drift in the group expressions, the date bound, or the money handling
    shows up here as a failing sum.
    """
    matrix = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(primary="month", secondary=secondary, limit="200"),
    ).json()
    spend = client.get(
        SPEND, headers=finance_headers, params=_params(group_by="month", limit="200")
    ).json()

    assert (
        matrix["claims_with_unknown_transaction_date"]
        == (spend["claims_with_unknown_transaction_date"])
    )
    assert matrix["results"]["page"]["total"] == len(matrix["results"]["items"])

    claim_counts: dict[tuple[object, object], int] = defaultdict(int)
    amount_totals: dict[tuple[object, object], Decimal] = defaultdict(Decimal)
    has_amount: dict[tuple[object, object], bool] = defaultdict(bool)
    for row in matrix["results"]["items"]:
        key = (row["bucket_start"], row["currency"])
        claim_counts[key] += row["claim_count"]
        if row["amount_total"] is not None:
            amount_totals[key] += Decimal(row["amount_total"])
            has_amount[key] = True

    spend_rows = {(row["bucket_start"], row["currency"]): row for row in spend["results"]["items"]}
    assert set(claim_counts) == set(spend_rows), (
        "the matrix must cover exactly the (month, currency) cells spend reports"
    )
    for key, spend_row in spend_rows.items():
        assert claim_counts[key] == spend_row["claim_count"], key
        if spend_row["amount_total"] is None:
            assert has_amount[key] is False, key
        else:
            assert amount_totals[key] == Decimal(spend_row["amount_total"]), key
            assert has_amount[key] is True, key

    assert sum(row["claim_count"] for row in matrix["results"]["items"]) == sum(
        row["claim_count"] for row in spend["results"]["items"]
    )


def test_matrix_sums_match_spend_under_a_department_and_currency_filter(
    client: TestClient, finance_headers: dict[str, str], analytics_dataset: dict[str, uuid.UUID]
) -> None:
    filters = {
        "currency": "INR",
        "department_id": str(analytics_dataset["department_id"]),
    }
    matrix = client.get(
        MATRIX,
        headers=finance_headers,
        params=_params(primary="month", secondary="category", **filters),
    ).json()
    spend = client.get(
        SPEND, headers=finance_headers, params=_params(group_by="month", **filters)
    ).json()

    claim_counts: dict[object, int] = defaultdict(int)
    amount_totals: dict[object, Decimal] = defaultdict(Decimal)
    for row in matrix["results"]["items"]:
        key = row["bucket_start"]
        claim_counts[key] += row["claim_count"]
        if row["amount_total"] is not None:
            amount_totals[key] += Decimal(row["amount_total"])

    spend_rows = {row["bucket_start"]: row for row in spend["results"]["items"]}
    assert spend_rows, "sanity: the filtered period must contain the engineering INR claims"
    assert set(claim_counts) == set(spend_rows)
    for month, spend_row in spend_rows.items():
        assert claim_counts[month] == spend_row["claim_count"], month
        assert amount_totals[month] == Decimal(spend_row["amount_total"]), month
