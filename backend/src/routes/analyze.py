from auth import verify_token
from cv_engine import analyze_burst
from db.session import get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from measurement_service import store_cv_result
from schemas.models import LatestMeasurementSchema, validate_installation_id
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/{installation_id}/burst", response_model=LatestMeasurementSchema)
async def analyze_and_store_image_burst(
    installation_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_token),
) -> LatestMeasurementSchema:
    try:
        validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        images_bytes: list[bytes] = []
        for file in files:
            content = await file.read()
            images_bytes.append(content)

        result = analyze_burst(images_bytes)
        return store_cv_result(db, installation_id, result)
    except Exception as e:
        print(f"Error in analyze_burst: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
