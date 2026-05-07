from auth import verify_web_ui_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from routes.installations import (
    latest_sensors_for_installation,
    render_error_fragment,
    render_sensors_fragment,
)
from schemas.models import validate_installation_id
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/sensors/latest-fragment", response_class=HTMLResponse)
async def get_latest_sensors_fragment(
    installation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_web_ui_token),
) -> HTMLResponse:
    try:
        validate_installation_id(installation_id)
    except ValueError:
        return HTMLResponse(render_error_fragment("Invalid installation ID"))

    installation = db.get(Installation, installation_id)
    if installation is None:
        return HTMLResponse(render_error_fragment("Installation not found."))

    sensors = latest_sensors_for_installation(db, installation_id)
    return HTMLResponse(render_sensors_fragment(sensors))
