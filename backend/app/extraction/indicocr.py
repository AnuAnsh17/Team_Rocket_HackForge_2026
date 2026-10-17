"""Persistent subprocess adapter for the locally installed IndicOCR runtime.

IndicOCR's Torch stack is intentionally isolated from the FastAPI environment. One
worker process loads the model once and accepts serialized page requests over stdin;
stdout is reserved for a small JSON protocol and stderr is discarded so receipt text
or model diagnostics cannot leak into application logs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.enums import ExtractionStatus
from app.extraction.base import ExtractionResult


class IndicOCRRuntimeError(RuntimeError):
    """The configured isolated IndicOCR runtime cannot be started."""


class IndicOCRUnsupportedMediaType(ValueError):
    """The installed IndicOCR parser accepts image pages, not this upload type."""


class IndicOCRWorker:
    """One lazily started IndicOCR process, serialized across concurrent requests."""

    def __init__(
        self,
        *,
        python_executable: str,
        model_path: str,
        timeout_seconds: int,
    ) -> None:
        self._python = Path(python_executable)
        self._model = Path(model_path)
        self._timeout = timeout_seconds
        self._worker_script = Path(__file__).with_name("indicocr_worker.py")
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()

    def extract_page(self, *, data: bytes, content_type: str) -> dict[str, Any]:
        if content_type in {"application/pdf", "image/heic", "image/heif"}:
            raise IndicOCRUnsupportedMediaType(
                "IndicOCR currently accepts JPEG, PNG and WEBP image pages only."
            )
        if content_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise IndicOCRUnsupportedMediaType("IndicOCR does not support this receipt media type.")

        with self._lock:
            self._ensure_started()
            process = self._process
            if process is None or process.stdin is None:
                raise IndicOCRRuntimeError("IndicOCR worker is unavailable.")
            request = json.dumps(
                {"data": base64.b64encode(data).decode("ascii"), "content_type": content_type},
                separators=(",", ":"),
            )
            try:
                process.stdin.write(request + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._stop_worker()
                raise IndicOCRRuntimeError(
                    "IndicOCR worker exited while receiving a page."
                ) from exc

            response = self._read_response()
            if response is None:
                self._stop_worker()
                raise IndicOCRRuntimeError("IndicOCR worker exited without a result.")
            try:
                payload = json.loads(response)
            except json.JSONDecodeError as exc:
                self._stop_worker()
                raise ValueError("IndicOCR worker returned malformed protocol data.") from exc
            if not isinstance(payload, dict):
                self._stop_worker()
                raise ValueError("IndicOCR worker returned an invalid response envelope.")
            if payload.get("event") == "error":
                error_type = payload.get("error_type")
                if not isinstance(error_type, str) or not error_type.isidentifier():
                    error_type = "UnknownError"
                if error_type == "ValueError":
                    raise ValueError("IndicOCR rejected its page output or source image.")
                raise RuntimeError(f"IndicOCR processing failed ({error_type}).")
            if payload.get("event") != "result":
                self._stop_worker()
                raise ValueError("IndicOCR worker returned an unknown response event.")
            page = payload.get("page")
            self._validate_page(page)
            return {"page": page, "latency_ms": payload.get("latency_ms")}

    def close(self) -> None:
        with self._lock:
            self._stop_worker()

    def _ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not self._python.is_file():
            raise IndicOCRRuntimeError("Configured IndicOCR Python executable was not found.")
        if not self._model.is_dir():
            raise IndicOCRRuntimeError("Configured IndicOCR model directory was not found.")
        if not self._worker_script.is_file():
            raise IndicOCRRuntimeError("IndicOCR worker entry point is missing.")
        self._responses = queue.Queue()
        try:
            self._process = subprocess.Popen(
                [str(self._python), "-u", str(self._worker_script), str(self._model)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            self._process = None
            raise IndicOCRRuntimeError("Could not start the configured IndicOCR runtime.") from exc

        assert self._process.stdout is not None
        reader = threading.Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            name="indicocr-protocol-reader",
            daemon=True,
        )
        reader.start()
        ready = self._read_response()
        if ready is None:
            self._stop_worker()
            raise IndicOCRRuntimeError("IndicOCR worker stopped before becoming ready.")
        try:
            event = json.loads(ready)
        except json.JSONDecodeError as exc:
            self._stop_worker()
            raise IndicOCRRuntimeError("IndicOCR worker returned malformed startup data.") from exc
        if not isinstance(event, dict) or event.get("event") != "ready":
            self._stop_worker()
            raise IndicOCRRuntimeError("IndicOCR worker failed to initialize.")

    def _read_response(self) -> str | None:
        try:
            return self._responses.get(timeout=self._timeout)
        except queue.Empty as exc:
            self._stop_worker()
            raise TimeoutError("IndicOCR exceeded its configured processing timeout.") from exc

    def _read_stdout(self, stream: Any) -> None:
        try:
            for line in stream:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def _stop_worker(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for pipe in (process.stdin, process.stdout):
            if pipe is not None:
                pipe.close()

    @staticmethod
    def _validate_page(page: object) -> None:
        if not isinstance(page, dict):
            raise ValueError("IndicOCR returned a page that was not an object.")
        if not {"image", "width", "height", "blocks", "markdown"}.issubset(page):
            raise ValueError("IndicOCR page is missing documented fields.")
        if not isinstance(page["image"], str):
            raise ValueError("IndicOCR page image name is invalid.")
        if type(page["width"]) is not int or page["width"] <= 0:
            raise ValueError("IndicOCR page width is invalid.")
        if type(page["height"]) is not int or page["height"] <= 0:
            raise ValueError("IndicOCR page height is invalid.")
        if not isinstance(page["markdown"], str) or not isinstance(page["blocks"], list):
            raise ValueError("IndicOCR markdown or block collection is invalid.")
        orders: list[int] = []
        for block in page["blocks"]:
            if not isinstance(block, dict) or not {"order", "bbox_xyxy", "text"}.issubset(block):
                raise ValueError("IndicOCR returned an invalid text block.")
            order = block["order"]
            box = block["bbox_xyxy"]
            if type(order) is not int or order < 0 or not isinstance(block["text"], str):
                raise ValueError("IndicOCR block order or text is invalid.")
            if (
                not isinstance(box, list)
                or len(box) != 4
                or any(type(value) not in {int, float} for value in box)
            ):
                raise ValueError("IndicOCR block coordinates are invalid.")
            orders.append(order)
        if sorted(orders) != list(range(len(orders))):
            raise ValueError("IndicOCR block order is not a gap-free sequence.")


class IndicOCRExtractor:
    """Map verified IndicOCR page output to the provider-neutral OCR result."""

    provider_name = "indicocr"

    def __init__(self, worker: IndicOCRWorker) -> None:
        self._worker = worker

    def extract(self, *, receipt_id: uuid.UUID, data: bytes, content_type: str) -> ExtractionResult:
        del receipt_id  # The local OCR engine receives only the page bytes.
        started = time.perf_counter()
        try:
            if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise IndicOCRUnsupportedMediaType(
                    "IndicOCR currently accepts JPEG, PNG and WEBP image pages only."
                )
            result = self._worker.extract_page(data=data, content_type=content_type)
            if not isinstance(result, dict) or "page" not in result:
                raise ValueError("IndicOCR worker returned an invalid result envelope.")
            page = result["page"]
            IndicOCRWorker._validate_page(page)
        except TimeoutError:
            return self._failure(ExtractionStatus.FAILED, "OCR_TIMEOUT")
        except IndicOCRRuntimeError:
            return self._failure(ExtractionStatus.UNAVAILABLE, "OCR_RUNTIME_UNAVAILABLE")
        except IndicOCRUnsupportedMediaType:
            return self._failure(ExtractionStatus.FAILED, "OCR_UNSUPPORTED_MEDIA_TYPE")
        except ValueError:
            return self._failure(ExtractionStatus.FAILED, "OCR_INVALID_OUTPUT")
        except Exception:
            return self._failure(ExtractionStatus.FAILED, "OCR_PROCESSING_FAILED")
        raw_text = page["markdown"]
        raw_payload = json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return ExtractionResult(
            status=ExtractionStatus.SUCCESS,
            provider=self.provider_name,
            model="bodhan-ai/indic-ocr",
            fields={},
            line_items=(),
            raw_text=raw_text,
            raw_payload_sha256=hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
            latency_ms=(
                result["latency_ms"]
                if type(result.get("latency_ms")) is int and result["latency_ms"] >= 0
                else round((time.perf_counter() - started) * 1000)
            ),
        )

    def close(self) -> None:
        self._worker.close()

    def _failure(self, status: ExtractionStatus, code: str) -> ExtractionResult:
        return ExtractionResult(
            status=status,
            provider=self.provider_name,
            model="bodhan-ai/indic-ocr",
            error_code=code,
            error_message=(
                "IndicOCR is unavailable in this runtime."
                if status is ExtractionStatus.UNAVAILABLE
                else "IndicOCR did not produce a valid page result."
            ),
        )
