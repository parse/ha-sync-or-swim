from html import escape
from urllib.parse import urlencode

import qrcode
import qrcode.image.svg
from auth import verify_web_ui_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from routes.installations import (
    latest_sensors_for_installation,
    render_error_fragment,
    render_sensors_fragment,
)
from schemas.models import validate_installation_id
from sqlalchemy.orm import Session

router = APIRouter()


def bearer_token_from_authorization(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        return ""
    return authorization.removeprefix("Bearer ")


def render_share_qr_fragment(
    request: Request, installation_id: str, web_token: str
) -> str:
    share_url = str(request.base_url.replace(path="/ui", query="", fragment=""))
    share_url = f"{share_url}?{urlencode({'installation_id': installation_id, 'web_token': web_token})}"
    image = qrcode.make(
        share_url,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=12,
        border=2,
    )
    qr_svg = image.to_string(encoding="unicode")

    return f"""
<div class="share-dialog-header">
  <div>
    <p class="eyebrow">Share Access</p>
    <h2 id="share-dialog-title">Scan QR code</h2>
  </div>
  <form method="dialog">
    <button class="secondary-button dialog-close" type="submit" aria-label="Close">Close</button>
  </form>
</div>
<div class="qr-code" aria-label="QR code for {escape(installation_id)}">
  {qr_svg}
</div>
<p class="share-installation">Installation ID: <strong>{escape(installation_id)}</strong></p>
"""


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


@router.get("/share-qr-fragment", response_class=HTMLResponse)
async def get_share_qr_fragment(
    request: Request,
    installation_id: str,
    authorization: str | None = Header(None),
    _auth: None = Depends(verify_web_ui_token),
) -> HTMLResponse:
    try:
        validate_installation_id(installation_id)
    except ValueError:
        return HTMLResponse(render_error_fragment("Invalid installation ID"))

    return HTMLResponse(
        render_share_qr_fragment(
            request, installation_id, bearer_token_from_authorization(authorization)
        )
    )
