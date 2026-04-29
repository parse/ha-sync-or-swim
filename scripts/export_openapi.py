from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
DEFAULT_OUTPUT = REPO_ROOT / "openapi.json"


def export_openapi(output: Path) -> None:
    """Export the FastAPI OpenAPI schema without requiring production settings."""

    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pahlen-monitor-openapi.db")
    sys.path.insert(0, str(BACKEND_SRC))

    from main import app

    output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export backend OpenAPI schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the OpenAPI JSON schema.",
    )
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
