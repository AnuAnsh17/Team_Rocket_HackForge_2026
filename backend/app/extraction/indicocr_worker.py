"""Line-oriented IPC worker, launched only by the backend IndicOCR adapter."""

from __future__ import annotations

import base64
import importlib
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

_EXTENSION_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _write(payload: dict[str, object]) -> None:
    # ASCII escapes keep protocol writes portable across Windows console encodings,
    # including OCR output containing Indic scripts.
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    model_path = Path(sys.argv[1])
    sys.path.insert(0, str(model_path))
    try:
        with redirect_stdout(sys.stderr):
            torch = importlib.import_module("torch")
            indic_ocr = importlib.import_module("indic_ocr")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            parser = indic_ocr.IndicOCR.from_pretrained(str(model_path), device=device)
    except Exception as exc:
        _write({"event": "error", "error_type": type(exc).__name__})
        return 1

    _write({"event": "ready"})
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request envelope must be an object")
            content_type = request.get("content_type")
            encoded = request.get("data")
            if content_type not in _EXTENSION_BY_MIME or not isinstance(encoded, str):
                raise ValueError("request does not contain a supported image")
            data = base64.b64decode(encoded, validate=True)
            with tempfile.TemporaryDirectory(prefix="proofline-indicocr-") as folder:
                image_path = Path(folder) / ("page" + _EXTENSION_BY_MIME[content_type])
                image_path.write_bytes(data)
                started = time.perf_counter()
                with redirect_stdout(sys.stderr):
                    page = parser.parse(str(image_path))
                elapsed_ms = round((time.perf_counter() - started) * 1000)
            _write({"event": "result", "page": page, "latency_ms": elapsed_ms})
        except Exception as exc:
            # Keep exception messages and OCR text out of backend logs/protocol diagnostics.
            _write({"event": "error", "error_type": type(exc).__name__})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
