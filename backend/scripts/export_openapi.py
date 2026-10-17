"""Export the backend's OpenAPI document for client generation.

Usage:
    cd backend
    ./.venv/Scripts/python scripts/export_openapi.py [output_path]

Default output: ../packages/api-client/openapi.json

Why a committed artifact: `packages/api-client` is generated from this file, and CI
regenerates it and fails if the committed copy differs. That is what turns a contract
drift into a build failure instead of a runtime surprise in one of the three clients.

The document is produced from the running application object, so it reflects exactly
what the service serves - including the enum catalogue and the money schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "packages" / "api-client" / "openapi.json"


def render_spec() -> str:
    """Return the OpenAPI document as stable, reviewable JSON.

    Keys are sorted and the indent is fixed so that a semantic no-op does not produce a
    diff, and a real change produces a small one.
    """
    spec = create_app().openapi()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    content = render_spec()
    output.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {output} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
