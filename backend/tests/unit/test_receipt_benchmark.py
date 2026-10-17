from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from scripts import receipt_benchmark as benchmark


def _annotation(kind: str, value: Any = None) -> dict[str, Any]:
    return {"annotation": kind, **({"value": value} if kind == "verified_value" else {})}


def _ground_truth(sample_id: str) -> dict[str, Any]:
    fields = {
        "merchant": _annotation("verified_value", "Synthetic Cafe"),
        "transaction_date": _annotation("verified_value", "2025-02-03"),
        "currency": _annotation("verified_value", "USD"),
        "subtotal": _annotation("verified_value", "10.00"),
        "tax_total": _annotation("verified_value", "0.80"),
        "tip": _annotation("verified_absent"),
        "discount": _annotation("unannotated"),
        "grand_total": _annotation("verified_value", "10.80"),
        "receipt_number": _annotation("ambiguous"),
    }
    line = {
        "description": _annotation("verified_value", "Tea"),
        "quantity": _annotation("verified_value", "2"),
        "unit_price": _annotation("verified_value", "5.00"),
        "line_total": _annotation("verified_value", "10.00"),
    }
    return {
        "schema_version": 1,
        "sample_id": sample_id,
        "fields": fields,
        "line_items": {"annotation": "verified_value", "value": [line]},
    }


def _write_image(path: Path, color: tuple[int, int, int] = (245, 245, 245)) -> None:
    Image.new("RGB", (48, 64), color).save(path, format="PNG")


def _make_dataset(root: Path, *, count: int = 1, duplicate_images: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    samples = []
    for index in range(count):
        sample_id = f"sample-{index + 1}"
        image_name = "receipt.png" if duplicate_images else f"images/{sample_id}.png"
        image_path = root / image_name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        if not image_path.exists():
            _write_image(image_path, (245 - index, 245, 245))
        gt_name = f"ground_truth/{sample_id}.json"
        gt_path = root / gt_name
        gt_path.parent.mkdir(parents=True, exist_ok=True)
        gt_path.write_text(json.dumps(_ground_truth(sample_id)), encoding="utf-8")
        samples.append(
            {
                "id": sample_id,
                "image": image_name,
                "ground_truth": gt_name,
                "category": "food",
                "quality": "good",
                "authenticity": "synthetic",
                "source_attribution": {
                    "name": "synthetic fixture",
                    "uri": "https://example.test/fixture",
                },
                "privacy_review": "approved",
                "cloud_inference_approved": True,
            }
        )
    manifest = {
        "schema_version": 1,
        "dataset_id": "offline-test-set",
        "license": {"name": "CC0 synthetic fixture", "url": "https://example.test/license"},
        "samples": samples,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _structured_result(*, total: str = "10.80", tip_status: str = "missing") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "merchant": {"value": "synthetic   cafe", "status": "extracted"},
        "transaction_date": {"value": "2025-02-03", "status": "extracted"},
        "currency": {"value": "USD", "status": "extracted"},
        "subtotal": {"value": "10.0", "status": "extracted"},
        "tax_total": {"value": "0.80", "status": "extracted"},
        "tip": {"value": None, "status": tip_status},
        "discount": {"value": None, "status": "missing"},
        "grand_total": {"value": total, "status": "extracted"},
        "receipt_number": {"value": None, "status": "ambiguous"},
        "line_items": [
            {
                "description": {"value": "Tea", "status": "extracted"},
                "quantity": {"value": "2.0", "status": "extracted"},
                "unit_price": {"value": "5.00", "status": "extracted"},
                "line_total": {"value": "10.00", "status": "extracted"},
            }
        ],
    }


def test_validate_accepts_decodable_image_and_recognizes_partial_ground_truth(
    tmp_path: Path,
) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))

    assert dataset.is_valid
    assert dataset.valid_samples[0].annotation_completeness == "partial"
    assert dataset.public_report()["distribution"]["category"] == {"food": 1}


def test_default_dataset_discovery_uses_runtime_home_and_onedrive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "profile"
    onedrive = tmp_path / "OneDrive"
    expected = onedrive / "Desktop" / "ProoflineReceiptBenchmark"
    expected.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("OneDrive", str(onedrive))

    assert benchmark.discover_dataset() == expected.resolve()


def test_validator_reports_missing_manifest_missing_files_and_traversal(tmp_path: Path) -> None:
    missing = benchmark.validate_dataset(tmp_path / "absent")
    assert not missing.is_valid
    assert "dataset directory does not exist" in missing.global_errors

    root = _make_dataset(tmp_path / "dataset")
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["samples"][0]["image"] = "../outside.png"
    (root / "manifest.json").write_text(json.dumps(manifest))
    invalid = benchmark.validate_dataset(root)
    assert not invalid.is_valid
    assert (
        "referenced image is missing or escapes the dataset directory"
        in invalid.invalid_samples["sample-1"]
    )


def test_validator_rejects_duplicate_image_hashes(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path / "dataset", count=2, duplicate_images=True)

    result = benchmark.validate_dataset(root)

    assert not result.is_valid
    assert len(result.duplicate_hashes) == 1
    assert set(next(iter(result.duplicate_hashes.values()))) == {"sample-1", "sample-2"}


def test_validator_rejects_missing_ground_truth_and_redacts_non_pseudonymous_id(
    tmp_path: Path,
) -> None:
    root = _make_dataset(tmp_path / "dataset")
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["samples"][0]["id"] = "employee-private@example.test"
    manifest["samples"][0]["ground_truth"] = "ground_truth/not-present.json"
    (root / "manifest.json").write_text(json.dumps(manifest))

    result = benchmark.validate_dataset(root)
    public = json.dumps(result.public_report())

    assert not result.is_valid
    assert "employee-private" not in public
    assert "ground-truth" in public


def test_live_approval_is_separate_from_offline_dataset_validation(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path / "dataset")
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["samples"][0]["cloud_inference_approved"] = False
    (root / "manifest.json").write_text(json.dumps(manifest))
    dataset = benchmark.validate_dataset(root)

    assert dataset.is_valid
    with pytest.raises(ValueError, match="cloud inference approval"):
        benchmark._check_live_approval(dataset, dataset.valid_samples)


@pytest.mark.parametrize(
    ("field", "value"),
    [("currency", "US"), ("grand_total", "1.23456"), ("transaction_date", "02/03/2025")],
)
def test_validator_rejects_invalid_ground_truth_schema(
    tmp_path: Path, field: str, value: str
) -> None:
    root = _make_dataset(tmp_path / "dataset")
    gt_path = root / "ground_truth/sample-1.json"
    data = json.loads(gt_path.read_text())
    data["fields"][field] = _annotation("verified_value", value)
    gt_path.write_text(json.dumps(data))

    result = benchmark.validate_dataset(root)

    assert not result.is_valid
    assert "sample-1" in result.invalid_samples


def test_scoring_uses_decimal_and_exact_date_and_excludes_uncertain_labels(tmp_path: Path) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))
    sample = dataset.valid_samples[0]
    response = {
        "id": str(uuid.uuid4()),
        "extraction_runs": [
            {
                "status": "partial",
                "provider": "mock",
                "model": "mock-model",
                "attempt_count": 1,
                "latency_ms": 120,
                "validation_result": {"human_review_required": True},
                "structured_result": _structured_result(total="10.81"),
            }
        ],
    }

    record = benchmark.score_sample(sample, response)
    summary = benchmark._metric_summary([record])

    assert record["field_matches"]["subtotal"] is True
    assert record["field_matches"]["grand_total"] is False
    assert record["field_matches"]["tip"] is True
    assert record["field_matches"]["discount"] is None
    assert record["field_matches"]["receipt_number"] is None
    assert record["line_item_matches"]["quantity"] == [True]
    assert summary["field_presence"]["grand_total"]["precision"] == 1.0
    assert summary["field_presence"]["tip"]["specificity"] == 1.0
    assert summary["human_review_rate"] == 1.0
    assert summary["provider_cost"] is None


def test_partial_and_failed_results_have_truthful_operational_counts() -> None:
    def record(status: str, field_match: bool | None) -> dict[str, Any]:
        return {
            "status": status,
            "latency_ms": 50,
            "elapsed_ms": 100,
            "human_review_required": None,
            "field_matches": {"merchant": field_match},
            "field_statuses": {"merchant": "missing"},
            "line_item_matches": {},
            "presence_counts": {},
        }

    summary = benchmark._metric_summary([record("partial", False), record("failed", None)])

    assert summary["attempted"] == 2
    assert summary["completed"] == 1
    assert summary["partial"] == 1
    assert summary["failed"] == 1
    assert summary["missing_field_rate"] == 1.0
    assert summary["latency_ms"]["end_to_end"]["median"] == 100


def test_failed_job_is_not_scored_as_correct_for_verified_absence(tmp_path: Path) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))
    record = benchmark.score_sample(
        dataset.valid_samples[0],
        {"extraction_runs": [{"status": "failed", "structured_result": None}]},
    )

    assert record["field_matches"]["tip"] is None
    assert record["presence_counts"] == {}
    assert record["field_statuses"]["tip"] == "unknown"


def test_offline_run_does_not_create_http_client_or_need_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden_client(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("offline run attempted to create an HTTP client")

    monkeypatch.setattr(benchmark.httpx, "Client", forbidden_client)

    dataset_path = _make_dataset(tmp_path / "dataset")
    code = benchmark.main(["run", "--dataset", str(dataset_path)])

    assert code == 0
    assert "no API or provider calls made" in capsys.readouterr().out


def test_live_runner_uses_mocked_local_api_without_external_network(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path / "dataset")
    dataset = benchmark.validate_dataset(root)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.method == "GET" and request.url.path.endswith("/meta"):
            return httpx.Response(200, json={"environment": "development", "demo_mode": True})
        if request.method == "POST" and request.url.path.endswith("/expenses"):
            return httpx.Response(201, json={"id": "expense-1"})
        if request.method == "POST" and request.url.path.endswith("/receipts"):
            return httpx.Response(
                201,
                json={
                    "receipt": {
                        "id": "receipt-1",
                        "extraction_status": "pending",
                        "extraction_runs": [],
                    }
                },
            )
        if request.method == "GET" and request.url.path.endswith("/receipts/receipt-1"):
            return httpx.Response(
                200,
                json={
                    "id": "receipt-1",
                    "extraction_status": "success",
                    "extraction_runs": [
                        {
                            "status": "success",
                            "provider": "mock",
                            "model": "mock-model",
                            "latency_ms": 10,
                            "attempt_count": 1,
                            "structured_result": _structured_result(),
                            "validation_result": {"human_review_required": False},
                        }
                    ],
                },
            )
        return httpx.Response(404)

    records = benchmark.run_live(
        dataset,
        dataset.valid_samples,
        base_url="http://127.0.0.1:8000",
        actor_id="seeded-user-uuid",
        output_timeout=2,
        cloud_upload_confirmed=True,
        provider_terms_reviewed=True,
        disposable_environment_confirmed=True,
        transport=httpx.MockTransport(handler),
    )

    assert calls == [
        "/api/v1/meta",
        "/api/v1/expenses",
        "/api/v1/expenses/expense-1/receipts",
        "/api/v1/receipts/receipt-1",
    ]
    assert records[0]["status"] == "success"
    assert records[0]["field_matches"]["grand_total"] is True
    assert records[0]["provider"] == "mock"
    assert records[0]["elapsed_ms"] is not None


def test_live_runner_rejects_non_loopback_api_before_any_request(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path / "dataset")
    dataset = benchmark.validate_dataset(root)

    with pytest.raises(ValueError, match="restricted to localhost"):
        benchmark.run_live(
            dataset,
            dataset.valid_samples,
            base_url="https://api.example.com",
            actor_id="seeded-user-uuid",
            output_timeout=1,
            cloud_upload_confirmed=True,
            provider_terms_reviewed=True,
            disposable_environment_confirmed=True,
        )


def test_live_runner_refuses_non_development_api_before_upload(tmp_path: Path) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"environment": "production", "demo_mode": False})

    with pytest.raises(ValueError, match="environment=development"):
        benchmark.run_live(
            dataset,
            dataset.valid_samples,
            base_url="http://localhost:8000",
            actor_id="seeded-user-uuid",
            output_timeout=1,
            cloud_upload_confirmed=True,
            provider_terms_reviewed=True,
            disposable_environment_confirmed=True,
            transport=httpx.MockTransport(handler),
        )

    assert calls == ["/api/v1/meta"]


def test_retry_handles_rate_limit_without_leaking_response_body() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="private response text")
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = benchmark._request_with_retry(client, "GET", "http://127.0.0.1/test")

    assert response.status_code == 200
    assert calls == 2


def test_report_files_are_unique_and_contain_no_extracted_field_values(tmp_path: Path) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))
    record = benchmark.score_sample(
        dataset.valid_samples[0],
        {
            "id": "receipt-id",
            "extraction_runs": [{"status": "success", "structured_result": _structured_result()}],
        },
    )
    record["elapsed_ms"] = 100
    first = benchmark._write_run_report(dataset, [record], dataset.root)
    second = benchmark._write_run_report(dataset, [record], dataset.root)

    assert first != second
    content = (first / "report.json").read_text(encoding="utf-8")
    assert "Synthetic Cafe" not in content
    assert "Tea" not in content
    assert (first / "samples.csv").is_file()
    assert (first / "report.md").is_file()


def test_scoring_saved_results_strips_arbitrary_and_raw_receipt_content(tmp_path: Path) -> None:
    dataset = benchmark.validate_dataset(_make_dataset(tmp_path / "dataset"))
    record = benchmark.score_sample(
        dataset.valid_samples[0],
        {
            "id": str(uuid.uuid4()),
            "extraction_runs": [{"status": "success", "structured_result": _structured_result()}],
        },
    )
    record["raw_ocr_text"] = "sensitive receipt body"
    record["structured_result"] = {"merchant": {"value": "sensitive merchant"}}
    source = dataset.root / "saved-results.json"
    source.write_text(json.dumps({"report_schema_version": 1, "samples": [record]}))

    clean_records = benchmark.score_results(dataset, source)
    report = benchmark.build_report(dataset, clean_records, "score-test")
    output = dataset.root / "result-output"
    benchmark._write_report_files(output, report)
    serialized = (output / "report.json").read_text(encoding="utf-8")

    assert "sensitive receipt body" not in serialized
    assert "sensitive merchant" not in serialized
    assert "raw_ocr_text" not in serialized


def test_results_cannot_be_written_under_repository() -> None:
    repository = Path(benchmark.__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the Git repository"):
        benchmark._new_output_dir(repository, "run")
