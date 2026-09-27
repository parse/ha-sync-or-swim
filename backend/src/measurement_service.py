from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, cast

from db.models import Installation, Measurement, SharedSensor
from request_timing import elapsed_ms, log_timing
from schemas.models import (
    CVAnalysisResult,
    CVUnitAnalysisPayload,
    DosingProblemLiteral,
    DosingProblemReasonLiteral,
    DosingProblemSchema,
    LatestMeasurementSchema,
    PoolAnalysisSchema,
    SharedSensorSchema,
    SharedSensorUpdateSchema,
    StatusLiteral,
    UnitAnalysis,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

UnitName = Literal["chlorine", "ph"]

# UnitAnalysis field -> Measurement column suffix; columns are "<unit>_<suffix>".
UNIT_COLUMN_SUFFIXES = {
    "status": "status",
    "diagnosis": "diagnosis",
    "pattern_detected": "pattern",
    "blinking_leds": "blinking",
    "solid_leds": "solid",
    "summary": "summary",
    "action_required": "action",
    "recommended_action": "recommended",
}

DISABLED_UNIT = UnitAnalysis(
    status="ok",
    diagnosis=None,
    pattern_detected="disabled",
    blinking_leds=[],
    solid_leds=[],
    summary="Installation disabled",
    action_required=False,
    recommended_action="No action needed",
)

# Home Assistant friendly names that say what is measured but not where.
GENERIC_SHARED_SENSOR_LABELS = {
    "battery",
    "current",
    "energy",
    "humidity",
    "illuminance",
    "power",
    "temperature",
    "voltage",
}


def led_labels(leds: list[int]) -> list[str]:
    return [f"LED {led}" for led in leds]


def status_from_db(value: str) -> StatusLiteral:
    if value in {"ok", "warning", "error", "unknown"}:
        return cast(StatusLiteral, value)
    return "unknown"


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes from the database as UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def compute_stale(captured_at: datetime | None, threshold_minutes: int) -> bool:
    if captured_at is None:
        return False
    return (
        datetime.now(tz=timezone.utc) - as_utc(captured_at)
    ).total_seconds() > threshold_minutes * 60


def dosing_problem_from_statuses(
    chlorine_status: StatusLiteral | None,
    ph_status: StatusLiteral | None,
    stale: bool,
) -> DosingProblemLiteral | None:
    statuses = (chlorine_status, ph_status)
    if "error" in statuses:
        return "Error"
    if "warning" in statuses or stale:
        return "Warning"
    if statuses == ("ok", "ok"):
        return "OK"
    return None


def dosing_problem_reason_from_statuses(
    chlorine_status: StatusLiteral | None,
    ph_status: StatusLiteral | None,
    stale: bool,
) -> DosingProblemReasonLiteral:
    chlorine_problem = chlorine_status in {"warning", "error"}
    ph_problem = ph_status in {"warning", "error"}
    has_error = chlorine_status == "error" or ph_status == "error"

    if chlorine_problem and ph_problem and has_error:
        return "multiple_units"
    if chlorine_status == "error":
        return "chlorine_error"
    if ph_status == "error":
        return "ph_error"
    if stale:
        return "stale_data"
    if chlorine_problem and ph_problem:
        return "multiple_units"
    if chlorine_status == "warning":
        return "chlorine_warning"
    if ph_status == "warning":
        return "ph_warning"
    if (chlorine_status, ph_status) == ("ok", "ok"):
        return "none"
    return "unknown"


def dosing_problem_message(reason: DosingProblemReasonLiteral) -> str:
    messages: dict[DosingProblemReasonLiteral, str] = {
        "stale_data": "Latest reading is stale",
        "chlorine_error": "Chlorine dosing unit reports an error",
        "ph_error": "pH dosing unit reports an error",
        "chlorine_warning": "Chlorine status is warning",
        "ph_warning": "pH status is warning",
        "multiple_units": "Multiple dosing units report warnings or errors",
        "unknown": "Dosing problem state is unknown",
        "none": "No dosing problem detected",
    }
    return messages[reason]


def action_required_from_cv(data: CVUnitAnalysisPayload) -> bool:
    if data["status"] == "error":
        return True
    if data["status"] != "warning":
        return False
    return data["diagnosis"] not in {"Below target", "Above target"}


def recommended_action_from_cv(data: CVUnitAnalysisPayload) -> str:
    status = data["status"]
    if status not in {"warning", "error"}:
        return ""

    mode = data["mode"]
    diagnosis = data["diagnosis"]
    if mode == "error" or status == "error":
        return "Dosing stopped after timeout. Check the dosing unit and circulation."
    if mode == "standby":
        return "Unit is in standby. Check that circulation is running."
    if diagnosis == "Below target":
        if mode == "dosing":
            return "Value is below target. Unit should be dosing."
        if mode == "waiting":
            return "Value is below target. Unit is waiting for the value to rise."
    if diagnosis == "Above target":
        if mode == "dosing":
            return "Value is above target. Unit should be dosing."
        if mode == "waiting":
            return "Value is above target. Unit is waiting for the value to drop."
    return "Check dosing unit LED pattern."


def unit_from_cv(data: CVUnitAnalysisPayload) -> UnitAnalysis:
    status = data["status"]
    diagnosis = data["diagnosis"]
    mode = data["mode"]
    level = data["level"]
    blinking = data["blinking"]
    led_states = data["led_states"]
    solid_leds = [idx + 1 for idx, is_on in enumerate(led_states) if is_on]

    if diagnosis:
        summary = diagnosis
    elif level is not None:
        summary = f"Level {level}"
    else:
        summary = "Unknown status"

    return UnitAnalysis(
        status=status,
        diagnosis=diagnosis,
        pattern_detected=mode,
        blinking_leds=led_labels(blinking),
        solid_leds=led_labels(solid_leds),
        summary=summary,
        action_required=action_required_from_cv(data),
        recommended_action=recommended_action_from_cv(data),
    )


def latest_schema_from_measurement(
    measurement: Measurement,
    sensors: list[SharedSensor] | None = None,
    *,
    staleness_threshold_minutes: int | None = None,
) -> LatestMeasurementSchema:
    sensor_schemas = [
        shared_sensor_schema(sensor) for sensor in sort_shared_sensors(sensors or [])
    ]
    stale = (
        compute_stale(measurement.captured_at, staleness_threshold_minutes)
        if staleness_threshold_minutes is not None
        else False
    )
    chlorine = _unit_from_columns(measurement, "chlorine")
    ph = _unit_from_columns(measurement, "ph")
    chlorine_status = chlorine.status
    ph_status = ph.status
    dosing_problem_reason = dosing_problem_reason_from_statuses(
        chlorine_status, ph_status, stale
    )

    return LatestMeasurementSchema(
        installation_id=measurement.installation_id,
        captured_at=measurement.captured_at,
        pushed_at=measurement.pushed_at,
        pool=PoolAnalysisSchema(chlorine=chlorine, ph=ph),
        dosing_problem=DosingProblemSchema(
            state=dosing_problem_from_statuses(chlorine_status, ph_status, stale),
            reason=dosing_problem_reason,
            message=dosing_problem_message(dosing_problem_reason),
            stale=stale,
            chlorine_status=chlorine_status,
            ph_status=ph_status,
        ),
        sensors=sensor_schemas,
        raw_response=measurement.raw_response,
    )


def _unit_columns(unit_name: UnitName, unit: UnitAnalysis) -> dict[str, Any]:
    values = unit.model_dump()
    return {
        f"{unit_name}_{suffix}": values[field]
        for field, suffix in UNIT_COLUMN_SUFFIXES.items()
    }


def _unit_from_columns(measurement: Measurement, unit_name: UnitName) -> UnitAnalysis:
    values = {
        field: getattr(measurement, f"{unit_name}_{suffix}")
        for field, suffix in UNIT_COLUMN_SUFFIXES.items()
    }
    values["status"] = status_from_db(values["status"])
    for field in ("blinking_leds", "solid_leds"):
        values[field] = values[field] or []
    for field in ("summary", "recommended_action"):
        values[field] = values[field] or ""
    return UnitAnalysis.model_validate(values)


def latest_measurement(db: Session, installation_id: str) -> Measurement | None:
    return (
        db.query(Measurement)
        .filter(Measurement.installation_id == installation_id)
        .order_by(Measurement.captured_at.desc())
        .first()
    )


def latest_sensors_for_installation(
    db: Session, installation_id: str
) -> list[SharedSensor]:
    sensors = (
        db.query(SharedSensor)
        .filter(SharedSensor.installation_id == installation_id)
        .all()
    )
    return sort_shared_sensors(sensors)


def sort_shared_sensors(sensors: list[SharedSensor]) -> list[SharedSensor]:
    return sorted(
        sensors, key=lambda sensor: (shared_sensor_display_label(sensor), sensor.key)
    )


def shared_sensor_schema(sensor: SharedSensor) -> SharedSensorSchema:
    return SharedSensorSchema(
        key=sensor.key,
        label=shared_sensor_display_label(sensor),
        preferred_alias=sensor.preferred_alias,
        value=sensor.value,
        unit=sensor.unit,
        device_class=sensor.device_class,
        state_class=sensor.state_class,
        updated_at=sensor.updated_at,
    )


def shared_sensor_display_label(sensor: SharedSensor) -> str:
    preferred_alias = sensor.preferred_alias.strip() if sensor.preferred_alias else ""
    if preferred_alias:
        return preferred_alias

    label = sensor.label.strip() if sensor.label else ""
    if not label:
        return sensor.key
    if label.lower() not in GENERIC_SHARED_SENSOR_LABELS:
        return label

    object_id = sensor.key.split(".", 1)[-1]
    parts = [p for p in object_id.split("_") if p and p not in {"sensor", "temp"}]
    return " ".join(p.capitalize() for p in parts) if parts else label


def store_cv_result(
    db: Session,
    installation_id: str,
    cv_result: CVAnalysisResult,
    captured_at: datetime | None = None,
) -> LatestMeasurementSchema:
    return _store_measurement(
        db,
        installation_id,
        unit_from_cv(cv_result["chlorine"]),
        unit_from_cv(cv_result["ph"]),
        captured_at,
    )


def store_disabled_measurement(
    db: Session,
    installation_id: str,
    captured_at: datetime | None = None,
) -> LatestMeasurementSchema:
    return _store_measurement(
        db, installation_id, DISABLED_UNIT, DISABLED_UNIT, captured_at
    )


def _store_measurement(
    db: Session,
    installation_id: str,
    chlorine: UnitAnalysis,
    ph: UnitAnalysis,
    captured_at: datetime | None,
) -> LatestMeasurementSchema:
    now = datetime.now(timezone.utc)
    installation = _touch_installation(db, installation_id, now)
    measurement = Measurement(
        installation_id=installation_id,
        captured_at=captured_at or now,
        **_unit_columns("chlorine", chlorine),
        **_unit_columns("ph", ph),
        raw_response=None,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    return latest_schema_from_measurement(measurement, installation.shared_sensors)


def _touch_installation(
    db: Session, installation_id: str, now: datetime
) -> Installation:
    installation = db.get(Installation, installation_id)
    if installation is None:
        installation = Installation(id=installation_id, last_seen=now)
        db.add(installation)
    else:
        installation.last_seen = now
    return installation


def store_shared_sensors(
    db: Session,
    installation_id: str,
    updates: list[SharedSensorUpdateSchema],
) -> list[SharedSensor]:
    now = datetime.now(timezone.utc)

    query_started = perf_counter()
    _upsert_shared_sensors(db, installation_id, updates, now)
    log_timing(
        "sensor_database_queries",
        installation_id=installation_id,
        duration_ms=elapsed_ms(query_started),
        update_count=len(updates),
        write_strategy="atomic_upsert",
    )
    commit_started = perf_counter()
    db.commit()
    log_timing(
        "sensor_database_commit",
        installation_id=installation_id,
        duration_ms=elapsed_ms(commit_started),
    )
    refresh_started = perf_counter()
    installation = db.get(Installation, installation_id)
    if installation is None:
        raise RuntimeError("Installation missing after shared sensor upsert")
    sensors = installation.shared_sensors
    log_timing(
        "sensor_database_refresh",
        installation_id=installation_id,
        duration_ms=elapsed_ms(refresh_started),
    )
    return sensors


def _upsert_shared_sensors(
    db: Session,
    installation_id: str,
    updates: list[SharedSensorUpdateSchema],
    now: datetime,
) -> None:
    """Atomically store sensors so concurrent retries cannot race on inserts."""
    insert = (
        postgresql_insert
        if db.get_bind().dialect.name == "postgresql"
        else sqlite_insert
    )
    installation_insert = insert(Installation).values(id=installation_id, last_seen=now)
    db.execute(
        installation_insert.on_conflict_do_update(
            index_elements=[Installation.id], set_={"last_seen": now}
        )
    )

    for update in updates:
        sensor_insert = insert(SharedSensor).values(
            installation_id=installation_id,
            key=update.key,
            label=update.label,
            value=update.value,
            unit=update.unit,
            device_class=update.device_class,
            state_class=update.state_class,
            updated_at=now,
        )
        db.execute(
            sensor_insert.on_conflict_do_update(
                index_elements=[SharedSensor.installation_id, SharedSensor.key],
                set_={
                    "label": update.label,
                    "value": update.value,
                    "unit": update.unit,
                    "device_class": update.device_class,
                    "state_class": update.state_class,
                    "updated_at": now,
                },
            )
        )
