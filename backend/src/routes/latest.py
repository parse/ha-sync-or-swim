from auth import verify_token
from db.models import Measurement
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from schemas.models import (
    LatestMeasurementSchema,
    UnitAnalysis,
    validate_installation_id,
)
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/{installation_id}", response_model=LatestMeasurementSchema)
async def get_latest_measurement(
    installation_id: str, db: Session = Depends(get_db), _=Depends(verify_token)
):
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

    return LatestMeasurementSchema(
        installation_id=latest.installation_id,
        captured_at=latest.captured_at,
        pushed_at=latest.pushed_at,
        chlorine=UnitAnalysis(
            status=latest.chlorine_status,
            diagnosis=latest.chlorine_diagnosis,
            pattern_detected=latest.chlorine_pattern,
            blinking_leds=latest.chlorine_blinking or [],
            solid_leds=latest.chlorine_solid or [],
            summary=latest.chlorine_summary or "",
            action_required=latest.chlorine_action,
            recommended_action=latest.chlorine_recommended or "",
        ),
        ph=UnitAnalysis(
            status=latest.ph_status,
            diagnosis=latest.ph_diagnosis,
            pattern_detected=latest.ph_pattern,
            blinking_leds=latest.ph_blinking or [],
            solid_leds=latest.ph_solid or [],
            summary=latest.ph_summary or "",
            action_required=latest.ph_action,
            recommended_action=latest.ph_recommended or "",
        ),
        raw_response=latest.raw_response,
    )
