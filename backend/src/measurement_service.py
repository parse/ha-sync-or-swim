from datetime import datetime, timezone
from typing import cast

from db.models import Installation, Measurement, SharedSensor
from schemas.models import (
    CVAnalysisResult,
    CVUnitAnalysisPayload,
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
        recommended_action=(
            "Check dosing unit" if status in {"warning", "error"} else ""
        ),
    )


def latest_schema_from_measurement(
    measurement: Measurement, sensors: list[SharedSensor] | None = None
) -> LatestMeasurementSchema:
    sensor_schemas = []
    if sensors:
        for s in sensors:
            sensor_schemas.append(
                SharedSensorSchema(
                    key=s.key,
                    label=s.label,
                    value=s.value,
                    unit=s.unit,
                    device_class=s.device_class,
                    state_class=s.state_class,
                    updated_at=s.updated_at,
                )
            )

    return LatestMeasurementSchema(
        installation_id=measurement.installation_id,
        captured_at=measurement.captured_at,
        pushed_at=measurement.pushed_at,
        pool=PoolAnalysisSchema(
            chlorine=UnitAnalysis(
                status=status_from_db(measurement.chlorine_status),
                diagnosis=measurement.chlorine_diagnosis,
                pattern_detected=measurement.chlorine_pattern,
                blinking_leds=measurement.chlorine_blinking or [],
                solid_leds=measurement.chlorine_solid or [],
                summary=measurement.chlorine_summary or "",
                action_required=measurement.chlorine_action,
                recommended_action=measurement.chlorine_recommended or "",
            ),
            ph=UnitAnalysis(
                status=status_from_db(measurement.ph_status),
                diagnosis=measurement.ph_diagnosis,
                pattern_detected=measurement.ph_pattern,
                blinking_leds=measurement.ph_blinking or [],
                solid_leds=measurement.ph_solid or [],
                summary=measurement.ph_summary or "",
                action_required=measurement.ph_action,
                recommended_action=measurement.ph_recommended or "",
            ),
        ),
        sensors=sensor_schemas,
        raw_response=measurement.raw_response,
    )


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
