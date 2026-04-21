#!/usr/bin/env python3
"""Generate Python TypedDicts from backend/openapi.json."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "backend" / "openapi.json"
OUTPUT_PATH = ROOT / "custom_components" / "pahlen_monitor" / "generated_api.py"
SCHEMA_ORDER = ["UnitAnalysis", "PushBody", "LatestMeasurement"]


def _load_schemas() -> dict[str, dict]:
    with OPENAPI_PATH.open(encoding="utf-8") as file:
        document = json.load(file)
    return document["components"]["schemas"]


def _ref_name(value: str) -> str:
    return value.rsplit("/", maxsplit=1)[-1]


def _python_type(schema: dict, *, field_name: str | None = None) -> str:
    if "$ref" in schema:
        return _ref_name(schema["$ref"])

    schema_type = schema.get("type")
    nullable = schema.get("nullable", False)

    if schema.get("enum"):
        if field_name == "status":
            python_type = "Status"
        else:
            enum_values = ", ".join(f'"{value}"' for value in schema["enum"])
            python_type = f"Literal[{enum_values}]"
    elif schema_type == "string":
        python_type = "str"
    elif schema_type == "boolean":
        python_type = "bool"
    elif schema_type == "number":
        python_type = "float"
    elif schema_type == "integer":
        python_type = "int"
    elif schema_type == "array":
        python_type = f"list[{_python_type(schema['items'])}]"
    elif schema_type == "object":
        python_type = "dict[str, object]"
    else:
        raise ValueError(f"Unsupported schema type: {schema}")

    if nullable:
        return f"{python_type} | None"
    return python_type


def _generate_status_alias(unit_schema: dict) -> list[str]:
    status_enum = unit_schema["properties"]["status"]["enum"]
    enum_values = ", ".join(f'"{value}"' for value in status_enum)
    set_values = ", ".join(f'"{value}"' for value in status_enum)
    return [
        f"Status = Literal[{enum_values}]",
        f"VALID_STATUSES = {{{set_values}}}",
        "",
    ]


def _generate_typed_dict(name: str, schema: dict) -> list[str]:
    lines = [f"class {name}(TypedDict):"]
    required = set(schema.get("required", []))
    for field_name, field_schema in schema["properties"].items():
        annotation = _python_type(field_schema, field_name=field_name)
        if field_name not in required:
            annotation = f"NotRequired[{annotation}]"
        lines.append(f"    {field_name}: {annotation}")
    lines.append("")
    return lines


def render_contract() -> str:
    schemas = _load_schemas()
    lines = [
        '"""Generated from backend/openapi.json. Do not edit manually."""',
        "",
        "from typing import Literal, NotRequired, TypedDict",
        "",
    ]
    lines.extend(_generate_status_alias(schemas["UnitAnalysis"]))
    for schema_name in SCHEMA_ORDER:
        lines.extend(_generate_typed_dict(schema_name, schemas[schema_name]))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT_PATH.write_text(render_contract(), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
