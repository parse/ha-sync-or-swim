import logging
from time import perf_counter
from typing import Any

from auth import verify_token
from cv_engine import analyze_frames, preprocess_image
from db.session import get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from measurement_service import store_cv_result
from request_timing import elapsed_ms, log_timing
from routes.dependencies import valid_installation_id
from schemas.models import CVAnalysisResult, LatestMeasurementSchema
from sqlalchemy.orm import Session

router = APIRouter()
_LOGGER = logging.getLogger(__name__)


def analysis_summary(result: CVAnalysisResult) -> dict[str, Any]:
    """Return the per-unit outcome worth logging; never image data."""
    return {
        f"{unit}_{field}": result[unit][field]
        for unit in ("chlorine", "ph")
        for field in ("mode", "status", "level")
    }


@router.post("/{installation_id}/burst", response_model=LatestMeasurementSchema)
def analyze_and_store_image_burst(
    files: list[UploadFile] = File(...),
    _auth: None = Depends(verify_token),
    installation_id: str = Depends(valid_installation_id),
    db: Session = Depends(get_db),
) -> LatestMeasurementSchema:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    started = perf_counter()
    try:
        images_bytes = [file.file.read() for file in files]
        read_ms = elapsed_ms(started)

        decode_started = perf_counter()
        frames = [preprocess_image(image) for image in images_bytes]
        decode_ms = elapsed_ms(decode_started)

        analysis_started = perf_counter()
        result = analyze_frames(frames)
        analysis_ms = elapsed_ms(analysis_started)

        store_started = perf_counter()
        latest = store_cv_result(db, installation_id, result)
        store_ms = elapsed_ms(store_started)
    except ValueError as e:
        _LOGGER.warning("Invalid burst upload for %s: %s", installation_id, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        _LOGGER.exception("Error analyzing burst for %s", installation_id)
        raise HTTPException(status_code=500, detail="Analysis failed") from e

    log_timing(
        "analysis_completed",
        installation_id=installation_id,
        frame_count=len(frames),
        upload_bytes=sum(len(image) for image in images_bytes),
        read_ms=read_ms,
        decode_ms=decode_ms,
        analysis_ms=analysis_ms,
        store_ms=store_ms,
        duration_ms=elapsed_ms(started),
        dosing_problem=latest.dosing_problem.state if latest.dosing_problem else None,
        **analysis_summary(result),
    )
    return latest
