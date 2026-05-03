from datetime import datetime, timezone

from auth import verify_token
from fastapi import APIRouter, Depends, HTTPException
from schemas.models import (
    LatestMeasurementSchema,
    UnitAnalysis,
    validate_installation_id,
)

router = APIRouter()


@router.get("/{installation_id}", response_model=LatestMeasurementSchema)
async def get_debug_measurement(
    installation_id: str, _auth: None = Depends(verify_token)
) -> LatestMeasurementSchema:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    now = datetime.now(timezone.utc)
    return LatestMeasurementSchema(
        installation_id=installation_id,
        captured_at=now,
        pushed_at=now,
        raw_response=None,
        chlorine=UnitAnalysis(
            status="ok",
            diagnosis="Auto mode",
            pattern_detected="LED 4 solid",
            blinking_leds=[],
            solid_leds=["LED 4 - green"],
            summary="Normal operation.",
            action_required=False,
            recommended_action="No action required",
        ),
        ph=UnitAnalysis(
            status="warning",
            diagnosis="Standby mode",
            pattern_detected="LED 5 blinking",
            blinking_leds=["LED 5 - yellow"],
            solid_leds=[],
            summary="pH unit in standby.",
            action_required=False,
            recommended_action="Check if the pump is running",
        ),
    )
