from auth import verify_token
from db.models import Installation, Measurement
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from measurement_service import latest_schema_from_measurement
from schemas.models import LatestMeasurementSchema, validate_installation_id
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/{installation_id}", response_model=LatestMeasurementSchema)
async def get_latest_measurement(
    installation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_token),
) -> LatestMeasurementSchema:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    latest = (
        db.query(Measurement)
        .filter(Measurement.installation_id == installation_id)
        .order_by(desc(Measurement.captured_at))
        .first()
    )

    if not latest:
        raise HTTPException(
            status_code=404, detail="No measurements found for this installation"
        )

    installation = db.get(Installation, installation_id)
    sensors = installation.shared_sensors if installation else []

    return latest_schema_from_measurement(latest, sensors)
