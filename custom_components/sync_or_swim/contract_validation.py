from typing import Any, Literal, TypeAlias, cast

from .generated_api_types import (
    DosingProblemSchema as _DosingProblemSchema,
)
from .generated_api_types import (
    InstallationResponseSchema as _InstallationResponseSchema,
)
from .generated_api_types import (
    LatestMeasurementSchema as _LatestMeasurementSchema,
)
from .generated_api_types import (
    PoolAnalysisSchema as _PoolAnalysisSchema,
)
from .generated_api_types import (
    SharedSensorSchema as _SharedSensorSchema,
)
from .generated_api_types import (
    UnitAnalysis as _UnitAnalysis,
)

Status = Literal["ok", "warning", "error", "unknown"]
DosingProblemState = Literal["OK", "Warning", "Error"]
DosingProblem: TypeAlias = _DosingProblemSchema
InstallationResponse: TypeAlias = _InstallationResponseSchema
LatestMeasurement: TypeAlias = _LatestMeasurementSchema
PoolAnalysis: TypeAlias = _PoolAnalysisSchema
SharedSensor: TypeAlias = _SharedSensorSchema
UnitAnalysis: TypeAlias = _UnitAnalysis
VALID_STATUSES = {"ok", "warning", "error", "unknown"}
VALID_DOSING_PROBLEM_STATES = {"OK", "Warning", "Error"}


class SyncOrSwimData(_LatestMeasurementSchema):
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


def validate_shared_sensor(data: Any, field_name: str) -> SharedSensor:
    """Validate a shared sensor payload."""
    _require_type(data, dict, field_name)
    _require_type(data.get("key"), str, f"{field_name}.key")
    _require_type(data.get("label"), str, f"{field_name}.label")
    _require_type(data.get("value"), str, f"{field_name}.value")
    _require_nullable_string(data.get("unit"), f"{field_name}.unit")
    _require_nullable_string(data.get("device_class"), f"{field_name}.device_class")
    _require_nullable_string(data.get("state_class"), f"{field_name}.state_class")
    _require_nullable_string(data.get("updated_at"), f"{field_name}.updated_at")

    return {
        "key": cast(str, data["key"]),
        "label": cast(str, data["label"]),
        "value": cast(str, data["value"]),
        "unit": cast(str | None, data.get("unit")),
        "device_class": cast(str | None, data.get("device_class")),
        "state_class": cast(str | None, data.get("state_class")),
        "updated_at": cast(str | None, data.get("updated_at")),
    }


def validate_dosing_problem(data: Any, field_name: str) -> DosingProblem:
    """Validate the backend-derived dosing problem payload."""
    _require_type(data, dict, field_name)
    state = data.get("state")
    if state is not None and state not in VALID_DOSING_PROBLEM_STATES:
        raise ValueError(
            f"Expected '{field_name}.state' to be one of {VALID_DOSING_PROBLEM_STATES} or null"
        )
    stale = data.get("stale", False)
    _require_type(stale, bool, f"{field_name}.stale")
    chlorine_status = data.get("chlorine_status")
    ph_status = data.get("ph_status")
    if chlorine_status is not None and chlorine_status not in VALID_STATUSES:
        raise ValueError(
            f"Expected '{field_name}.chlorine_status' to be one of {VALID_STATUSES} or null"
        )
    if ph_status is not None and ph_status not in VALID_STATUSES:
        raise ValueError(
            f"Expected '{field_name}.ph_status' to be one of {VALID_STATUSES} or null"
        )

    return {
        "state": cast(DosingProblemState | None, state),
        "stale": cast(bool, stale),
        "chlorine_status": cast(Status | None, chlorine_status),
        "ph_status": cast(Status | None, ph_status),
    }


def validate_latest_measurement(data: Any) -> LatestMeasurement:
    """Validate the backend response used by the consumer coordinator."""

    _require_type(data, dict, "latest_measurement")
    _require_type(data.get("installation_id"), str, "installation_id")
    _require_nullable_string(data.get("captured_at"), "captured_at")
    _require_nullable_string(data.get("pushed_at"), "pushed_at")
    _require_nullable_string(data.get("raw_response"), "raw_response")

    pool_raw = data.get("pool")
    pool = None
    if pool_raw:
        pool = cast(
            PoolAnalysis,
            {
                "chlorine": validate_unit_analysis(
                    pool_raw.get("chlorine"), "pool.chlorine"
                ),
                "ph": validate_unit_analysis(pool_raw.get("ph"), "pool.ph"),
            },
        )

    sensors_raw = data.get("sensors", [])
    _require_type(sensors_raw, list, "sensors")
    sensors = [
        validate_shared_sensor(s, f"sensors[{i}]") for i, s in enumerate(sensors_raw)
    ]

    dosing_problem_raw = data.get("dosing_problem")
    dosing_problem = (
        validate_dosing_problem(dosing_problem_raw, "dosing_problem")
        if dosing_problem_raw is not None
        else None
    )

    validated: _LatestMeasurementSchema = {
        "installation_id": cast(str, data["installation_id"]),
        "captured_at": cast(str | None, data.get("captured_at")),
        "pushed_at": cast(str | None, data.get("pushed_at")),
        "pool": pool,
        "dosing_problem": dosing_problem,
        "sensors": sensors,
        "raw_response": cast(str | None, data.get("raw_response")),
    }
    return validated
