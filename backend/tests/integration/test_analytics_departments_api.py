"""Department analytics: the response must equal the stored records.

The assertion that matters here is not "the numbers look sensible" - it is that every
figure the endpoint returns can be recomputed from the database by an independent query
and comes out identical. A polished dashboard backed by a wrong aggregation is still a
broken dashboard, so each test recomputes its expectation in raw SQL rather than calling
the service again (which would only prove the service agrees with itself).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

URL = "/api/v1/analytics/departments"
WINDOW = "from=2026-01-01&to=2026-12-31"

# Recomputes the department breakdown from the tables, independently of the service.
DEPARTMENT_SQL = text(
    """
    SELECT d.id AS department_id,
           d.name AS department_name,
           e.currency AS currency,
           count(*) AS claim_count,
           count(e.amount) AS amount_claim_count,
           sum(e.amount) AS amount_total,
           count(*) FILTER (WHERE e.status = 'approved') AS approved_claim_count,
           sum(e.amount) FILTER (WHERE e.status = 'approved') AS approved_amount_total,
           count(*) FILTER (WHERE e.status IN ('submitted', 'in_review')) AS pending_review_count,
           count(*) FILTER (WHERE e.status = 'rejected') AS rejected_count,
           count(*) FILTER (WHERE e.status = 'needs_info') AS needs_info_count,
           count(*) FILTER (WHERE e.status = 'draft') AS draft_count
      FROM expenses e
      JOIN organization_memberships m ON m.id = e.membership_id
      LEFT JOIN departments d
             ON d.id = m.department_id AND d.organization_id = e.organization_id
     WHERE e.organization_id = :org
       AND e.expense_date >= :from_date
       AND e.expense_date <= :to_date
     GROUP BY d.id, d.name, e.currency
    """
)


def _stored_rows(db: Session, organization_id) -> dict[tuple[object, object], dict]:
    rows = db.execute(
        DEPARTMENT_SQL, {"org": organization_id, "from_date": "2026-01-01", "to_date": "2026-12-31"}
    ).mappings()
    return {(row["department_id"], row["currency"]): dict(row) for row in rows}


def _response(client, headers) -> dict:
    response = client.get(f"{URL}?{WINDOW}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _organization_id(db: Session):
    return db.execute(text("SELECT id FROM organizations LIMIT 1")).scalar_one()


def _by_bucket(rows: list[dict]) -> dict[tuple[str | None, str | None], dict]:
    """Key rows by (department id as text, currency) so JSON and UUID forms compare."""
    return {
        (str(row["department_id"]) if row["department_id"] else None, row["currency"]): row
        for row in rows
    }


def test_every_row_equals_an_independent_sql_aggregate(
    client, db: Session, finance_headers, analytics_dataset
) -> None:
    """The core check: API figures == raw SQL figures, per department and currency."""
    body = _response(client, finance_headers)
    stored = _stored_rows(db, _organization_id(db))

    reported = _by_bucket(body["departments"])
    expected_rows = _by_bucket(list(stored.values()))
    assert set(reported) == set(expected_rows), (
        "the endpoint and the database disagree on which buckets exist"
    )

    for key, expected in expected_rows.items():
        row = reported[key]
        assert row["claim_count"] == expected["claim_count"]
        assert row["amount_claim_count"] == expected["amount_claim_count"]
        assert row["approved_claim_count"] == expected["approved_claim_count"]
        assert row["pending_review_count"] == expected["pending_review_count"]
        assert row["rejected_count"] == expected["rejected_count"]
        assert row["needs_info_count"] == expected["needs_info_count"]
        assert row["draft_count"] == expected["draft_count"]
        assert row["department_name"] == expected["department_name"]
        # Exact decimal equality, as strings - not a tolerance. A bucket with no amount
        # must report null rather than zero.
        for field in ("amount_total", "approved_amount_total"):
            if expected[field] is None:
                assert row[field] is None, (key, field)
            else:
                assert Decimal(row[field]) == Decimal(expected[field]), (key, field)


def test_totals_are_exactly_the_sum_of_the_department_rows(
    client, finance_headers, analytics_dataset
) -> None:
    """``departments`` decomposes ``totals``; a consumer must never have to add rows up."""
    body = _response(client, finance_headers)
    by_currency: dict[object, dict] = {}
    for row in body["departments"]:
        bucket = by_currency.setdefault(
            row["currency"], {"claim_count": 0, "amount_total": Decimal("0")}
        )
        bucket["claim_count"] += row["claim_count"]
        bucket["amount_total"] += Decimal(row["amount_total"] or "0")

    for total in body["totals"]:
        bucket = by_currency[total["currency"]]
        assert total["claim_count"] == bucket["claim_count"]
        assert Decimal(total["amount_total"] or "0") == bucket["amount_total"]


def test_requested_shares_sum_to_one_per_currency(
    client, finance_headers, analytics_dataset
) -> None:
    body = _response(client, finance_headers)
    shares: dict[str, Decimal] = {}
    for row in body["departments"]:
        if row["currency"] is None:
            # A bucket with no currency has no currency total to be a share of.
            assert row["requested_share"] is None
            continue
        shares[row["currency"]] = shares.get(row["currency"], Decimal("0")) + Decimal(
            row["requested_share"]
        )
    assert shares, "the fixture must contain at least one currency"
    for currency, total in shares.items():
        # Four decimal places of rounding per row, so allow the accumulated rounding only.
        assert abs(total - Decimal("1")) <= Decimal("0.001"), (currency, total)


def test_approved_expenditure_never_exceeds_requested(
    client, finance_headers, analytics_dataset
) -> None:
    """Approval is a workflow state and a subset of requested spend, never a payment."""
    for row in _response(client, finance_headers)["departments"]:
        assert row["approved_claim_count"] <= row["claim_count"]
        approved = Decimal(row["approved_amount_total"] or "0")
        assert approved <= Decimal(row["amount_total"] or "0")


def test_undated_claims_are_excluded_from_rows_and_counted_separately(
    client, db: Session, finance_headers, analytics_dataset
) -> None:
    """The fixture's ``unknown-date`` claim has an amount and no transaction date.

    It must be counted once and appear in no bucket: an undated claim is unknown, not
    zero spend in the first month, and not swappable into the period total.
    """
    body = _response(client, finance_headers)
    assert body["claims_with_unknown_transaction_date"] == 1

    organization_id = _organization_id(db)
    in_range = db.execute(
        text(
            "SELECT COALESCE(sum(amount), 0) FROM expenses WHERE organization_id = :org "
            "AND expense_date >= :from_date AND expense_date <= :to_date"
        ),
        {"org": organization_id, "from_date": "2026-01-01", "to_date": "2026-12-31"},
    ).scalar_one()
    all_dated_and_undated = db.execute(
        text("SELECT COALESCE(sum(amount), 0) FROM expenses WHERE organization_id = :org"),
        {"org": organization_id},
    ).scalar_one()

    reported = sum(Decimal(row["amount_total"] or "0") for row in body["departments"])
    assert reported == Decimal(in_range)
    # The undated claim's 50.00 is stored but is not in the period total.
    assert Decimal(all_dated_and_undated) - Decimal(in_range) == Decimal("50.00")


def test_a_claim_without_an_amount_is_counted_but_is_not_zero_money(
    client, finance_headers, analytics_dataset
) -> None:
    """The fixture's ``missing-amount`` draft has no amount and no currency.

    It is still a claim, so it belongs in the claim count - but its bucket must report
    *no* amount rather than an amount of zero, because zero is a figure and unknown is
    not.
    """
    body = _response(client, finance_headers)
    amountless = [row for row in body["departments"] if row["currency"] is None]
    assert len(amountless) == 1, "the fixture creates exactly one claim with no currency"

    row = amountless[0]
    assert row["claim_count"] == 1
    assert row["amount_claim_count"] == 0
    assert row["amount_total"] is None
    assert row["average_amount_total"] is None
    assert row["requested_share"] is None


def test_currencies_are_never_combined(client, finance_headers, analytics_dataset) -> None:
    body = _response(client, finance_headers)
    currencies = {row["currency"] for row in body["departments"] if row["currency"]}
    assert len(currencies) >= 1
    # One row per (department, currency): no bucket holds two currencies.
    keys = [(row["department_id"], row["currency"]) for row in body["departments"]]
    assert len(keys) == len(set(keys))


def test_department_filter_restricts_the_whole_breakdown(
    client, db: Session, finance_headers, analytics_dataset
) -> None:
    body = _response(client, finance_headers)
    target = next((row for row in body["departments"] if row["department_id"] is not None), None)
    assert target is not None, "the fixture must place at least one member in a department"

    filtered = client.get(
        f"{URL}?{WINDOW}&department_id={target['department_id']}", headers=finance_headers
    )
    assert filtered.status_code == 200, filtered.text
    payload = filtered.json()
    assert {row["department_id"] for row in payload["departments"]} == {target["department_id"]}
    # Compare like with like: totals are ordered per currency, so match on the currency
    # rather than by position.
    unfiltered_totals = {row["currency"]: row for row in body["totals"]}
    for total in payload["totals"]:
        assert total["claim_count"] <= unfiltered_totals[total["currency"]]["claim_count"]
    # Compare like with like: the filter selects one department, so that department's
    # own figures must be unchanged rather than compared against the organization total.
    unfiltered_rows = _by_bucket(body["departments"])
    for row in payload["departments"]:
        key = (str(row["department_id"]) if row["department_id"] else None, row["currency"])
        assert row["claim_count"] == unfiltered_rows[key]["claim_count"]
        assert row["amount_total"] == unfiltered_rows[key]["amount_total"]
        assert row["approved_amount_total"] == unfiltered_rows[key]["approved_amount_total"]


def test_an_empty_period_returns_no_rows_rather_than_zeros(
    client, finance_headers, analytics_dataset
) -> None:
    """Fabricated zero rows would look like real data with real spend of zero."""
    response = client.get(f"{URL}?from=1999-01-01&to=1999-12-31", headers=finance_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["departments"] == []
    assert body["totals"] == []
    # The undated claim is reported for *every* period, including one with no dated
    # claims at all: it cannot be attributed to a period, and hiding it inside an empty
    # result would make it invisible rather than unknown. This matches `overview`.
    assert body["claims_with_unknown_transaction_date"] == 1


def test_an_inverted_range_is_rejected(client, finance_headers) -> None:
    response = client.get(f"{URL}?from=2026-12-31&to=2026-01-01", headers=finance_headers)
    assert response.status_code == 422


def test_authentication_and_authorization_are_enforced(
    client, employee_headers, finance_headers, analytics_dataset
) -> None:
    assert client.get(f"{URL}?{WINDOW}").status_code == 401
    # An ordinary employee has no organization-wide analytics permission.
    assert client.get(f"{URL}?{WINDOW}", headers=employee_headers).status_code == 403
    assert client.get(f"{URL}?{WINDOW}", headers=finance_headers).status_code == 200
