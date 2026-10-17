from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api.deps import get_receipt_extractor, get_receipt_storage
from app.core.enums import ExtractionStatus
from app.extraction.base import ExtractionResult
from app.extraction.worker import ExtractionJobWorker
from app.models.receipt import ExtractionRun, Receipt
from app.schemas.extraction import ReceiptExtractionPayload
from app.storage.local import LocalPrivateReceiptStorage
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

PNG = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A]) + b"synthetic receipt image"


class FakeExtractor:
    provider_name = "test-provider"

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self.result = result or ExtractionResult(
            status=ExtractionStatus.SUCCESS,
            provider=self.provider_name,
            model="fixture",
            raw_text="synthetic OCR text",
            raw_payload_sha256="a" * 64,
            latency_ms=1,
        )

    def extract(self, *, receipt_id: uuid.UUID, data: bytes, content_type: str) -> ExtractionResult:
        assert receipt_id
        assert data == PNG
        assert content_type == "image/png"
        return self.result


@pytest.fixture
def receipt_client(
    client: TestClient,
    tmp_path: Path,
) -> Iterator[tuple[TestClient, FakeExtractor]]:

    extractor = FakeExtractor()
    client.app.dependency_overrides[get_receipt_extractor] = lambda: extractor
    client.app.dependency_overrides[get_receipt_storage] = lambda: LocalPrivateReceiptStorage(
        root=str(tmp_path)
    )
    yield client, extractor
    client.app.dependency_overrides.pop(get_receipt_extractor, None)
    client.app.dependency_overrides.pop(get_receipt_storage, None)


def make_expense(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/expenses",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"channel": "web"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client: TestClient, headers: dict[str, str], expense_id: str, data: bytes = PNG):
    return client.post(
        f"/api/v1/expenses/{expense_id}/receipts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        files={"file": ("synthetic.png", data, "image/png")},
    )


@pytest.mark.integration
def test_valid_upload_persists_private_receipt_and_run_without_raw_text(
    receipt_client: tuple[TestClient, FakeExtractor], employee_headers: dict[str, str], db: Session
) -> None:
    client, extractor = receipt_client
    expense_id = make_expense(client, employee_headers)
    response = upload(client, employee_headers, expense_id)

    assert response.status_code == 201, response.text
    body = response.json()
    receipt_id = uuid.UUID(body["receipt"]["id"])
    assert body["receipt"]["extraction_status"] == "pending"
    assert body["extraction_scheduled"] is True
    assert "synthetic OCR text" not in response.text
    receipt = db.get(Receipt, receipt_id)
    assert receipt is not None and receipt.expense_id == uuid.UUID(expense_id)
    assert receipt.sha256
    run = db.execute(
        select(ExtractionRun).where(ExtractionRun.receipt_id == receipt_id)
    ).scalar_one()
    assert run.status == "pending"
    assert run.raw_text_sha256 is None and run.raw_payload_sha256 is None
    assert "raw_text" not in run.__dict__

    extractor.result = ExtractionResult(
        status=ExtractionStatus.SUCCESS,
        provider=extractor.provider_name,
        structured_data=ReceiptExtractionPayload(
            merchant={"value": "Synthetic Shop", "status": "extracted"},
            transaction_date={"value": "2026-10-01", "status": "extracted"},
            currency={"value": "INR", "status": "extracted"},
            grand_total={"value": "12.50", "status": "extracted"},
            subtotal={"value": None, "status": "missing"},
            tax_total={"value": None, "status": "missing"},
        ),
    )
    worker = ExtractionJobWorker(
        session_factory=lambda: Session(
            bind=db.connection(), join_transaction_mode="create_savepoint"
        ),
        storage=client.app.dependency_overrides[get_receipt_storage](),
        extractor=extractor,
        concurrency=1,
        max_attempts=1,
        timeout_seconds=1,
        retry_backoff_seconds=0,
    )
    worker._process_run(run.id)
    db.refresh(run)
    assert run.status == "success"
    assert run.structured_result is not None
    assert run.structured_result["merchant"]["value"] == "Synthetic Shop"
    assert run.validation_result is not None
    assert run.raw_text_sha256 is None

    content = client.get(body["receipt"]["content_url"], headers=employee_headers)
    assert content.status_code == 200 and content.content == PNG
    assert content.headers["cache-control"] == "private, no-store"


@pytest.mark.integration
def test_invalid_content_is_rejected_and_duplicate_bytes_are_preserved(
    receipt_client: tuple[TestClient, FakeExtractor], employee_headers: dict[str, str]
) -> None:
    client, _ = receipt_client
    expense_id = make_expense(client, employee_headers)
    rejected = upload(client, employee_headers, expense_id, b"not a receipt")
    assert rejected.status_code == 415

    first = upload(client, employee_headers, expense_id)
    second = upload(client, employee_headers, expense_id)
    assert first.status_code == second.status_code == 201
    assert first.json()["receipt"]["id"] != second.json()["receipt"]["id"]
    assert first.json()["receipt"]["sha256"] == second.json()["receipt"]["sha256"]


@pytest.mark.integration
def test_upload_enforces_configured_size_limit(
    receipt_client: tuple[TestClient, FakeExtractor], employee_headers: dict[str, str]
) -> None:
    client, _ = receipt_client
    expense_id = make_expense(client, employee_headers)
    client.app.state.max_receipt_bytes = len(PNG) - 1
    oversized = upload(client, employee_headers, expense_id)
    assert oversized.status_code == 413


@pytest.mark.integration
def test_batch_upload_creates_independent_pending_runs_and_scoped_listing(
    receipt_client: tuple[TestClient, FakeExtractor], employee_headers: dict[str, str], db: Session
) -> None:
    client, _ = receipt_client
    expense_id = make_expense(client, employee_headers)
    batch_key = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/expenses/{expense_id}/receipts/batch",
        headers={**employee_headers, "Idempotency-Key": batch_key},
        files=[
            ("files", ("one.png", PNG, "image/png")),
            ("files", ("two.png", PNG, "image/png")),
        ],
    )
    assert response.status_code == 201, response.text
    items = response.json()
    assert len(items) == 2
    assert all(item["extraction_scheduled"] for item in items)
    assert all(item["receipt"]["extraction_status"] == "pending" for item in items)
    assert items[0]["receipt"]["id"] != items[1]["receipt"]["id"]
    assert all(len(item["receipt"]["extraction_runs"]) == 1 for item in items)
    assert all(
        db.get(ExtractionRun, uuid.UUID(item["receipt"]["extraction_runs"][0]["id"])).status
        == "pending"
        for item in items
    )
    repeated = client.post(
        f"/api/v1/expenses/{expense_id}/receipts/batch",
        headers={**employee_headers, "Idempotency-Key": batch_key},
        files=[
            ("files", ("one.png", PNG, "image/png")),
            ("files", ("two.png", PNG, "image/png")),
        ],
    )
    assert repeated.status_code == 201
    assert [item["receipt"]["id"] for item in repeated.json()] == [
        item["receipt"]["id"] for item in items
    ]
    listed = client.get(f"/api/v1/expenses/{expense_id}/receipts", headers=employee_headers)
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {item["receipt"]["id"] for item in items}


@pytest.mark.integration
def test_reextraction_appends_history_and_hides_receipt_from_other_employee(
    receipt_client: tuple[TestClient, FakeExtractor],
    employee_headers: dict[str, str],
    seeded: dict[str, object],
    db: Session,
) -> None:
    authenticated, _ = receipt_client
    expense_id = make_expense(authenticated, employee_headers)
    uploaded = upload(authenticated, employee_headers, expense_id).json()
    receipt_id = uploaded["receipt"]["id"]
    subjects = seeded["subjects"]
    assert isinstance(subjects, dict)
    outsider = {"X-Demo-Actor-Id": subjects["employee.rohit"]}
    refused = authenticated.post(
        f"/api/v1/receipts/{receipt_id}/extractions",
        headers={**outsider, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert refused.status_code == 404

    run_id = uuid.UUID(uploaded["receipt"]["extraction_runs"][0]["id"])
    worker = ExtractionJobWorker(
        session_factory=lambda: Session(
            bind=db.connection(), join_transaction_mode="create_savepoint"
        ),
        storage=authenticated.app.dependency_overrides[get_receipt_storage](),
        extractor=authenticated.app.dependency_overrides[get_receipt_extractor](),
        concurrency=1,
        max_attempts=1,
        timeout_seconds=1,
        retry_backoff_seconds=0,
    )
    worker._process_run(run_id)

    key = str(uuid.uuid4())
    first = authenticated.post(
        f"/api/v1/receipts/{receipt_id}/extractions",
        headers={**employee_headers, "Idempotency-Key": key},
    )
    repeated = authenticated.post(
        f"/api/v1/receipts/{receipt_id}/extractions",
        headers={**employee_headers, "Idempotency-Key": key},
    )
    assert first.status_code == repeated.status_code == 202
    assert first.json()["extraction_runs"][-1]["id"] == repeated.json()["extraction_runs"][-1]["id"]
    assert len(first.json()["extraction_runs"]) == 2


@pytest.mark.integration
def test_failed_ocr_is_persisted_as_failed_and_auth_is_required(
    receipt_client: tuple[TestClient, FakeExtractor],
    employee_headers: dict[str, str],
    client: TestClient,
    db: Session,
) -> None:
    authed_client, extractor = receipt_client
    expense_id = make_expense(authed_client, employee_headers)
    extractor.result = ExtractionResult(
        status=ExtractionStatus.FAILED,
        provider=extractor.provider_name,
        error_code="OCR_TIMEOUT",
        error_message="OCR timed out.",
    )
    failed = upload(authed_client, employee_headers, expense_id)
    assert failed.status_code == 201
    assert failed.json()["receipt"]["extraction_status"] == "pending"
    run_id = uuid.UUID(failed.json()["receipt"]["extraction_runs"][0]["id"])
    worker = ExtractionJobWorker(
        session_factory=lambda: Session(
            bind=db.connection(), join_transaction_mode="create_savepoint"
        ),
        storage=authed_client.app.dependency_overrides[get_receipt_storage](),
        extractor=extractor,
        concurrency=1,
        max_attempts=1,
        timeout_seconds=1,
        retry_backoff_seconds=0,
    )
    worker._process_run(run_id)
    assert db.get(ExtractionRun, run_id).status == "failed"
    no_auth = upload(client, {}, expense_id)
    assert no_auth.status_code == 401


@pytest.mark.integration
def test_receipt_metadata_is_not_visible_to_another_employee(
    receipt_client: tuple[TestClient, FakeExtractor],
    employee_headers: dict[str, str],
    seeded: dict[str, object],
) -> None:
    client, _ = receipt_client
    expense_id = make_expense(client, employee_headers)
    uploaded = upload(client, employee_headers, expense_id)
    receipt_id = uploaded.json()["receipt"]["id"]
    subjects = seeded["subjects"]
    assert isinstance(subjects, dict)
    outsider = {"X-Demo-Actor-Id": subjects["employee.rohit"]}
    hidden = client.get(f"/api/v1/receipts/{receipt_id}", headers=outsider)
    assert hidden.status_code == 404
    hidden_content = client.get(f"/api/v1/receipts/{receipt_id}/content", headers=outsider)
    assert hidden_content.status_code == 404
