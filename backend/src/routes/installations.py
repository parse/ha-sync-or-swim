from datetime import timezone
from html import escape

from auth import verify_token, verify_web_ui_token
from db.models import Installation, SharedSensor
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from measurement_service import store_disabled_measurement, store_shared_sensors
from schemas.models import (
    InstallationResponseSchema,
    LatestMeasurementSchema,
    SharedSensorSchema,
    SharedSensorUpdateSchema,
    validate_installation_id,
)
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


def shared_sensor_schema_from_model(sensor: SharedSensor) -> SharedSensorSchema:
    return SharedSensorSchema(
        key=sensor.key,
        label=sensor.label,
        value=sensor.value,
        unit=sensor.unit,
        device_class=sensor.device_class,
        state_class=sensor.state_class,
        updated_at=sensor.updated_at,
    )


def latest_sensors_for_installation(
    db: Session, installation_id: str
) -> list[SharedSensor]:
    return (
        db.query(SharedSensor)
        .filter(SharedSensor.installation_id == installation_id)
        .order_by(SharedSensor.label, SharedSensor.key)
        .all()
    )


def render_sensors_fragment(sensors: list[SharedSensor]) -> str:
    if not sensors:
        return """
<p class="status">No shared sensors found.</p>
<table>
  <thead>
    <tr>
      <th>Sensor</th>
      <th>Value</th>
      <th>Updated</th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="3">No shared sensors found.</td></tr>
  </tbody>
</table>
"""

    rows = []
    for sensor in sensors:
        value = f"{sensor.value} {sensor.unit}" if sensor.unit else sensor.value
        updated_at_value = sensor.updated_at
        if updated_at_value and (
            updated_at_value.tzinfo is None or updated_at_value.utcoffset() is None
        ):
            updated_at_value = updated_at_value.replace(tzinfo=timezone.utc)
        updated_at = updated_at_value.isoformat() if updated_at_value else ""
        updated = (
            f'<time datetime="{escape(updated_at)}">{escape(updated_at)}</time>'
            if updated_at
            else ""
        )
        rows.append(
            "<tr>"
            f'<td data-label="Sensor">{escape(sensor.label or sensor.key)}</td>'
            f'<td data-label="Value" class="value">{escape(value)}</td>'
            f'<td data-label="Updated">{updated}</td>'
            "</tr>"
        )

    return f"""
<p class="status">Last fetched now</p>
<table>
  <thead>
    <tr>
      <th>Sensor</th>
      <th>Value</th>
      <th>Updated</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>
"""


def render_error_fragment(message: str) -> str:
    return f"""
<p class="status error">{escape(message)}</p>
<table>
  <thead>
    <tr>
      <th>Sensor</th>
      <th>Value</th>
      <th>Updated</th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="3">{escape(message)}</td></tr>
  </tbody>
</table>
"""


@router.get("/", response_model=list[InstallationResponseSchema])
async def get_installations(
    db: Session = Depends(get_db), _auth: None = Depends(verify_token)
) -> list[InstallationResponseSchema]:
    all_installations = (
        db.query(Installation).order_by(desc(Installation.last_seen)).all()
    )

    return [
        InstallationResponseSchema(
            id=i.id, last_seen=i.last_seen, created_at=i.created_at
        )
        for i in all_installations
    ]


@router.get(
    "/{installation_id}/sensors/latest", response_model=list[SharedSensorSchema]
)
async def get_latest_sensors(
    installation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_web_ui_token),
) -> list[SharedSensorSchema]:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    installation = db.get(Installation, installation_id)
    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")

    sensors = latest_sensors_for_installation(db, installation_id)
    return [shared_sensor_schema_from_model(s) for s in sensors]


@router.post("/{installation_id}/disabled", response_model=LatestMeasurementSchema)
async def disable_installation(
    installation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_token),
) -> LatestMeasurementSchema:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return store_disabled_measurement(db, installation_id)


@router.post("/{installation_id}/sensors", response_model=list[SharedSensorSchema])
async def update_sensors(
    installation_id: str,
    updates: list[SharedSensorUpdateSchema],
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_token),
) -> list[SharedSensorSchema]:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    sensors = store_shared_sensors(db, installation_id, updates)
    return [shared_sensor_schema_from_model(s) for s in sensors]
