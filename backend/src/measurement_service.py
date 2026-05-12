from datetime import datetime, timezone
from typing import cast

from db.models import Installation, Measurement, SharedSensor
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
from sqlalchemy.orm import Session


def led_labels(leds: list[int]) -> list[str]:
    return [f"LED {led}" for led in leds]


def status_from_db(value: str) -> StatusLiteral:
    if value in {"ok", "warning", "error", "unknown"}:
        return cast(StatusLiteral, value)
    return "unknown"


def compute_stale(captured_at: datetime | None, threshold_minutes: int) -> bool:
    if captured_at is None:
        return False
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return (
        datetime.now(tz=timezone.utc) - captured_at
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
    if any(status in (None, "unknown") for status in statuses):
        return None
    return None


def dosing_problem_reason_from_statuses(
    chlorine_status: StatusLiteral | None,
    ph_status: StatusLiteral | None,
    stale: bool,
) -> DosingProblemReasonLiteral:
    chlorine_problem = chlorine_status in {"warning", "error"}
    ph_problem = ph_status in {"warning", "error"}

    if chlorine_problem and ph_problem:
        return "multiple_units"
    if chlorine_status == "error":
        return "chlorine_error"
    if ph_status == "error":
        return "ph_error"
    if chlorine_status == "warning":
        return "chlorine_warning"
    if ph_status == "warning":
        return "ph_warning"
    if stale:
        return "stale_data"
    if (chlorine_status, ph_status) == ("ok", "ok"):
        return "none"
    return "unknown"


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
        return "Value is below target. Check the dosing unit and current pool value."
    if diagnosis == "Above target":
        return "Value is above target. Check the dosing unit and current pool value."
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
        action_required=status in {"warning", "error"},
        recommended_action=recommended_action_from_cv(data),
    )


def latest_schema_from_measurement(
    measurement: Measurement,
    sensors: list[SharedSensor] | None = None,
    *,
    staleness_threshold_minutes: int | None = None,
) -> LatestMeasurementSchema:
    sensor_schemas = []
    if sensors:
        sorted_sensors = sorted(
            sensors,
            key=lambda sensor: (shared_sensor_display_label(sensor), sensor.key),
        )
        for s in sorted_sensors:
            sensor_schemas.append(
                SharedSensorSchema(
                    key=s.key,
                    label=shared_sensor_display_label(s),
                    preferred_alias=s.preferred_alias,
                    value=s.value,
                    unit=s.unit,
                    device_class=s.device_class,
                    state_class=s.state_class,
                    updated_at=s.updated_at,
                )
            )

    stale = (
        compute_stale(measurement.captured_at, staleness_threshold_minutes)
        if staleness_threshold_minutes is not None
        else False
    )
    chlorine_status = status_from_db(measurement.chlorine_status)
    ph_status = status_from_db(measurement.ph_status)

    return LatestMeasurementSchema(
        installation_id=measurement.installation_id,
        captured_at=measurement.captured_at,
        pushed_at=measurement.pushed_at,
        pool=PoolAnalysisSchema(
            chlorine=UnitAnalysis(
                status=chlorine_status,
                diagnosis=measurement.chlorine_diagnosis,
                pattern_detected=measurement.chlorine_pattern,
                blinking_leds=measurement.chlorine_blinking or [],
                solid_leds=measurement.chlorine_solid or [],
                summary=measurement.chlorine_summary or "",
                action_required=measurement.chlorine_action,
                recommended_action=measurement.chlorine_recommended or "",
            ),
            ph=UnitAnalysis(
                status=ph_status,
                diagnosis=measurement.ph_diagnosis,
                pattern_detected=measurement.ph_pattern,
                blinking_leds=measurement.ph_blinking or [],
                solid_leds=measurement.ph_solid or [],
                summary=measurement.ph_summary or "",
                action_required=measurement.ph_action,
                recommended_action=measurement.ph_recommended or "",
            ),
        ),
        dosing_problem=DosingProblemSchema(
            state=dosing_problem_from_statuses(chlorine_status, ph_status, stale),
            reason=dosing_problem_reason_from_statuses(
                chlorine_status, ph_status, stale
            ),
            stale=stale,
            chlorine_status=chlorine_status,
            ph_status=ph_status,
        ),
        sensors=sensor_schemas,
        raw_response=measurement.raw_response,
    )


def shared_sensor_display_label(sensor: SharedSensor) -> str:
    preferred_alias = sensor.preferred_alias.strip() if sensor.preferred_alias else ""
    label = sensor.label.strip() if sensor.label else ""
    return preferred_alias or label or sensor.key


def store_cv_result(
    db: Session,
    installation_id: str,
    cv_result: CVAnalysisResult,
    captured_at: datetime | None = None,
) -> LatestMeasurementSchema:
    captured_at = captured_at or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    installation = db.get(Installation, installation_id)
    if installation is None:
        installation = Installation(id=installation_id, last_seen=now)
        db.add(installation)
    else:
        installation.last_seen = now

    chlorine = unit_from_cv(cv_result["chlorine"])
    ph = unit_from_cv(cv_result["ph"])

    measurement = Measurement(
        installation_id=installation_id,
        captured_at=captured_at,
        chlorine_status=chlorine.status,
        chlorine_diagnosis=chlorine.diagnosis,
        chlorine_pattern=chlorine.pattern_detected,
        chlorine_blinking=chlorine.blinking_leds,
        chlorine_solid=chlorine.solid_leds,
        chlorine_summary=chlorine.summary,
        chlorine_action=chlorine.action_required,
        chlorine_recommended=chlorine.recommended_action,
        ph_status=ph.status,
        ph_diagnosis=ph.diagnosis,
        ph_pattern=ph.pattern_detected,
        ph_blinking=ph.blinking_leds,
        ph_solid=ph.solid_leds,
        ph_summary=ph.summary,
        ph_action=ph.action_required,
        ph_recommended=ph.recommended_action,
        raw_response=None,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    return latest_schema_from_measurement(measurement, installation.shared_sensors)


def store_shared_sensors(
    db: Session,
    installation_id: str,
    updates: list[SharedSensorUpdateSchema],
) -> list[SharedSensor]:
    now = datetime.now(timezone.utc)

    installation = db.get(Installation, installation_id)
    if installation is None:
        installation = Installation(id=installation_id, last_seen=now)
        db.add(installation)
    else:
        installation.last_seen = now

    for update in updates:
        existing = (
            db.query(SharedSensor)
            .filter(
                SharedSensor.installation_id == installation_id,
                SharedSensor.key == update.key,
            )
            .first()
        )

        if existing:
            existing.label = update.label
            existing.value = update.value
            existing.unit = update.unit
            existing.device_class = update.device_class
            existing.state_class = update.state_class
            existing.updated_at = now
        else:
            new_sensor = SharedSensor(
                installation_id=installation_id,
                key=update.key,
                label=update.label,
                value=update.value,
                unit=update.unit,
                device_class=update.device_class,
                state_class=update.state_class,
                updated_at=now,
            )
            db.add(new_sensor)

    db.commit()
    db.refresh(installation)
    return installation.shared_sensors


def store_disabled_measurement(
    db: Session,
    installation_id: str,
    captured_at: datetime | None = None,
) -> LatestMeasurementSchema:
    captured_at = captured_at or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    installation = db.get(Installation, installation_id)
    if installation is None:
        installation = Installation(id=installation_id, last_seen=now)
        db.add(installation)
    else:
        installation.last_seen = now

    measurement = Measurement(
        installation_id=installation_id,
        captured_at=captured_at,
        chlorine_status="ok",
        chlorine_diagnosis=None,
        chlorine_pattern="disabled",
        chlorine_blinking=[],
        chlorine_solid=[],
        chlorine_summary="Installation disabled",
        chlorine_action=False,
        chlorine_recommended="No action needed",
        ph_status="ok",
        ph_diagnosis=None,
        ph_pattern="disabled",
        ph_blinking=[],
        ph_solid=[],
        ph_summary="Installation disabled",
        ph_action=False,
        ph_recommended="No action needed",
        raw_response=None,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    return latest_schema_from_measurement(measurement, installation.shared_sensors)
