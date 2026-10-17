from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from app.api.deps import get_receipt_extractor, get_receipt_storage
from app.core.enums import ExtractionStatus
from app.extraction.base import ExtractionResult
from app.models.audit import AuditEvent
from app.models.expense import ExpenseFieldEvidence
from app.storage.local import LocalPrivateReceiptStorage
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
PNG = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A]) + b"synthetic receipt image"


class _Extractor:
    provider_name = "test-provider"

    def extract(self, *, receipt_id: uuid.UUID, data: bytes, content_type: str) -> ExtractionResult:
        return ExtractionResult(
            status=ExtractionStatus.UNAVAILABLE,
            provider=self.provider_name,
            error_code="TEST_UNAVAILABLE",
            error_message="No inference was run in this test.",
        )


@pytest.fixture
def lifecycle_client(client: TestClient, tmp_path: Path):
    client.app.dependency_overrides[get_receipt_extractor] = lambda: _Extractor()
    client.app.dependency_overrides[get_receipt_storage] = lambda: LocalPrivateReceiptStorage(
        root=str(tmp_path)
    )
    yield client
    client.app.dependency_overrides.pop(get_receipt_extractor, None)
    client.app.dependency_overrides.pop(get_receipt_storage, None)


def _draft(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/expenses",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "channel": "web",
            "merchant": "Synthetic Cafe",
            "expense_date": "2026-10-01",
            "amount": "12.50",
            "currency": "INR",
            "category": "meal",
            "business_purpose": "Synthetic demonstration",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _attach_receipt(client: TestClient, headers: dict[str, str], expense_id: str) -> None:
    response = client.post(
        f"/api/v1/expenses/{expense_id}/receipts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        files={"file": ("synthetic.png", PNG, "image/png")},
    )
    assert response.status_code == 201, response.text


def _submit(client: TestClient, headers: dict[str, str], expense_id: str, version: int, key: str):
    return client.post(
        f"/api/v1/expenses/{expense_id}/submit",
        headers={**headers, "Idempotency-Key": key},
        json={"expected_version": version},
    )


def test_employee_draft_submit_and_idempotent_replay(lifecycle_client, employee_headers) -> None:
    draft = _draft(lifecycle_client, employee_headers)
    _attach_receipt(lifecycle_client, employee_headers, draft["id"])
    key = str(uuid.uuid4())
    first = _submit(lifecycle_client, employee_headers, draft["id"], draft["version"], key)
    replay = _submit(lifecycle_client, employee_headers, draft["id"], draft["version"], key)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "submitted"
    assert replay.json() == first.json()
    assert replay.json()["version"] == draft["version"] + 1


def test_review_decision_is_scoped_audited_and_idempotent(
    lifecycle_client, employee_headers, finance_headers, db: Session
) -> None:
    draft = _draft(lifecycle_client, employee_headers)
    _attach_receipt(lifecycle_client, employee_headers, draft["id"])
    submitted = _submit(
        lifecycle_client, employee_headers, draft["id"], draft["version"], str(uuid.uuid4())
    ).json()
    key = str(uuid.uuid4())
    payload = {
        "action": "request_correction",
        "reason": "Please confirm the attendee count.",
        "expected_version": submitted["version"],
    }
    url = f"/api/v1/expenses/{draft['id']}/decisions"
    first = lifecycle_client.post(
        url, headers={**finance_headers, "Idempotency-Key": key}, json=payload
    )
    replay = lifecycle_client.post(
        url, headers={**finance_headers, "Idempotency-Key": key}, json=payload
    )
    assert first.status_code == 201, first.text
    assert first.json()["new_status"] == "needs_info"
    assert replay.json() == first.json()

    history = lifecycle_client.get(
        f"/api/v1/expenses/{draft['id']}/audit", headers=employee_headers
    )
    assert history.status_code == 200
    assert any(item["action"] == "expense.request_correction" for item in history.json()["items"])
    assert "Please confirm the attendee count." in history.text
    events = (
        db.execute(select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(draft["id"])))
        .scalars()
        .all()
    )
    assert sum(event.action == "expense.request_correction" for event in events) == 1


def test_correction_adds_provenance_and_reject_requires_reason(
    lifecycle_client, employee_headers, finance_headers, db: Session
) -> None:
    draft = _draft(lifecycle_client, employee_headers)
    _attach_receipt(lifecycle_client, employee_headers, draft["id"])
    submitted = _submit(
        lifecycle_client, employee_headers, draft["id"], draft["version"], str(uuid.uuid4())
    ).json()
    requested = lifecycle_client.post(
        f"/api/v1/expenses/{draft['id']}/decisions",
        headers={**finance_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "action": "request_correction",
            "reason": "Fix merchant",
            "expected_version": submitted["version"],
        },
    )
    assert requested.status_code == 201
    corrected = lifecycle_client.patch(
        f"/api/v1/expenses/{draft['id']}",
        headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "expected_version": requested.json()["expense_version"],
            "merchant": "Corrected Synthetic Cafe",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["merchant"]["value"] == "Corrected Synthetic Cafe"
    assert corrected.json()["merchant"]["source"] == "employee_input"
    evidence = (
        db.execute(
            select(ExpenseFieldEvidence)
            .where(
                ExpenseFieldEvidence.expense_id == uuid.UUID(draft["id"]),
                ExpenseFieldEvidence.field_name == "merchant",
            )
            .order_by(ExpenseFieldEvidence.expense_version)
        )
        .scalars()
        .all()
    )
    assert len(evidence) == 2
    assert evidence[0].is_current is False and evidence[1].is_current is True
    assert evidence[1].created_by_user_id == uuid.UUID(employee_headers["X-Demo-Actor-Id"])

    invalid_reject = lifecycle_client.post(
        f"/api/v1/expenses/{draft['id']}/decisions",
        headers={**finance_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"action": "reject", "expected_version": corrected.json()["version"]},
    )
    assert invalid_reject.status_code == 422


def test_read_scope_and_mutation_authorization(lifecycle_client, employee_headers, seeded) -> None:
    draft = _draft(lifecycle_client, employee_headers)
    _attach_receipt(lifecycle_client, employee_headers, draft["id"])
    outsider = {"X-Demo-Actor-Id": seeded["subjects"]["employee.rohit"]}
    assert (
        lifecycle_client.get(f"/api/v1/expenses/{draft['id']}", headers=outsider).status_code == 404
    )
    assert lifecycle_client.get("/api/v1/expenses", headers=employee_headers).json()["items"]
    assert lifecycle_client.get("/api/v1/expenses", headers=outsider).json()["items"] == []
    denied = lifecycle_client.post(
        f"/api/v1/expenses/{draft['id']}/decisions",
        headers={**employee_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"action": "approve", "expected_version": draft["version"]},
    )
    assert denied.status_code == 403


def test_submission_requires_a_receipt_and_valid_state(lifecycle_client, employee_headers) -> None:
    draft = _draft(lifecycle_client, employee_headers)
    response = _submit(
        lifecycle_client, employee_headers, draft["id"], draft["version"], str(uuid.uuid4())
    )
    assert response.status_code == 422
    assert (
        lifecycle_client.get(f"/api/v1/expenses/{draft['id']}", headers=employee_headers).json()[
            "status"
        ]
        == "draft"
    )
