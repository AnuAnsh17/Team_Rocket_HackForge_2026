# Receipt benchmark harness

The tool at `backend/scripts/receipt_benchmark.py` validates a labelled dataset,
optionally exercises the existing local Proofline API, and scores saved extraction
results. It never calls the provider adapter directly. The backend remains responsible
for upload validation, authorization, persistence and provider calls.

No live run was made while this harness was built. The Desktop collection workspace
currently has no `manifest.json` or reviewed ground-truth files, so it is not ready for
validation or inference.

## Environment and commands

Install the optional image-decoding dependency in the backend virtual environment:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev,benchmark]"
```

The command discovers `Desktop/ProoflineReceiptBenchmark` at runtime (including common
OneDrive Desktop locations); pass `--dataset` to select another directory.

Offline validation (never contacts Proofline or an inference provider):

```powershell
.\.venv\Scripts\python.exe scripts\receipt_benchmark.py validate
.\.venv\Scripts\python.exe scripts\receipt_benchmark.py validate --dataset "C:\path\to\ProoflineReceiptBenchmark"
```

An offline default run is also safe and makes no requests:

```powershell
.\.venv\Scripts\python.exe scripts\receipt_benchmark.py run --dataset "C:\path\to\ProoflineReceiptBenchmark"
```

The exact opt-in command for at most five approved samples against a local disposable
Proofline instance is:

```powershell
$env:PROOFLINE_BENCHMARK_ACTOR_ID = "<seeded demo user UUID>"
.\.venv\Scripts\python.exe scripts\receipt_benchmark.py run `
  --dataset "$env:USERPROFILE\Desktop\ProoflineReceiptBenchmark" `
  --live --limit 5 --base-url http://127.0.0.1:8000 `
  --provider-terms-reviewed --confirm-cloud-upload --confirm-disposable-environment
```

The runner rejects non-loopback API URLs and first requires `/api/v1/meta` to report
`environment=development` and `demo_mode=true`. It also requires the existing demo
identity header and the operator's `--confirm-disposable-environment` attestation that
the database is disposable and receipt storage is private/local. The configured backend
alone holds the OpenCode Go credential. Every selected sample must have
`privacy_review: "approved"` and
`cloud_inference_approved: true`. Before a real run, an operator must verify that the
selected provider/model and intended image use are allowed under the applicable terms;
`--provider-terms-reviewed` records that operator attestation. The separate
`--confirm-cloud-upload` flag confirms that the approved image bytes may leave the
machine. The runner also requires an explicit `--limit` above five and
`--allow-large-run`, and caps one invocation at 100 samples. Use a disposable local DB
and local private receipt storage, never production data.

Saved results can be re-scored without any API calls:

```powershell
.\.venv\Scripts\python.exe scripts\receipt_benchmark.py score `
  --dataset "$env:USERPROFILE\Desktop\ProoflineReceiptBenchmark" `
  --results "$env:USERPROFILE\Desktop\ProoflineReceiptBenchmark\results\run-...\report.json"
```

Each invocation creates a unique directory under the dataset's `results/`, containing
`report.json`, `samples.csv` and `report.md`; existing outputs are not overwritten.
Reports contain sample IDs, statuses, field match booleans/statuses, segmentation and
timings. They do not include images, extracted field values, OCR text, filenames,
credentials, or authorization headers.

## Dataset schema (version 1)

Create `manifest.json` at the dataset root. Paths are relative to that root and cannot
escape it; image files must decode fully as JPEG, PNG or WebP. Sample IDs must use the
pseudonymous `sample-<token>` form and be unique, and content SHA-256 hashes must not
repeat. A duplicate-hash group is reported and all members are invalid until a curator
resolves the duplicate. `license` provides dataset-level rights
attribution; each sample also records its source.

```json
{
  "schema_version": 1,
  "dataset_id": "receipts-2026-01",
  "license": {"name": "License name", "url": "https://example.org/license"},
  "samples": [
    {
      "id": "sample-0001",
      "image": "images/sample-0001.png",
      "ground_truth": "ground_truth/sample-0001.json",
      "category": "food",
      "quality": "good",
      "authenticity": "synthetic",
      "source_attribution": {"name": "Source/dataset", "uri": "https://example.org/source"},
      "privacy_review": "approved",
      "cloud_inference_approved": false
    }
  ]
}
```

`category` is one of `food`, `hotel`, `ground_transport`, `tickets`, `fuel`, `retail`,
`other`; `quality` is `good` or `medium`; `authenticity` is `authentic` or `synthetic`.
The privacy and cloud fields are explicit per sample. Validation can pass while cloud
inference remains unapproved; a live run refuses unapproved selected samples.

Each referenced ground-truth JSON file has the canonical extraction field names and
separate source-annotation labels. `verified_value` requires a schema-valid `value`;
the other annotation kinds must omit `value` (or set it to null). The latter are never
scored as errors. In particular, `unannotated` is not an assertion of absence.

```json
{
  "schema_version": 1,
  "sample_id": "sample-0001",
  "fields": {
    "merchant": {"annotation": "verified_value", "value": "Illustrative Cafe"},
    "transaction_date": {"annotation": "verified_value", "value": "2025-02-03"},
    "currency": {"annotation": "verified_value", "value": "USD"},
    "subtotal": {"annotation": "verified_value", "value": "10.00"},
    "tax_total": {"annotation": "verified_absent"},
    "tip": {"annotation": "ambiguous"},
    "discount": {"annotation": "illegible"},
    "grand_total": {"annotation": "verified_value", "value": "10.00"},
    "receipt_number": {"annotation": "unannotated"}
  },
  "line_items": {
    "annotation": "verified_value",
    "value": [
      {
        "description": {"annotation": "verified_value", "value": "Tea"},
        "quantity": {"annotation": "verified_value", "value": "2"},
        "unit_price": {"annotation": "verified_value", "value": "5.00"},
        "line_total": {"annotation": "verified_value", "value": "10.00"}
      }
    ]
  }
}
```

The values above are schema examples only and are not benchmark results or annotations
for any supplied receipt. All nine scalar fields are required. `line_items.annotation`
can use the same five source-label kinds; a `verified_absent` annotation is distinct
from an empty or unannotated array. Annotation completeness is derived: all verified
values/absences means complete; any ambiguous, illegible or unannotated field means
partial.

## Matching and metrics

- Merchant and line-item descriptions: trim and collapse whitespace, then Unicode
  case-fold. No fuzzy or punctuation-based matching is applied.
- Dates and receipt numbers: exact canonical string equality; dates must be ISO
  `YYYY-MM-DD` by the production extraction schema.
- Currency: uppercase string equality; the ground-truth schema requires three uppercase
  ISO-style letters.
- Money, quantity and unit price: finite `Decimal` equality; no tolerance or float
  conversion is used.
- A `verified_value` is positive for presence detection if the model says `extracted`
  with a value. A `verified_absent` is negative if the model says `missing` or
  `not_applicable` without a value. Value accuracy is reported separately, so a wrong
  amount can still count as detection of a present field.
- Ambiguous, illegible and unannotated values are excluded from field accuracy and
  field-presence denominators. Missing/uncertain labels never become negative examples.
- Line items compare by source order and position. No row-matching heuristic is used;
  reorderings are visible errors.
- The API's `latency_ms` is reported as provider latency. Runner wall time per sample
  is reported separately as end-to-end latency. p95 is withheld below 20 measurements.
  Human-review rate is reported only when API validation metadata exists. Provider cost
  is explicitly unavailable unless a reliable cost field becomes part of the API.
- Category, quality, authenticity and annotation-completeness metrics are emitted as
  separate segments. Synthetic and authentic samples are never silently blended.

## Output shape (illustrative only)

```text
report.json
  report_schema_version, run_id, generated_at
  dataset: size, validation_valid, distributions, annotation_completeness
  summary: attempted/completed/partial/failed, field_accuracy, field_presence,
           line_item_accuracy, latency_ms, human_review_rate, provider_cost=null
  segments: category / quality / authenticity / annotation_completeness
  samples: sample_id, receipt_id, provider/model, status, timings, field match booleans
report.md
  concise status, counts, latency, field-accuracy table, limitations
samples.csv
  one row per sample, with no extracted text or field values
```

The JSON includes discrepancy indicators by sample ID, not the extracted or expected
field values. No percentage from synthetic fixtures is a product accuracy claim.

Illustrative excerpt from a hypothetical one-sample synthetic run (structure only; not
a measured result):

```json
{
  "dataset": {
    "size": 1,
    "validation_valid": true,
    "category_quality_authenticity_distribution": {
      "category": {"food": 1},
      "quality": {"good": 1},
      "authenticity": {"synthetic": 1}
    }
  },
  "summary": {
    "attempted": 1,
    "completed": 1,
    "failed": 0,
    "field_accuracy": {
      "grand_total": {"correct": 1, "evaluated": 1, "accuracy": 1.0}
    },
    "provider_cost": null
  },
  "samples": [
    {
      "sample_id": "sample-demo-001",
      "status": "success",
      "field_matches": {"grand_total": true},
      "segments": {"authenticity": "synthetic"}
    }
  ]
}
```

## Remaining dataset prerequisites

The current Desktop folder is a collection workspace only. Before validation, its owner
must add a version-1 manifest, source/license attribution, stable IDs, image/ground-truth
references, category/quality/authenticity tags and field labels reviewed by a human.
Before any cloud run, the reviewer must additionally attest privacy review and
per-sample cloud-use approval, and confirm provider terms. No live inference was executed
as part of building this harness.
