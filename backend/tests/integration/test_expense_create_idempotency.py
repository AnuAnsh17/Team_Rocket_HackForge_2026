"""Idempotent replay of the expense-creating request itself.

`test_expense_lifecycle_api.py` covers replay for the submit and decision
endpoints, but every draft it creates uses a fresh Idempotency-Key - so the one
endpoint where a retry is most likely (a client that sent a create and never saw
the response) had no coverage at all. That is the gap this file closes, and it is
the path that returned a 500 in live verification.
"""

from __future__ import annotations

import uuid

from app.services import idempotency_service
from fastapi.testclient import TestClient

CREATE_BODY = {
    "channel": "web",
    "merchant": "Synthetic Cafe",
    "expense_date": "2026-10-01",
    "amount": "12.50",
    "currency": "INR",
    "category": "meal",
    "business_purpose": "Synthetic demonstration",
}


def _create(client: TestClient, headers: dict[str, str], key: str):
    return client.post(
        "/api/v1/expenses", headers={**headers, "Idempotency-Key": key}, json=CREATE_BODY
    )


def test_replaying_a_create_returns_the_stored_draft(client: TestClient, employee_headers) -> None:
    key = str(uuid.uuid4())

    first = _create(client, employee_headers, key)
    assert first.status_code == 201, first.text

    replay = _create(client, employee_headers, key)
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()


def test_a_replayed_create_does_not_create_a_second_claim(
    client: TestClient, employee_headers
) -> None:
    key = str(uuid.uuid4())
    first = _create(client, employee_headers, key)
    _create(client, employee_headers, key)

    listing = client.get("/api/v1/expenses", headers=employee_headers)
    assert listing.status_code == 200
    ids = [row["id"] for row in listing.json()["items"]]
    assert ids.count(first.json()["id"]) == 1
    assert len(ids) == 1


def test_reusing_a_key_for_a_different_body_is_refused(
    client: TestClient, employee_headers
) -> None:
    """A key identifies one request. Reusing it for another must not replay."""
    key = str(uuid.uuid4())
    assert _create(client, employee_headers, key).status_code == 201

    changed = dict(CREATE_BODY, amount="99.99")
    response = client.post(
        "/api/v1/expenses", headers={**employee_headers, "Idempotency-Key": key}, json=changed
    )
    assert response.status_code == 409, response.text


def test_a_retry_that_races_the_original_commit_replays_instead_of_failing(
    client: TestClient, employee_headers, monkeypatch
) -> None:
    """The intermittent live 500, reproduced deterministically.

    ``get_session`` commits in a generating dependency, which FastAPI finalises
    *after* the response has been sent. A retry that arrives promptly can therefore
    run its idempotency lookup before the original request's transaction commits,
    miss the row, and collide with the unique index on insert.

    The lookup is forced to miss once here, which is exactly the state the racing
    retry is in. The endpoint must replay the stored response: the original effect
    did happen, so failing the retry with a 500 would leave the client unable to
    learn what it had already done.
    """
    key = str(uuid.uuid4())
    first = _create(client, employee_headers, key)
    assert first.status_code == 201, first.text

    real_lookup = idempotency_service._find_existing
    calls = {"lookups": 0}

    def lookup_that_misses_once(session, actor_user_id, idempotency_key):
        calls["lookups"] += 1
        if calls["lookups"] == 1:
            return None
        return real_lookup(session, actor_user_id, idempotency_key)

    monkeypatch.setattr(idempotency_service, "_find_existing", lookup_that_misses_once)

    replay = _create(client, employee_headers, key)

    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    # The recovery lookup ran, and only one claim and one key exist.
    assert calls["lookups"] >= 2
    listing = client.get("/api/v1/expenses", headers=employee_headers).json()["items"]
    assert len(listing) == 1
