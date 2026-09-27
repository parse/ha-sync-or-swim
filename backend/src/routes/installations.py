from time import perf_counter

from auth import verify_token, verify_web_ui_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends, Header, HTTPException
from idempotency import sensor_request_lock
from measurement_service import (
    latest_sensors_for_installation,
    shared_sensor_schema,
    store_disabled_measurement,
    store_shared_sensors,
)
from request_timing import elapsed_ms, log_timing
from routes.dependencies import valid_installation_id
from schemas.models import (
    InstallationResponseSchema,
    LatestMeasurementSchema,
    SharedSensorSchema,
    SharedSensorUpdateSchema,
)
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/", response_model=list[InstallationResponseSchema])
def get_installations(
    _auth: None = Depends(verify_token), db: Session = Depends(get_db)
) -> list[InstallationResponseSchema]:
    all_installations = (
        db.query(Installation).order_by(Installation.last_seen.desc()).all()
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
def get_latest_sensors(
    _auth: None = Depends(verify_web_ui_token),
    installation_id: str = Depends(valid_installation_id),
    db: Session = Depends(get_db),
) -> list[SharedSensorSchema]:
    installation = db.get(Installation, installation_id)
    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")

    sensors = latest_sensors_for_installation(db, installation_id)
    return [shared_sensor_schema(s) for s in sensors]


@router.post("/{installation_id}/disabled", response_model=LatestMeasurementSchema)
def disable_installation(
    _auth: None = Depends(verify_token),
    installation_id: str = Depends(valid_installation_id),
    db: Session = Depends(get_db),
) -> LatestMeasurementSchema:
    return store_disabled_measurement(db, installation_id)


@router.post("/{installation_id}/sensors", response_model=list[SharedSensorSchema])
def update_sensors(
    updates: list[SharedSensorUpdateSchema],
    _auth: None = Depends(verify_token),
    installation_id: str = Depends(valid_installation_id),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> list[SharedSensorSchema]:
    log_timing(
        "sensor_request_validation",
        installation_id=installation_id,
        sensor_entity_ids=",".join(update.key for update in updates),
    )

    write_started = perf_counter()
    lock_key = idempotency_key or ",".join(sorted(update.key for update in updates))
    with sensor_request_lock(installation_id, lock_key):
        sensors = store_shared_sensors(db, installation_id, updates)
    log_timing(
        "sensor_database_write",
        installation_id=installation_id,
        sensor_entity_ids=",".join(update.key for update in updates),
        duration_ms=elapsed_ms(write_started),
        external_call_ms=0,
    )
    response_started = perf_counter()
    response = [shared_sensor_schema(s) for s in sensors]
    log_timing(
        "sensor_response_serialization",
        installation_id=installation_id,
        duration_ms=elapsed_ms(response_started),
    )
    return response
