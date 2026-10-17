"""Offline receipt benchmark validation/scoring and an explicitly opt-in API runner.

Dataset JSON values follow the production ReceiptExtractionPayload field names. This
module never calls an extraction provider except through ``run --live`` and the local
Proofline API. It does not emit image bytes, raw OCR text, credentials, or field values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from app.schemas.extraction import ReceiptExtractionPayload
from pydantic import ValidationError

Image: Any = import_module("PIL.Image") if importlib.util.find_spec("PIL") else None

SCHEMA_VERSION = 1
FIELD_NAMES = (
    "merchant",
    "transaction_date",
    "currency",
    "subtotal",
    "tax_total",
    "tip",
    "discount",
    "grand_total",
    "receipt_number",
)
LINE_FIELD_NAMES = ("description", "quantity", "unit_price", "line_total")
ANNOTATIONS = {"verified_value", "verified_absent", "ambiguous", "illegible", "unannotated"}
CATEGORIES = {"food", "hotel", "ground_transport", "tickets", "fuel", "retail", "other"}
QUALITIES = {"good", "medium"}
AUTHENTICITIES = {"authentic", "synthetic"}
IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_LIVE_LIMIT = 100
SAMPLE_ID_PATTERN = re.compile(r"^sample-[A-Za-z0-9_-]{1,56}$")


@dataclass(slots=True)
class ValidSample:
    metadata: dict[str, Any]
    ground_truth: dict[str, Any]
    image_path: Path
    image_sha256: str
    annotation_completeness: str


@dataclass(slots=True)
class DatasetResult:
    root: Path
    manifest: dict[str, Any] | None
    valid_samples: list[ValidSample]
    invalid_samples: dict[str, list[str]]
    duplicate_hashes: dict[str, list[str]]
    global_errors: list[str]
    distribution: dict[str, dict[str, int]]
    annotation_completeness: dict[str, int]

    @property
    def is_valid(self) -> bool:
        return self.manifest is not None and not self.global_errors and not self.invalid_samples

    def public_report(self) -> dict[str, Any]:
        def report_id(value: str) -> str:
            return value if SAMPLE_ID_PATTERN.fullmatch(value) else "<invalid-sample-id>"

        return {
            "dataset_directory": "<selected-dataset>",
            "manifest_found": self.manifest is not None,
            "valid": self.is_valid,
            "valid_sample_ids": sorted(
                report_id(sample.metadata["id"]) for sample in self.valid_samples
            ),
            "invalid_samples": [
                {"sample_id": report_id(sample_id), "issues": issues}
                for sample_id, issues in sorted(self.invalid_samples.items())
            ],
            "duplicate_file_groups": [
                {"sample_ids": sorted(report_id(sample_id) for sample_id in ids)}
                for _, ids in sorted(self.duplicate_hashes.items())
            ],
            "global_errors": self.global_errors,
            "annotation_completeness": self.annotation_completeness,
            "distribution": self.distribution,
        }


class LocalApiFailure(ValueError):
    """Safe-to-report local API error without response body or sensitive headers."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Local Proofline API returned HTTP {status_code}.")
        self.status_code = status_code


def discover_dataset() -> Path:
    """Resolve the conventional Desktop folder without embedding a user-specific path."""
    home = Path.home()
    candidates = [home / "Desktop" / "ProoflineReceiptBenchmark"]
    for variable in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value) / "Desktop" / "ProoflineReceiptBenchmark")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    raise FileNotFoundError(
        "Could not find Desktop/ProoflineReceiptBenchmark. Pass --dataset with its location."
    )


def _safe_child(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _annotation_completeness(ground_truth: dict[str, Any]) -> str:
    annotations: list[str] = [ground_truth["fields"][name]["annotation"] for name in FIELD_NAMES]
    lines = ground_truth["line_items"]
    annotations.append(lines["annotation"])
    if lines["annotation"] == "verified_value":
        for item in lines["value"]:
            annotations.extend(item[name]["annotation"] for name in LINE_FIELD_NAMES)
    return (
        "complete"
        if all(value in {"verified_value", "verified_absent"} for value in annotations)
        else "partial"
    )


def _check_ground_truth(data: object, sample_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, ["ground-truth file must contain a JSON object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("ground-truth schema_version must be 1")
    if data.get("sample_id") != sample_id:
        errors.append("ground-truth sample_id must match manifest sample id")
    fields = data.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(FIELD_NAMES):
        errors.append("fields must contain exactly the canonical extraction field names")
        fields = {}
    payload: dict[str, Any] = {}
    for field_name in FIELD_NAMES:
        annotation = fields.get(field_name)
        if not isinstance(annotation, dict) or annotation.get("annotation") not in ANNOTATIONS:
            errors.append(f"field {field_name} must declare a supported annotation")
            payload[field_name] = {"value": None, "status": "missing"}
            continue
        kind = annotation["annotation"]
        value = annotation.get("value")
        if kind == "verified_value" and value is None:
            errors.append(f"field {field_name} verified_value requires value")
        if kind != "verified_value" and value is not None:
            errors.append(f"field {field_name} {kind} annotation must not contain value")
        payload[field_name] = {
            "value": value if kind == "verified_value" else None,
            "status": {
                "verified_value": "extracted",
                "verified_absent": "missing",
                "ambiguous": "ambiguous",
                "illegible": "illegible",
                "unannotated": "missing",
            }.get(kind, "missing"),
        }
    line_items = data.get("line_items")
    line_values: list[dict[str, Any]] = []
    if not isinstance(line_items, dict) or line_items.get("annotation") not in ANNOTATIONS:
        errors.append("line_items must declare a supported annotation")
    else:
        line_kind = line_items["annotation"]
        rows = line_items.get("value")
        if line_kind == "verified_value":
            if not isinstance(rows, list) or not rows:
                errors.append("verified line_items requires a non-empty value array")
                rows = []
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or set(row) != set(LINE_FIELD_NAMES):
                    errors.append(f"line item {index} must contain exactly {LINE_FIELD_NAMES}")
                    continue
                parsed_row: dict[str, Any] = {}
                for name in LINE_FIELD_NAMES:
                    cell = row[name]
                    if not isinstance(cell, dict) or cell.get("annotation") not in ANNOTATIONS:
                        errors.append(f"line item {index} field {name} must declare an annotation")
                        parsed_row[name] = {"value": None, "status": "missing"}
                        continue
                    kind = cell["annotation"]
                    value = cell.get("value")
                    if kind == "verified_value" and value is None:
                        errors.append(
                            f"line item {index} field {name} verified_value requires value"
                        )
                    if kind != "verified_value" and value is not None:
                        errors.append(
                            f"line item {index} field {name} {kind} must not contain value"
                        )
                    parsed_row[name] = {
                        "value": value if kind == "verified_value" else None,
                        "status": {
                            "verified_value": "extracted",
                            "verified_absent": "missing",
                            "ambiguous": "ambiguous",
                            "illegible": "illegible",
                            "unannotated": "missing",
                        }[kind],
                    }
                line_values.append(parsed_row)
        elif rows is not None:
            errors.append(f"line_items {line_kind} annotation must not contain value")
        payload["line_items"] = line_values
    if not errors:
        try:
            ReceiptExtractionPayload.model_validate(payload)
        except ValidationError as exc:
            errors.extend(
                f"ground-truth value/schema error: {item['loc']} ({item['type']})"
                for item in exc.errors()
            )
    return (data if not errors else None), errors


def validate_dataset(directory: Path) -> DatasetResult:
    root = directory.expanduser().resolve()
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    manifest: dict[str, Any] | None = None
    if not root.is_dir():
        return DatasetResult(root, None, [], {}, {}, ["dataset directory does not exist"], {}, {})
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest = loaded
        else:
            errors.append("manifest.json must contain a JSON object")
    except FileNotFoundError:
        errors.append("manifest.json is missing; see docs/receipt-benchmark.md for the schema")
    except (json.JSONDecodeError, UnicodeDecodeError):
        errors.append("manifest.json is not valid UTF-8 JSON")
    if manifest is None:
        return DatasetResult(root, None, [], {}, {}, errors, {}, {})

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("manifest schema_version must be 1")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"].strip():
        errors.append("manifest dataset_id is required")
    license_info = manifest.get("license")
    if (
        not isinstance(license_info, dict)
        or not isinstance(license_info.get("name"), str)
        or not license_info["name"].strip()
        or not isinstance(license_info.get("url"), str)
        or not license_info["url"].startswith(("https://", "http://"))
    ):
        errors.append("manifest license requires a name and attribution URL")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        errors.append("manifest samples must be a non-empty array")
        samples = []

    seen_ids: Counter[str] = Counter()
    for sample in samples:
        if isinstance(sample, dict) and isinstance(sample.get("id"), str):
            seen_ids[str(sample["id"])] += 1
    invalid: dict[str, list[str]] = {}
    valid: list[ValidSample] = []
    hash_groups: dict[str, list[str]] = defaultdict(list)
    categories: Counter[str] = Counter()
    qualities: Counter[str] = Counter()
    authenticity: Counter[str] = Counter()
    annotation_counts: Counter[str] = Counter()

    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"sample at index {index} must be an object")
            continue
        sample_id = sample.get("id")
        label = sample_id if isinstance(sample_id, str) and sample_id else f"<index:{index}>"
        issues: list[str] = []
        if not isinstance(sample_id, str) or not sample_id.strip():
            issues.append("sample id is required")
        elif not SAMPLE_ID_PATTERN.fullmatch(sample_id):
            issues.append("sample id must use a pseudonymous sample-<token> identifier")
        elif seen_ids[sample_id] > 1:
            issues.append("sample id is duplicated in the manifest")
        for field_name, accepted in (
            ("category", CATEGORIES),
            ("quality", QUALITIES),
            ("authenticity", AUTHENTICITIES),
        ):
            if sample.get(field_name) not in accepted:
                issues.append(f"{field_name} must be one of {sorted(accepted)}")
        attribution = sample.get("source_attribution")
        if (
            not isinstance(attribution, dict)
            or not all(
                isinstance(attribution.get(key), str) and attribution[key].strip()
                for key in ("name", "uri")
            )
            or not str(attribution.get("uri", "")).startswith(("https://", "http://"))
        ):
            issues.append("source_attribution requires name and URI")
        if sample.get("privacy_review") != "approved":
            issues.append("privacy_review must be approved before benchmark inclusion")
        if not isinstance(sample.get("cloud_inference_approved"), bool):
            issues.append("cloud_inference_approved must be an explicit boolean")

        image_path = _safe_child(root, sample.get("image"))
        if image_path is None:
            issues.append("referenced image is missing or escapes the dataset directory")
            digest = ""
        else:
            with image_path.open("rb") as image_file:
                digest = hashlib.file_digest(image_file, "sha256").hexdigest()
            hash_groups[digest].append(label)
            if Image is None:
                issues.append("Pillow is required for image decoding; install the benchmark extra")
            else:
                try:
                    with Image.open(image_path) as image:
                        image_format = image.format
                        width, height = image.size
                        image.verify()
                    with Image.open(image_path) as image:
                        image.load()
                    if image_format not in IMAGE_FORMATS or width < 1 or height < 1:
                        issues.append("image must decode as non-empty JPEG, PNG or WebP")
                except (OSError, Image.DecompressionBombError):
                    issues.append("image could not be safely decoded as JPEG, PNG or WebP")
        gt_path = _safe_child(root, sample.get("ground_truth"))
        if gt_path is None:
            issues.append(
                "referenced ground-truth file is missing or escapes the dataset directory"
            )
            ground_truth = None
        else:
            try:
                gt_raw = json.loads(gt_path.read_text(encoding="utf-8"))
                ground_truth, gt_errors = _check_ground_truth(gt_raw, label)
                issues.extend(gt_errors)
            except (json.JSONDecodeError, UnicodeDecodeError):
                ground_truth = None
                issues.append("ground-truth file is not valid UTF-8 JSON")
        if ground_truth is not None:
            completeness = _annotation_completeness(ground_truth)
            annotation_counts[completeness] += 1
        else:
            completeness = "unknown"
        if sample.get("category") in CATEGORIES:
            categories[sample["category"]] += 1
        if sample.get("quality") in QUALITIES:
            qualities[sample["quality"]] += 1
        if sample.get("authenticity") in AUTHENTICITIES:
            authenticity[sample["authenticity"]] += 1
        if issues:
            invalid[label] = issues
        elif ground_truth is not None and image_path is not None:
            valid.append(ValidSample(sample, ground_truth, image_path, digest, completeness))

    duplicate_hashes = {digest: ids for digest, ids in hash_groups.items() if len(ids) > 1}
    duplicated_ids = {sample_id for ids in duplicate_hashes.values() for sample_id in ids}
    if duplicated_ids:
        valid = [sample for sample in valid if sample.metadata["id"] not in duplicated_ids]
        for sample_id in duplicated_ids:
            invalid.setdefault(sample_id, []).append(
                "image SHA-256 duplicates another manifest sample"
            )
    distribution = {
        "category": dict(sorted(categories.items())),
        "quality": dict(sorted(qualities.items())),
        "authenticity": dict(sorted(authenticity.items())),
    }
    return DatasetResult(
        root,
        manifest,
        valid,
        invalid,
        duplicate_hashes,
        errors,
        distribution,
        dict(sorted(annotation_counts.items())),
    )


def _canonical(value: object, field_name: str) -> str | None:
    if not isinstance(value, str):
        return None
    if field_name in {
        "subtotal",
        "tax_total",
        "tip",
        "discount",
        "grand_total",
        "quantity",
        "unit_price",
        "line_total",
    }:
        try:
            decimal_value = Decimal(value)
        except (InvalidOperation, ValueError):
            return None
        return format(decimal_value.normalize(), "f") if decimal_value.is_finite() else None
    if field_name == "merchant" or field_name == "description":
        return " ".join(value.split()).casefold()
    if field_name == "currency":
        return value.upper()
    # Dates and receipt numbers intentionally use exact canonical/string comparison.
    return value


def _field_cell(result: object, name: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"status": "missing", "value": None}
    cell = result.get(name)
    if not isinstance(cell, dict):
        return {"status": "missing", "value": None}
    return cell


def score_sample(sample: ValidSample, receipt_response: dict[str, Any]) -> dict[str, Any]:
    runs = receipt_response.get("extraction_runs", [])
    successful = [
        run for run in runs if isinstance(run, dict) and run.get("status") in {"success", "partial"}
    ]
    run = (
        successful[-1] if successful else (runs[-1] if runs and isinstance(runs[-1], dict) else {})
    )
    status_value = str(run.get("status", "pending")) if isinstance(run, dict) else "pending"
    extracted = run.get("structured_result") if isinstance(run, dict) else None
    if isinstance(extracted, dict) and "schema_version" in extracted:
        extracted = {key: value for key, value in extracted.items() if key != "schema_version"}
    has_result = status_value in {"success", "partial"} and isinstance(extracted, dict)
    if not has_result:
        extracted = None
    gt = sample.ground_truth
    metrics: dict[str, bool | None] = {}
    presence: dict[str, dict[str, int]] = {}
    for name in FIELD_NAMES:
        expected = gt["fields"][name]
        annotation = expected["annotation"]
        actual = _field_cell(extracted, name)
        if not has_result or annotation in {"ambiguous", "illegible", "unannotated"}:
            metrics[name] = None
            continue
        if annotation == "verified_absent":
            correct_absence = (
                actual.get("status") in {"missing", "not_applicable"}
                and actual.get("value") is None
            )
            metrics[name] = correct_absence
            predicted_present = (
                actual.get("status") == "extracted" and actual.get("value") is not None
            )
            presence[name] = {
                "predicted_present": int(predicted_present),
                "true_positive": 0,
                "positive": 0,
                "negative": 1,
                "true_negative": int(not predicted_present),
            }
        else:
            predicted_present = (
                actual.get("status") == "extracted" and actual.get("value") is not None
            )
            correct = predicted_present and _canonical(actual.get("value"), name) == _canonical(
                expected.get("value"), name
            )
            metrics[name] = bool(correct)
            presence[name] = {
                "predicted_present": int(predicted_present),
                "true_positive": int(predicted_present),
                "positive": 1,
                "negative": 0,
                "true_negative": 0,
            }

    line_labels = gt["line_items"]
    line_actual = extracted.get("line_items", []) if isinstance(extracted, dict) else []
    line_metrics: dict[str, list[bool | None]] = {name: [] for name in LINE_FIELD_NAMES}
    if not has_result:
        line_metrics = {name: [] for name in LINE_FIELD_NAMES}
    elif line_labels["annotation"] in {"ambiguous", "illegible", "unannotated"}:
        line_metrics = {name: [None] for name in LINE_FIELD_NAMES}
    elif line_labels["annotation"] == "verified_absent":
        for name in LINE_FIELD_NAMES:
            line_metrics[name] = [not line_actual]
    else:
        for index, gt_row in enumerate(line_labels["value"]):
            actual_row = (
                line_actual[index]
                if isinstance(line_actual, list)
                and index < len(line_actual)
                and isinstance(line_actual[index], dict)
                else {}
            )
            for name in LINE_FIELD_NAMES:
                expected = gt_row[name]
                annotation = expected["annotation"]
                actual = _field_cell(actual_row, name)
                if annotation in {"ambiguous", "illegible", "unannotated"}:
                    line_metrics[name].append(None)
                elif annotation == "verified_absent":
                    line_metrics[name].append(
                        actual.get("status") in {"missing", "not_applicable"}
                        and actual.get("value") is None
                    )
                else:
                    line_metrics[name].append(
                        actual.get("status") == "extracted"
                        and _canonical(actual.get("value"), name)
                        == _canonical(expected.get("value"), name)
                    )
        for name in LINE_FIELD_NAMES:
            if isinstance(line_actual, list) and len(line_actual) > len(line_labels["value"]):
                line_metrics[name].extend([False] * (len(line_actual) - len(line_labels["value"])))
    attempts = int(run.get("attempt_count") or 0) if isinstance(run, dict) else 0
    latency = run.get("latency_ms") if isinstance(run, dict) else None
    return {
        "sample_id": sample.metadata["id"],
        "receipt_id": receipt_response.get("id"),
        "provider": _safe_identifier(run.get("provider")) if isinstance(run, dict) else None,
        "model": _safe_identifier(run.get("model")) if isinstance(run, dict) else None,
        "status": status_value,
        "attempt_count": attempts,
        "latency_ms": latency if isinstance(latency, int) and latency >= 0 else None,
        "human_review_required": _human_review_required(run),
        "field_matches": metrics,
        "field_statuses": {
            name: _safe_field_status(_field_cell(extracted, name).get("status"))
            if has_result
            else "unknown"
            for name in FIELD_NAMES
        },
        "line_item_matches": line_metrics,
        "presence_counts": presence,
        "segments": {
            "category": sample.metadata["category"],
            "quality": sample.metadata["quality"],
            "authenticity": sample.metadata["authenticity"],
            "annotation_completeness": sample.annotation_completeness,
        },
    }


def _human_review_required(run: object) -> bool | None:
    if not isinstance(run, dict):
        return None
    validation = run.get("validation_result")
    if not isinstance(validation, dict):
        return None
    value = validation.get("human_review_required")
    return value if isinstance(value, bool) else None


def _safe_field_status(value: object) -> str:
    return value if isinstance(value, str) else "unknown"


def _metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    field_values: dict[str, list[bool]] = defaultdict(list)
    line_values: dict[str, list[bool]] = defaultdict(list)
    presence_totals: dict[str, Counter[str]] = defaultdict(Counter)
    field_statuses: Counter[str] = Counter()
    for record in records:
        for name, matched in record["field_matches"].items():
            if matched is not None:
                field_values[name].append(matched)
        for name, matches in record["line_item_matches"].items():
            line_values[name].extend(value for value in matches if value is not None)
        for name, counts in record["presence_counts"].items():
            presence_totals[name].update(counts)
        field_statuses.update(record.get("field_statuses", {}).values())
    field_summary = {
        name: {
            "correct": sum(values),
            "evaluated": len(values),
            "accuracy": sum(values) / len(values) if values else None,
        }
        for name, values in sorted(field_values.items())
    }
    line_summary = {
        name: {
            "correct": sum(values),
            "evaluated": len(values),
            "accuracy": sum(values) / len(values) if values else None,
        }
        for name, values in sorted(line_values.items())
    }
    presence: dict[str, Any] = {}
    for name, counts in sorted(presence_totals.items()):
        tp = counts["true_positive"]
        predicted = counts["predicted_present"]
        positive = counts["positive"]
        negatives = counts["negative"]
        tn = counts["true_negative"]
        presence[name] = {
            "true_positive": tp,
            "false_positive": max(0, predicted - tp),
            "true_negative": max(0, tn),
            "false_negative": max(0, positive - tp),
            "precision": tp / predicted if predicted else None,
            "recall": tp / positive if positive else None,
            "specificity": tn / negatives if negatives else None,
        }
    statuses = Counter(record["status"] for record in records)
    provider_latencies = sorted(
        record["latency_ms"]
        for record in records
        if isinstance(record.get("latency_ms"), int) and record["latency_ms"] >= 0
    )
    end_to_end_latencies = sorted(
        record["elapsed_ms"] for record in records if record.get("elapsed_ms") is not None
    )
    human_review = [
        record["human_review_required"]
        for record in records
        if record["human_review_required"] is not None
    ]
    return {
        "attempted": len(records),
        "completed": sum(statuses[key] for key in ("success", "partial")),
        "partial": statuses["partial"],
        "failed": statuses["failed"],
        "timed_out": statuses["timeout"],
        "failed_or_timed_out": statuses["failed"] + statuses["timeout"],
        "unavailable": statuses["unavailable"],
        "pending_or_running": statuses["pending"] + statuses["running"],
        "status_counts": dict(sorted(statuses.items())),
        "field_accuracy": field_summary,
        "line_item_accuracy": line_summary,
        "field_presence": presence,
        "latency_ms": {
            "provider": {
                "n": len(provider_latencies),
                "median": statistics.median(provider_latencies) if provider_latencies else None,
                "p95": _percentile(provider_latencies, 0.95)
                if len(provider_latencies) >= 20
                else None,
                "total": sum(provider_latencies) if provider_latencies else None,
            },
            "end_to_end": {
                "n": len(end_to_end_latencies),
                "median": statistics.median(end_to_end_latencies) if end_to_end_latencies else None,
                "p95": _percentile(end_to_end_latencies, 0.95)
                if len(end_to_end_latencies) >= 20
                else None,
                "total": sum(end_to_end_latencies) if end_to_end_latencies else None,
            },
        },
        "field_status_counts": dict(sorted(field_statuses.items())),
        "field_status_evaluated_count": sum(
            count for name, count in field_statuses.items() if name != "unknown"
        ),
        "missing_field_rate": (
            field_statuses["missing"]
            / sum(count for name, count in field_statuses.items() if name != "unknown")
            if any(name != "unknown" for name in field_statuses)
            else None
        ),
        "human_review_rate": sum(human_review) / len(human_review) if human_review else None,
        "human_review_n": len(human_review),
        "provider_cost": None,
        "provider_cost_note": "unavailable: no reliable cost metadata is exposed by this API",
    }


def _percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return values[index]


def build_report(
    dataset: DatasetResult, records: list[dict[str, Any]], run_id: str
) -> dict[str, Any]:
    slices: dict[str, dict[str, list[dict[str, Any]]]] = {
        key: defaultdict(list)
        for key in ("category", "quality", "authenticity", "annotation_completeness")
    }
    for record in records:
        for dimension, value in record["segments"].items():
            slices[dimension][value].append(record)
    elapsed_values = [
        record["elapsed_ms"] for record in records if isinstance(record.get("elapsed_ms"), int)
    ]
    total_elapsed_ms = next(
        (
            record["total_run_elapsed_ms"]
            for record in records
            if isinstance(record.get("total_run_elapsed_ms"), int)
        ),
        sum(elapsed_values) if elapsed_values else None,
    )
    return {
        "report_schema_version": 1,
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "id": (
                dataset.manifest.get("dataset_id")
                if dataset.manifest
                and isinstance(dataset.manifest.get("dataset_id"), str)
                and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", dataset.manifest["dataset_id"])
                else "<invalid-dataset-id>"
            ),
            "size": len(dataset.manifest.get("samples", [])) if dataset.manifest else 0,
            "validation_valid": dataset.is_valid,
            "category_quality_authenticity_distribution": dataset.distribution,
            "annotation_completeness": dataset.annotation_completeness,
        },
        "summary": _metric_summary(records),
        "segments": {
            dimension: {label: _metric_summary(items) for label, items in sorted(values.items())}
            for dimension, values in slices.items()
        },
        "samples": records,
        "elapsed_ms": total_elapsed_ms,
        "throughput_receipts_per_minute": (
            len(records) * 60000 / total_elapsed_ms
            if total_elapsed_ms and total_elapsed_ms > 0
            else None
        ),
        "limitations": [
            "This report evaluates only verified annotations; ambiguous, illegible and unannotated labels are excluded.",
            "Line items are compared by position; reordered rows are not aligned heuristically.",
            "No calibrated confidence or provider cost is reported.",
            "Small samples do not establish general accuracy; authentic and synthetic segments remain separate.",
        ],
    }


def _write_report_files(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=False)
    json_path = output_dir / "report.json"
    csv_path = output_dir / "samples.csv"
    md_path = output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        columns = [
            "sample_id",
            "status",
            "provider_latency_ms",
            "end_to_end_latency_ms",
            "human_review_required",
            "category",
            "quality",
            "authenticity",
            "annotation_completeness",
        ]
        columns += [f"{name}_match" for name in FIELD_NAMES]
        columns += [f"line_item_{name}_matches" for name in LINE_FIELD_NAMES]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in report["samples"]:
            row: dict[str, Any] = {
                key: record.get(key)
                for key in (
                    "sample_id",
                    "status",
                    "human_review_required",
                )
            }
            row["provider_latency_ms"] = record.get("latency_ms")
            row["end_to_end_latency_ms"] = record.get("elapsed_ms")
            row.update(record["segments"])
            row.update({f"{name}_match": value for name, value in record["field_matches"].items()})
            row.update(
                {
                    f"line_item_{name}_matches": json.dumps(matches)
                    for name, matches in record["line_item_matches"].items()
                }
            )
            writer.writerow(row)
    summary = report["summary"]
    lines = [
        "# Receipt benchmark report",
        "",
        f"- Run: `{report['run_id']}`",
        f"- Generated: {report['generated_at']}",
        f"- Dataset size: {report['dataset']['size']}",
        f"- Validation passed: {report['dataset']['validation_valid']}",
        f"- Attempted / completed / partial / failed: {summary['attempted']} / {summary['completed']} / {summary['partial']} / {summary['failed']}",
        f"- Timed out: {summary['timed_out']}",
        f"- Median end-to-end latency (ms): {summary['latency_ms']['end_to_end']['median']}",
        f"- p95 end-to-end latency (ms): {summary['latency_ms']['end_to_end']['p95']}",
        f"- Human-review rate: {_format_rate(summary['human_review_rate'], summary['human_review_n'])}",
        f"- Missing field rate: {_format_rate(summary['missing_field_rate'], summary['field_status_evaluated_count'])}",
        "- Provider cost: unavailable (not exposed reliably by the API)",
        "",
        "## Field accuracy",
        "",
        "| Field | Correct | Evaluated | Accuracy |",
        "|---|---:|---:|---:|",
    ]
    for name, value in summary["field_accuracy"].items():
        lines.append(
            f"| {name} | {value['correct']} | {value['evaluated']} | {_format_rate(value['accuracy'], value['evaluated'])} |"
        )
    lines += ["", "## Dataset and extraction segments", ""]
    distributions = report["dataset"]["category_quality_authenticity_distribution"]
    for distribution_name, values in distributions.items():
        lines.append(
            f"- {distribution_name}: "
            + (", ".join(f"{key}={value}" for key, value in values.items()) or "none")
        )
    for dimension in ("category", "quality", "authenticity", "annotation_completeness"):
        lines += ["", f"### {dimension.replace('_', ' ').title()}", ""]
        lines += [
            "| Segment | n | Merchant accuracy | Date accuracy | Currency accuracy | Grand total accuracy |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for label, segment in report["segments"][dimension].items():
            summary_for_segment = segment
            cells = []
            for field_name in ("merchant", "transaction_date", "currency", "grand_total"):
                metric = summary_for_segment["field_accuracy"].get(field_name, {})
                cells.append(_format_rate(metric.get("accuracy"), metric.get("evaluated", 0)))
            lines.append(f"| {label} | {summary_for_segment['attempted']} | {' | '.join(cells)} |")
    mismatches = [
        (
            record["sample_id"],
            [name for name, matched in record["field_matches"].items() if matched is False],
        )
        for record in report["samples"]
        if any(matched is False for matched in record["field_matches"].values())
    ]
    lines += ["", "## Field mismatch examples", ""]
    if mismatches:
        lines.extend(
            f"- `{sample_id}`: {', '.join(fields)}" for sample_id, fields in mismatches[:100]
        )
    else:
        lines.append("No verified-label field mismatches were measured.")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines += [
        "",
        "Sample-level discrepancies are listed by sample ID in `report.json`; no receipt text or field values are included.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, csv_path, md_path


def _format_rate(value: float | None, n: int) -> str:
    return "not measured" if value is None else f"{value:.1%} (n={n})"


def _new_output_dir(dataset_dir: Path, prefix: str) -> Path:
    repository = Path(__file__).resolve().parents[2]
    try:
        dataset_dir.resolve().relative_to(repository)
    except ValueError:
        pass
    else:
        raise ValueError("benchmark results must be stored outside the Git repository")
    base = dataset_dir / "results"
    base.mkdir(parents=True, exist_ok=True)
    while True:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        candidate = base / f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"
        if not candidate.exists():
            return candidate


def _write_run_report(
    dataset: DatasetResult, records: list[dict[str, Any]], dataset_dir: Path
) -> Path:
    run_id = uuid.uuid4().hex
    report = build_report(dataset, records, run_id)
    output_dir = _new_output_dir(dataset_dir, "run")
    _write_report_files(output_dir, report)
    return output_dir


def _base_url_is_loopback(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.hostname
        in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
    )


def _request_with_retry(
    client: httpx.Client, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return response
            try:
                retry_after = float(response.headers.get("Retry-After", "1"))
            except ValueError:
                retry_after = 1.0
            time.sleep(min(2.0, max(0.0, retry_after)))
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("request retry loop ended without a response")


def _require_success(response: httpx.Response) -> None:
    if response.is_error:
        raise LocalApiFailure(response.status_code)


def _check_live_approval(dataset: DatasetResult, samples: list[ValidSample]) -> None:
    if not dataset.is_valid:
        raise ValueError(
            "dataset validation failed; resolve every manifest/image/ground-truth issue first"
        )
    not_approved = [
        sample.metadata["id"]
        for sample in samples
        if sample.metadata["cloud_inference_approved"] is not True
    ]
    if not_approved:
        raise ValueError("cloud inference approval is missing for selected sample(s)")


def run_live(
    dataset: DatasetResult,
    samples: list[ValidSample],
    *,
    base_url: str,
    actor_id: str,
    output_timeout: float,
    cloud_upload_confirmed: bool = False,
    provider_terms_reviewed: bool = False,
    disposable_environment_confirmed: bool = False,
    large_run_confirmed: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> list[dict[str, Any]]:
    _check_live_approval(dataset, samples)
    if not 1 <= len(samples) <= MAX_LIVE_LIMIT:
        raise ValueError(f"live runs must include between 1 and {MAX_LIVE_LIMIT} samples")
    if len(samples) > 5 and not large_run_confirmed:
        raise ValueError("runs above five require explicit large-run confirmation")
    if not provider_terms_reviewed:
        raise ValueError("provider terms must be reviewed before cloud inference")
    if not cloud_upload_confirmed:
        raise ValueError("cloud image upload must be explicitly confirmed")
    if not disposable_environment_confirmed:
        raise ValueError("confirm a disposable local database and private local receipt storage")
    if not _base_url_is_loopback(base_url):
        raise ValueError("live runs are restricted to localhost/loopback Proofline APIs")
    if not actor_id.strip():
        raise ValueError(
            "a seeded demo actor UUID is required via --actor-id or PROOFLINE_BENCHMARK_ACTOR_ID"
        )
    api_root = base_url.rstrip("/") + "/api/v1"
    headers = {"X-Demo-Actor-Id": actor_id, "User-Agent": "Proofline-Receipt-Benchmark/1.0"}
    records: list[dict[str, Any]] = []
    total_start = time.monotonic()
    with httpx.Client(
        timeout=httpx.Timeout(output_timeout),
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:
        meta = _request_with_retry(client, "GET", f"{api_root}/meta", headers=headers)
        _require_success(meta)
        meta_body = meta.json()
        if (
            not isinstance(meta_body, dict)
            or meta_body.get("environment") != "development"
            or meta_body.get("demo_mode") is not True
        ):
            raise ValueError("local API must report environment=development and demo_mode=true")
        for sample in samples:
            started = time.monotonic()
            result_record: dict[str, Any] = {"sample_id": sample.metadata["id"], "elapsed_ms": None}
            try:
                draft = _request_with_retry(
                    client,
                    "POST",
                    f"{api_root}/expenses",
                    headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
                    json={"channel": "web"},
                )
                _require_success(draft)
                expense_id = draft.json()["id"]
                with sample.image_path.open("rb") as image:
                    upload = _request_with_retry(
                        client,
                        "POST",
                        f"{api_root}/expenses/{expense_id}/receipts",
                        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
                        files={"file": ("benchmark-receipt", image, _mime_for(sample.image_path))},
                    )
                _require_success(upload)
                receipt_id = upload.json()["receipt"]["id"]
                deadline = time.monotonic() + output_timeout
                receipt_data: dict[str, Any] = upload.json()["receipt"]
                while (
                    receipt_data.get("extraction_status") in {"pending", "running"}
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.5)
                    poll = _request_with_retry(
                        client, "GET", f"{api_root}/receipts/{receipt_id}", headers=headers
                    )
                    _require_success(poll)
                    receipt_data = poll.json()
                if receipt_data.get("extraction_status") in {"pending", "running"}:
                    result_record["status"] = "timeout"
                    result_record["error_code"] = "RESULT_POLL_TIMEOUT"
                    result_record["receipt_id"] = receipt_id
                    result_record["segments"] = _segments(sample)
                    result_record["field_matches"] = dict.fromkeys(FIELD_NAMES)
                    result_record["field_statuses"] = dict.fromkeys(FIELD_NAMES, "unknown")
                    result_record["line_item_matches"] = {name: [] for name in LINE_FIELD_NAMES}
                    result_record["presence_counts"] = {}
                    result_record["human_review_required"] = None
                else:
                    result_record.update(score_sample(sample, receipt_data))
            except LocalApiFailure as exc:
                result_record.update(
                    {
                        "status": "failed",
                        "error_code": f"LOCAL_API_HTTP_{exc.status_code}",
                        "segments": _segments(sample),
                        "field_matches": dict.fromkeys(FIELD_NAMES),
                        "field_statuses": dict.fromkeys(FIELD_NAMES, "unknown"),
                        "line_item_matches": {name: [] for name in LINE_FIELD_NAMES},
                        "presence_counts": {},
                        "human_review_required": None,
                    }
                )
            except httpx.TimeoutException:
                result_record.update(
                    {
                        "status": "failed",
                        "error_code": "LOCAL_API_TIMEOUT",
                        "segments": _segments(sample),
                        "field_matches": dict.fromkeys(FIELD_NAMES),
                        "field_statuses": dict.fromkeys(FIELD_NAMES, "unknown"),
                        "line_item_matches": {name: [] for name in LINE_FIELD_NAMES},
                        "presence_counts": {},
                        "human_review_required": None,
                    }
                )
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                # Keep errors non-sensitive: no response body, URL query, headers, or receipt data.
                result_record.update(
                    {
                        "status": "failed",
                        "error_code": "LOCAL_API_REQUEST_FAILED",
                        "error_type": type(exc).__name__,
                        "segments": _segments(sample),
                        "field_matches": dict.fromkeys(FIELD_NAMES),
                        "field_statuses": dict.fromkeys(FIELD_NAMES, "unknown"),
                        "line_item_matches": {name: [] for name in LINE_FIELD_NAMES},
                        "presence_counts": {},
                        "human_review_required": None,
                    }
                )
            result_record["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            records.append(result_record)
    if records:
        records[0]["total_run_elapsed_ms"] = round((time.monotonic() - total_start) * 1000)
    return records


def _segments(sample: ValidSample) -> dict[str, str]:
    return {
        "category": sample.metadata["category"],
        "quality": sample.metadata["quality"],
        "authenticity": sample.metadata["authenticity"],
        "annotation_completeness": sample.annotation_completeness,
    }


def _mime_for(path: Path) -> str:
    if Image is None:
        raise ValueError("Pillow is required to identify validated image media types")
    with Image.open(path) as image:
        return {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
            image.format or "", "application/octet-stream"
        )


def score_results(dataset: DatasetResult, results_file: Path) -> list[dict[str, Any]]:
    data = json.loads(results_file.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("report_schema_version") != 1
        or not isinstance(data.get("samples"), list)
    ):
        raise ValueError("results file is not a supported benchmark report")
    by_id = {sample.metadata["id"]: sample for sample in dataset.valid_samples}
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for saved in data["samples"]:
        if not isinstance(saved, dict) or saved.get("sample_id") not in by_id:
            raise ValueError("results contain a sample id not present in the validated dataset")
        sample_id = str(saved["sample_id"])
        if sample_id in seen:
            raise ValueError("results contain the same sample more than once")
        seen.add(sample_id)
        sample = by_id[sample_id]
        matches = saved.get("field_matches")
        line_matches = saved.get("line_item_matches")
        if not isinstance(matches, dict) or not isinstance(line_matches, dict):
            raise ValueError("results sample is missing scoring fields")
        safe_matches = {
            name: matches.get(name) if isinstance(matches.get(name), bool) else None
            for name in FIELD_NAMES
        }
        safe_statuses = {
            name: _safe_field_status(saved.get("field_statuses", {}).get(name))
            if isinstance(saved.get("field_statuses"), dict)
            else "unknown"
            for name in FIELD_NAMES
        }
        safe_line_matches: dict[str, list[bool | None]] = {}
        for name in LINE_FIELD_NAMES:
            value = line_matches.get(name, [])
            safe_line_matches[name] = (
                [cell if isinstance(cell, bool) else None for cell in value[:100]]
                if isinstance(value, list)
                else []
            )
        raw_presence = saved.get("presence_counts")
        safe_presence: dict[str, dict[str, int]] = {}
        if isinstance(raw_presence, dict):
            for name in FIELD_NAMES:
                values = raw_presence.get(name)
                if isinstance(values, dict):
                    safe_presence[name] = {
                        key: count
                        for key in (
                            "predicted_present",
                            "true_positive",
                            "positive",
                            "negative",
                            "true_negative",
                        )
                        if type(count := values.get(key)) is int and count >= 0
                    }
        status = saved.get("status")
        if status not in {
            "success",
            "partial",
            "failed",
            "unavailable",
            "pending",
            "running",
            "timeout",
        }:
            status = "failed"
        receipt_id = saved.get("receipt_id")
        try:
            receipt_id = str(uuid.UUID(receipt_id)) if isinstance(receipt_id, str) else None
        except ValueError:
            receipt_id = None
        safe_record: dict[str, Any] = {
            "sample_id": sample_id,
            "receipt_id": receipt_id,
            "provider": _safe_identifier(saved.get("provider")),
            "model": _safe_identifier(saved.get("model")),
            "status": status,
            "attempt_count": _safe_nonnegative_int(saved.get("attempt_count")),
            "latency_ms": _safe_nonnegative_int(saved.get("latency_ms")),
            "elapsed_ms": _safe_nonnegative_int(saved.get("elapsed_ms")),
            "human_review_required": saved.get("human_review_required")
            if isinstance(saved.get("human_review_required"), bool)
            else None,
            "field_matches": safe_matches,
            "field_statuses": safe_statuses,
            "line_item_matches": safe_line_matches,
            "presence_counts": safe_presence,
            "segments": _segments(sample),
        }
        if (
            isinstance(saved.get("total_run_elapsed_ms"), int)
            and saved["total_run_elapsed_ms"] >= 0
        ):
            safe_record["total_run_elapsed_ms"] = saved["total_run_elapsed_ms"]
        records.append(safe_record)
    return records


def _safe_nonnegative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _safe_identifier(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,120}", value):
        return value
    return None


def _validate_command(args: argparse.Namespace) -> int:
    dataset = validate_dataset(args.dataset or discover_dataset())
    print(json.dumps(dataset.public_report(), indent=2))
    return 0 if dataset.is_valid else 2


def _run_command(args: argparse.Namespace) -> int:
    if not args.live:
        dataset = validate_dataset(args.dataset or discover_dataset())
        print(json.dumps(dataset.public_report(), indent=2))
        print("Offline mode: no API or provider calls made.")
        return 0 if dataset.is_valid else 2
    directory = (args.dataset or discover_dataset()).resolve()
    dataset = validate_dataset(directory)
    if not dataset.is_valid:
        print(json.dumps(dataset.public_report(), indent=2))
        return 2
    available_count = len(dataset.valid_samples)
    selected_limit = args.limit if args.limit is not None else min(5, available_count)
    if selected_limit < 1 or selected_limit > MAX_LIVE_LIMIT:
        raise ValueError(f"--limit must be between 1 and {MAX_LIVE_LIMIT}")
    if selected_limit > 5 and not args.allow_large_run:
        raise ValueError("runs above five require --allow-large-run and an explicit --limit")
    if selected_limit > available_count:
        raise ValueError("--limit exceeds the number of validated samples")
    if not args.provider_terms_reviewed:
        raise ValueError(
            "--provider-terms-reviewed is required after reviewing applicable provider terms"
        )
    actor = args.actor_id or os.environ.get("PROOFLINE_BENCHMARK_ACTOR_ID", "")
    selected = sorted(dataset.valid_samples, key=lambda sample: sample.metadata["id"])[
        :selected_limit
    ]
    _check_live_approval(dataset, selected)
    if not args.confirm_cloud_upload:
        raise ValueError(
            "--confirm-cloud-upload is required to confirm approved images may be sent for inference"
        )
    records = run_live(
        dataset,
        selected,
        base_url=args.base_url,
        actor_id=actor,
        output_timeout=args.timeout,
        cloud_upload_confirmed=args.confirm_cloud_upload,
        provider_terms_reviewed=args.provider_terms_reviewed,
        disposable_environment_confirmed=args.confirm_disposable_environment,
        large_run_confirmed=args.allow_large_run,
    )
    output = _write_run_report(dataset, records, directory)
    print(
        json.dumps(
            {"run_directory": str(output), "attempted": len(records), "live": True}, indent=2
        )
    )
    return 0


def _score_command(args: argparse.Namespace) -> int:
    dataset = validate_dataset(args.dataset or discover_dataset())
    if not dataset.is_valid:
        print(json.dumps(dataset.public_report(), indent=2))
        return 2
    records = score_results(dataset, args.results)
    report = build_report(dataset, records, uuid.uuid4().hex)
    output = _new_output_dir(dataset.root, "score")
    _write_report_files(output, report)
    print(json.dumps({"report_directory": str(output), "scored": len(records)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser(
        "validate", help="validate manifest, annotations and images offline"
    )
    validate.add_argument("--dataset", type=Path)
    validate.set_defaults(handler=_validate_command)
    run = subparsers.add_parser(
        "run", help="default offline; --live opts into local API/cloud inference"
    )
    run.add_argument("--dataset", type=Path)
    run.add_argument("--live", action="store_true")
    run.add_argument("--limit", type=int)
    run.add_argument("--allow-large-run", action="store_true")
    run.add_argument("--confirm-cloud-upload", action="store_true")
    run.add_argument("--confirm-disposable-environment", action="store_true")
    run.add_argument("--provider-terms-reviewed", action="store_true")
    run.add_argument("--base-url", default="http://127.0.0.1:8000")
    run.add_argument("--actor-id")
    run.add_argument("--timeout", type=float, default=180.0)
    run.set_defaults(handler=_run_command)
    score = subparsers.add_parser(
        "score", help="score a saved report against validated ground truth"
    )
    score.add_argument("--dataset", type=Path)
    score.add_argument("--results", type=Path, required=True)
    score.set_defaults(handler=_score_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        if isinstance(result, int):
            return result
        raise TypeError("command handler returned an invalid exit code")
    except httpx.HTTPError as exc:
        print(f"error: local Proofline API request failed ({type(exc).__name__})", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
