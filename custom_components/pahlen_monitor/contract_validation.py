from typing import Any, Literal, NotRequired, TypedDict, cast

# Re-defining the API contract manually now that generation scripts are removed.
# This acts as the single source of truth for the Home Assistant plugin.

Status = Literal["ok", "warning", "error", "unknown"]
VALID_STATUSES = {"ok", "warning", "error", "unknown"}


class UnitAnalysis(TypedDict):
    status: Status
    diagnosis: str | None
    pattern_detected: str | None
    blinking_leds: list[str]
    solid_leds: list[str]
    summary: str
    action_required: bool
    recommended_action: str


class PushBody(TypedDict):
    captured_at: str
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: NotRequired[str | None]


class LatestMeasurement(TypedDict):
    installation_id: str
    captured_at: str | None
    pushed_at: str | None
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: str | None


class AnalysisResult(TypedDict):
    """Result produced by the camera analysis step."""

    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: str | None


class PahlenData(LatestMeasurement):
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
    _require_string_list(data.get("blinking_leds"), f"{field_name}.blinking_leds")
    _require_string_list(data.get("solid_leds"), f"{field_name}.solid_leds")
    _require_type(data.get("summary"), str, f"{field_name}.summary")
    _require_type(data.get("action_required"), bool, f"{field_name}.action_required")
    _require_type(
        data.get("recommended_action"), str, f"{field_name}.recommended_action"
    )
    return cast(UnitAnalysis, data)


def validate_analysis_result(data: Any) -> AnalysisResult:
    """Validate the analysis result before it is pushed upstream."""

    _require_type(data, dict, "analysis_result")
    chlorine = validate_unit_analysis(data.get("chlorine"), "chlorine")
    ph = validate_unit_analysis(data.get("ph"), "ph")
    _require_nullable_string(data.get("raw_response"), "raw_response")
    validated: AnalysisResult = {
        "chlorine": chlorine,
        "ph": ph,
        "raw_response": data.get("raw_response"),
    }
    return validated


def validate_push_body(data: Any) -> PushBody:
    """Validate the payload sent from the producer to the hosted backend."""

    _require_type(data, dict, "push_body")
    _require_type(data.get("captured_at"), str, "captured_at")
    _require_nullable_string(data.get("raw_response"), "raw_response")

    validated: PushBody = {
        "captured_at": cast(str, data["captured_at"]),
        "chlorine": validate_unit_analysis(data.get("chlorine"), "chlorine"),
        "ph": validate_unit_analysis(data.get("ph"), "ph"),
        "raw_response": cast(str | None, data.get("raw_response")),
    }
    return validated


def validate_latest_measurement(data: Any) -> LatestMeasurement:
    """Validate the backend response used by the consumer coordinator."""

    _require_type(data, dict, "latest_measurement")
    _require_type(data.get("installation_id"), str, "installation_id")
    _require_nullable_string(data.get("captured_at"), "captured_at")
    _require_nullable_string(data.get("pushed_at"), "pushed_at")
    _require_nullable_string(data.get("raw_response"), "raw_response")

    validated: LatestMeasurement = {
        "installation_id": cast(str, data["installation_id"]),
        "captured_at": cast(str | None, data.get("captured_at")),
        "pushed_at": cast(str | None, data.get("pushed_at")),
        "chlorine": validate_unit_analysis(data.get("chlorine"), "chlorine"),
        "ph": validate_unit_analysis(data.get("ph"), "ph"),
        "raw_response": cast(str | None, data.get("raw_response")),
    }
    return validated
