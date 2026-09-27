from datetime import datetime, timezone

from auth import verify_token
from fastapi import APIRouter, Depends
from routes.dependencies import valid_installation_id
from schemas.models import (
    DosingProblemSchema,
    LatestMeasurementSchema,
    PoolAnalysisSchema,
    UnitAnalysis,
)

router = APIRouter()


@router.get("/{installation_id}", response_model=LatestMeasurementSchema)
async def get_debug_measurement(
    _auth: None = Depends(verify_token),
    installation_id: str = Depends(valid_installation_id),
) -> LatestMeasurementSchema:
    now = datetime.now(timezone.utc)
    return LatestMeasurementSchema(
        installation_id=installation_id,
        captured_at=now,
        pushed_at=now,
        raw_response=None,
        pool=PoolAnalysisSchema(
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
        ),
        dosing_problem=DosingProblemSchema(
            state="Warning",
            reason="ph_warning",
            message="pH status is warning",
            stale=False,
            chlorine_status="ok",
            ph_status="warning",
        ),
    )
