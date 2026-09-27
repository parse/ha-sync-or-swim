from auth import verify_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from measurement_service import latest_measurement, latest_schema_from_measurement
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

    latest = latest_measurement(db, installation_id)
    if not latest:
        raise HTTPException(
            status_code=404, detail="No measurements found for this installation"
        )

    installation = db.get(Installation, installation_id)
    sensors = installation.shared_sensors if installation else []

    return latest_schema_from_measurement(
        latest,
        sensors,
        staleness_threshold_minutes=staleness_threshold_minutes,
    )
