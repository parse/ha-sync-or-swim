from time import perf_counter

from auth import verify_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from measurement_service import (
    as_utc,
    latest_measurement,
    latest_schema_from_measurement,
)
from request_timing import elapsed_ms, log_timing
from routes.dependencies import valid_installation_id
from schemas.models import LatestMeasurementSchema
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/{installation_id}", response_model=LatestMeasurementSchema)
def get_latest_measurement(
    staleness_threshold_minutes: int | None = None,
    _auth: None = Depends(verify_token),
    installation_id: str = Depends(valid_installation_id),
    db: Session = Depends(get_db),
) -> LatestMeasurementSchema:
    if staleness_threshold_minutes is not None and staleness_threshold_minutes < 0:
        raise HTTPException(
            status_code=400, detail="staleness_threshold_minutes must be non-negative"
        )

    started = perf_counter()
    latest = latest_measurement(db, installation_id)
    if not latest:
        log_timing(
            "latest_read",
            installation_id=installation_id,
            duration_ms=elapsed_ms(started),
            found=False,
        )
        raise HTTPException(
            status_code=404, detail="No measurements found for this installation"
        )

    installation = db.get(Installation, installation_id)
    sensors = installation.shared_sensors if installation else []

    response = latest_schema_from_measurement(
        latest,
        sensors,
        staleness_threshold_minutes=staleness_threshold_minutes,
    )
    problem = response.dosing_problem
    log_timing(
        "latest_read",
        installation_id=installation_id,
        duration_ms=elapsed_ms(started),
        found=True,
        captured_at=as_utc(latest.captured_at).isoformat(),
        stale=problem.stale if problem else None,
        dosing_problem=problem.state if problem else None,
        sensor_count=len(response.sensors),
    )
    return response
