from auth import verify_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from measurement_service import store_disabled_measurement
from schemas.models import (
    InstallationResponseSchema,
    LatestMeasurementSchema,
    validate_installation_id,
)
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


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
