from datetime import timezone
from html import escape
from urllib.parse import urlencode

import qrcode
import qrcode.image.svg
from auth import verify_web_ui_token
from db.models import Installation, Measurement
from db.session import get_db
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from measurement_service import latest_schema_from_measurement
from routes.installations import (
    latest_sensors_for_installation,
    render_error_fragment,
    render_sensors_fragment,
)
from schemas.models import validate_installation_id
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()
WEB_UI_STALENESS_THRESHOLD_MINUTES = 120


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


def render_pool_status_fragment(measurement: Measurement) -> str:
    latest = latest_schema_from_measurement(
        measurement,
        staleness_threshold_minutes=WEB_UI_STALENESS_THRESHOLD_MINUTES,
    )
    problem = latest.dosing_problem
    state = problem.state if problem else None
    state_label = state or "Unknown"
    state_class = state_label.lower()
    captured_at_value = latest.captured_at
    if captured_at_value and (
        captured_at_value.tzinfo is None or captured_at_value.utcoffset() is None
    ):
        captured_at_value = captured_at_value.replace(tzinfo=timezone.utc)
    captured_at = captured_at_value.isoformat() if captured_at_value else ""
    captured = (
        f'<time datetime="{escape(captured_at)}">{escape(captured_at)}</time>'
        if captured_at
        else "Unknown"
    )
    stale = problem.stale if problem else False
    chlorine_status = problem.chlorine_status if problem else None
    ph_status = problem.ph_status if problem else None
    action_rows = ""
    if latest.pool:
        for label, unit in (
            ("Chlorine action", latest.pool.chlorine),
            ("pH action", latest.pool.ph),
        ):
            recommended_action = unit.recommended_action.strip()
            if unit.status in {"warning", "error"} and recommended_action:
                action_rows += f"""
    <div class="pool-status-action">
      <dt>{escape(label)}</dt>
      <dd>{escape(recommended_action)}</dd>
    </div>"""

    return f"""
<section class="pool-status" aria-label="Pool status">
  <div>
    <p class="eyebrow">Pool Status</p>
    <h2>Dosing problem</h2>
  </div>
  <div class="pool-status-value {escape(state_class)}">{escape(state_label)}</div>
  <dl class="pool-status-details">
    <div>
      <dt>Captured</dt>
      <dd>{captured}</dd>
    </div>
    <div>
      <dt>Stale</dt>
      <dd>{escape("Yes" if stale else "No")}</dd>
    </div>
    <div>
      <dt>Chlorine</dt>
      <dd>{escape(chlorine_status or "unknown")}</dd>
    </div>
    <div>
      <dt>pH</dt>
      <dd>{escape(ph_status or "unknown")}</dd>
    </div>
    {action_rows}
  </dl>
</section>
"""


@router.get("/pool-status/latest-fragment", response_class=HTMLResponse)
async def get_latest_pool_status_fragment(
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

    measurement = (
        db.query(Measurement)
        .filter(Measurement.installation_id == installation_id)
        .order_by(desc(Measurement.captured_at))
        .first()
    )
    if measurement is None:
        return HTMLResponse(render_error_fragment("No measurements found."))

    return HTMLResponse(render_pool_status_fragment(measurement))


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
