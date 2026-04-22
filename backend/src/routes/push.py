from datetime import datetime

from auth import verify_token
from db.models import Installation, Measurement
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from schemas.models import PushBodySchema, validate_installation_id
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/{installation_id}", status_code=201)
async def push_measurement(
    installation_id: str,
    push_data: PushBodySchema,
    db: Session = Depends(get_db),
    _=Depends(verify_token),
):
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        # Upsert installation
        stmt = (
            insert(Installation)
            .values(id=installation_id, last_seen=datetime.now())
            .on_conflict_do_update(
                index_elements=[Installation.id], set_={"last_seen": datetime.now()}
            )
        )
        db.execute(stmt)

        # Insert measurement
        new_measurement = Measurement(
            installation_id=installation_id,
            captured_at=push_data.captured_at,
            chlorine_status=push_data.chlorine.status,
            chlorine_diagnosis=push_data.chlorine.diagnosis,
            chlorine_pattern=push_data.chlorine.pattern_detected,
            chlorine_blinking=push_data.chlorine.blinking_leds,
            chlorine_solid=push_data.chlorine.solid_leds,
            chlorine_summary=push_data.chlorine.summary,
            chlorine_action=push_data.chlorine.action_required,
            chlorine_recommended=push_data.chlorine.recommended_action,
            ph_status=push_data.ph.status,
            ph_diagnosis=push_data.ph.diagnosis,
            ph_pattern=push_data.ph.pattern_detected,
            ph_blinking=push_data.ph.blinking_leds,
            ph_solid=push_data.ph.solid_leds,
            ph_summary=push_data.ph.summary,
            ph_action=push_data.ph.action_required,
            ph_recommended=push_data.ph.recommended_action,
            raw_response=push_data.raw_response,
        )
        db.add(new_measurement)
        db.commit()
        db.refresh(new_measurement)

        return {"id": new_measurement.id}
    except Exception as e:
        db.rollback()
        print(f"Error in push_measurement: {e}")
        raise HTTPException(status_code=500, detail="Database error") from e
