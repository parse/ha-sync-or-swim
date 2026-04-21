#!/usr/bin/env python3
"""Check that the generated Python contract is up to date with backend/openapi.json."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_PATH = ROOT / "custom_components" / "pahlen_monitor" / "generated_api.py"
GENERATOR_PATH = ROOT / "scripts" / "generate_python_contract.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_python_contract", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    generator = _load_generator()
    expected = generator.render_contract()
    current = GENERATED_PATH.read_text(encoding="utf-8")
    if current != expected:
        raise SystemExit(
            "Generated Python contract is out of date. Run: python3 scripts/generate_python_contract.py"
        )

    print("Generated Python contract matches backend/openapi.json.")


if __name__ == "__main__":
    main()
