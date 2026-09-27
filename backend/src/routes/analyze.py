import logging

from auth import verify_token
from cv_engine import analyze_burst
from db.session import get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from measurement_service import store_cv_result
from schemas.models import LatestMeasurementSchema, validate_installation_id
from sqlalchemy.orm import Session

router = APIRouter()
_LOGGER = logging.getLogger(__name__)


@router.post("/{installation_id}/burst", response_model=LatestMeasurementSchema)
def analyze_and_store_image_burst(
    installation_id: str,
    files: list[UploadFile] = File(...),
    _auth: None = Depends(verify_token),
    db: Session = Depends(get_db),
) -> LatestMeasurementSchema:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        images_bytes = [file.file.read() for file in files]
        result = analyze_burst(images_bytes)
        return store_cv_result(db, installation_id, result)
    except ValueError as e:
        _LOGGER.warning("Invalid burst upload for %s: %s", installation_id, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        _LOGGER.exception("Error analyzing burst for %s", installation_id)
        raise HTTPException(status_code=500, detail="Analysis failed") from e
