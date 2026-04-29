from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from export_openapi import export_openapi

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_TYPES = (
    REPO_ROOT / "custom_components" / "pahlen_monitor" / "generated_api_types.py"
)


def generate_types(output: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        openapi_path = Path(temp_dir) / "openapi.json"
        export_openapi(openapi_path)
        output.unlink(missing_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "datamodel_code_generator",
                "--input",
                str(openapi_path),
                "--input-file-type",
                "openapi",
                "--output",
                str(output),
                "--output-model-type",
                "typing.TypedDict",
                "--target-python-version",
                "3.11",
                "--formatters",
                "ruff-format",
                "ruff-check",
                "--disable-timestamp",
                "--disable-warnings",
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--quiet", str(output)],
            check=True,
            cwd=REPO_ROOT,
        )


def check_generated_types() -> bool:
    with tempfile.TemporaryDirectory(
        prefix=".api-type-check-", dir=REPO_ROOT
    ) as temp_dir:
        candidate = Path(temp_dir) / "generated_api_types.py"
        generate_types(candidate)
        return candidate.read_text(encoding="utf-8") == GENERATED_TYPES.read_text(
            encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Home Assistant API types from backend OpenAPI."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed generated types are stale.",
    )
    args = parser.parse_args()

    if args.check:
        if check_generated_types():
            return
        print(
            f"{GENERATED_TYPES.relative_to(REPO_ROOT)} is stale. "
            "Run scripts/generate_api_types.py.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    generate_types(GENERATED_TYPES)


if __name__ == "__main__":
    main()
