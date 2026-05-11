from datetime import datetime, timezone

from db.models import Installation, Measurement
from db.session import SessionLocal
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def add_measurement() -> None:
    with SessionLocal() as db:
        db.add(Installation(id="test-installation"))
        db.add(
            Measurement(
                installation_id="test-installation",
                captured_at=datetime.now(timezone.utc),
                chlorine_status="ok",
                chlorine_diagnosis=None,
                chlorine_pattern="auto",
                chlorine_blinking=[],
                chlorine_solid=[],
                chlorine_summary="Chlorine summary",
                chlorine_action=False,
                chlorine_recommended="",
                ph_status="ok",
                ph_diagnosis=None,
                ph_pattern="auto",
                ph_blinking=[],
                ph_solid=[],
                ph_summary="pH summary",
                ph_action=False,
                ph_recommended="",
                raw_response=None,
            )
        )
        db.commit()


def test_latest_rejects_negative_staleness_threshold():
    add_measurement()

    response = client.get(
        "/api/latest/test-installation",
        params={"staleness_threshold_minutes": -1},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "staleness_threshold_minutes must be non-negative"
    )
