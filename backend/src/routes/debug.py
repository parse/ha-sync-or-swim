from datetime import datetime
from typing import Any

from auth import verify_token
from fastapi import APIRouter, Depends, HTTPException
from schemas.models import (
    validate_installation_id,
)

router = APIRouter()


@router.get("/{installation_id}")
async def get_debug_measurement(
    installation_id: str, _auth: None = Depends(verify_token)
) -> dict[str, Any]:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "installation_id": installation_id,
        "captured_at": datetime.now(),
        "pushed_at": datetime.now(),
        "raw_response": None,
        "chlorine": {
            "status": "ok",
            "diagnosis": "Auto mode",
            "pattern_detected": "LED 4 solid",
            "blinking_leds": [],
            "solid_leds": ["LED 4 – green"],
            "summary": "Normal operation.",
            "action_required": False,
            "recommended_action": "No action required",
        },
        "ph": {
            "status": "warning",
            "diagnosis": "Standby mode",
            "pattern_detected": "LED 5 blinking",
            "blinking_leds": ["LED 5 – yellow"],
            "solid_leds": [],
            "summary": "pH unit in standby.",
            "action_required": False,
            "recommended_action": "Check if the pump is running",
        },
        "debug": True,
    }
