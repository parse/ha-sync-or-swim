from typing import Any, Literal, TypeAlias, cast

from .generated_api_types import (
    InstallationResponseSchema as _InstallationResponseSchema,
)
from .generated_api_types import (
    LatestMeasurementSchema as _LatestMeasurementSchema,
)
from .generated_api_types import (
    UnitAnalysis as _UnitAnalysis,
)

Status = Literal["ok", "warning", "error", "unknown"]
InstallationResponse: TypeAlias = _InstallationResponseSchema
LatestMeasurement: TypeAlias = _LatestMeasurementSchema
UnitAnalysis: TypeAlias = _UnitAnalysis
VALID_STATUSES = {"ok", "warning", "error", "unknown"}


class PahlenData(_LatestMeasurementSchema):
    """Data structure used internally by the coordinator/entities."""

    stale: bool
    error: str | None


def _require_type(value: Any, expected: type[Any], field_name: str) -> None:
    if not isinstance(value, expected):
        raise ValueError(
            f"Expected '{field_name}' to be {expected.__name__}, got {type(value).__name__}"
        )


def _require_nullable_string(value: Any, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ValueError(
            f"Expected '{field_name}' to be string or null, got {type(value).__name__}"
        )


def _require_string_list(value: Any, field_name: str) -> None:
    _require_type(value, list, field_name)
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"Expected '{field_name}' to contain only strings")


def _optional_string_list(data: dict[str, Any], key: str, field_name: str) -> list[str]:
    if key not in data:
        return []
    value = data[key]
    _require_string_list(value, field_name)
    return cast(list[str], value)


def validate_unit_analysis(data: Any, field_name: str) -> UnitAnalysis:
    """Validate one unit payload against the backend contract."""

    _require_type(data, dict, field_name)
    status = data.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Expected '{field_name}.status' to be one of {VALID_STATUSES}"
        )
    _require_nullable_string(data.get("diagnosis"), f"{field_name}.diagnosis")
    _require_nullable_string(
        data.get("pattern_detected"), f"{field_name}.pattern_detected"
    )
    _require_type(data.get("summary"), str, f"{field_name}.summary")
    _require_type(data.get("action_required"), bool, f"{field_name}.action_required")
    _require_type(
        data.get("recommended_action"), str, f"{field_name}.recommended_action"
    )
    return {
        "status": cast(Status, status),
        "diagnosis": cast(str | None, data.get("diagnosis")),
        "pattern_detected": cast(str | None, data.get("pattern_detected")),
        "blinking_leds": _optional_string_list(
            data, "blinking_leds", f"{field_name}.blinking_leds"
        ),
        "solid_leds": _optional_string_list(
            data, "solid_leds", f"{field_name}.solid_leds"
        ),
        "summary": cast(str, data["summary"]),
        "action_required": cast(bool, data["action_required"]),
        "recommended_action": cast(str, data["recommended_action"]),
    }


def validate_latest_measurement(data: Any) -> LatestMeasurement:
    """Validate the backend response used by the consumer coordinator."""

    _require_type(data, dict, "latest_measurement")
    _require_type(data.get("installation_id"), str, "installation_id")
    _require_nullable_string(data.get("captured_at"), "captured_at")
    _require_nullable_string(data.get("pushed_at"), "pushed_at")
    _require_nullable_string(data.get("raw_response"), "raw_response")

    validated: _LatestMeasurementSchema = {
        "installation_id": cast(str, data["installation_id"]),
        "captured_at": cast(str | None, data.get("captured_at")),
        "pushed_at": cast(str | None, data.get("pushed_at")),
        "chlorine": validate_unit_analysis(data.get("chlorine"), "chlorine"),
        "ph": validate_unit_analysis(data.get("ph"), "ph"),
        "raw_response": cast(str | None, data.get("raw_response")),
    }
    return validated
