# Receipt extraction runtime

## Provider selection

The API and clients never call an extraction provider directly. Set the backend's
`EXTRACTION_PROVIDER` to one of:

- `opencode_go` for the `deepseek-v4.1-flash` model through the OpenCode Go
  subscription. Configure `OPENCODE_GO_API_KEY` only in the backend's ignored
  local `.env` or deployment secret store. `OPENCODE_GO_BASE_URL` defaults to
  `https://opencode.ai/zen/go/v1`; the adapter calls `/chat/completions`.
  Requests identify Proofline with its own User-Agent and use the stable receipt
  UUID as `x-opencode-session` for Go session routing.
  OpenCode's Go catalog lists this model as accepting text and image input. Its
  documented catalog also lists `deepseek-v4-flash-vision-exp` as an explicit
  vision model, but the configured model is not silently replaced.
- `local_ocr` for IndicOCR. Set `EXTRACTION_MODEL` to the existing cached model
  directory and `EXTRACTION_PYTHON_EXECUTABLE` to the already installed isolated
  Python runtime. IndicOCR remains an OCR-only provider and does not produce
  structured fields.
- `unavailable` to accept the receipt workflow while reporting extraction as
  unavailable. No fake fields are returned.

No API credential belongs in `.env.example`, a browser/mobile environment variable,
or a client bundle. The example file contains blank credential placeholders only.

## Upload and status flow

Create an employee-owned draft with `POST /api/v1/expenses`, then upload one receipt
with `POST /api/v1/expenses/{expense_id}/receipts` or 1–20 files with
`POST /api/v1/expenses/{expense_id}/receipts/batch`. Every file is independently
validated by signature and size, hashed, stored privately and associated with a
persisted `pending` extraction run before the request completes. The app-scoped
worker claims persisted runs and commits `running` before provider I/O. Read
`GET /api/v1/expenses/{expense_id}/receipts` to see each independent status/result.
The original file is only available through the authorized content route.

Supported upload types are JPEG, PNG and WebP, maximum 10 MiB each by default.
Unsupported, empty, mislabeled or oversized data is rejected before storage. OpenCode Go
provider errors, malformed output, empty output and truncation become stable failed or
unavailable states. A single failed receipt does not prevent other pending runs from
being claimed. Retry uses `POST /api/v1/receipts/{receipt_id}/extractions`, requires
owner authorization and an idempotency key, and appends a new historical run.

`EXTRACTION_CONCURRENCY` bounds simultaneous jobs within each backend process
(default 2). HTTP requests and database sessions remain outside long provider
transactions. On restart, old `running` jobs become failed instead of being
re-sent automatically, avoiding an implicit duplicate provider charge. Explicit
retry is available to the owner. The poller is in-process and per-process; deployments
must run one API process for predictable concurrency until distributed worker
coordination is added. Shutdown stops claiming new runs and drains active calls.

## Data and review

The versioned structured payload has schema version `1.0`; each field contains a
value and an explicit extracted/missing/ambiguous/illegible/not-applicable status.
Money is persisted and returned as decimal strings. Only validated normalized fields
and deterministic validation results are stored. The provider's complete message,
source quotations, OCR Markdown and base64 image are not stored or returned while
retention policy is unresolved. The source receipt ID and SHA-256 remain available as
provenance. Arithmetic reconciliation is a review signal only; it never changes
model output, makes a policy decision or alleges fraud.

## Local checks and optional live call

Run offline adapter/schema tests with:

```powershell
cd backend
$env:APP_ENV = 'test'
$env:TEST_DATABASE_URL = 'postgresql+psycopg://proofline:proofline@localhost:55432/proofline_receipt_ai_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m pytest tests/unit/test_deepseek_extractor.py tests/unit/test_extraction_schema.py -q
```

A live OpenCode Go inference requires an authorized synthetic or rights-cleared image
and a locally configured `OPENCODE_GO_API_KEY`; it uses your Go subscription. There is
no default live test in CI. From `backend/`, set `RUN_OPENCODE_GO_INTEGRATION=1` and
`OPENCODE_GO_API_KEY` in the local process environment. Point `DATABASE_URL` and
`TEST_DATABASE_URL` at a disposable isolated PostgreSQL database, then run:

```powershell
$env:APP_ENV = 'test'
$env:TEST_DATABASE_URL = 'postgresql+psycopg://proofline:proofline@localhost:55432/proofline_receipt_ai_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:RUN_OPENCODE_GO_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_deepseek_live.py -q
```

No labeled receipt benchmark or accuracy claim is included in this implementation.
