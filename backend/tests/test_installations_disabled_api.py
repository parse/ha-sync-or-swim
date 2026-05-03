from db.models import Measurement
from db.session import SessionLocal
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_disabled_endpoint_requires_auth():
    response = client.post("/installations/test-installation/disabled")

    assert response.status_code == 401


def test_disabled_endpoint_rejects_bad_installation_id():
    response = client.post(
        "/api/installations/Bad_Installation/disabled",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid installation ID"


def test_disabled_endpoint_stores_latest_disabled_measurement():
    response = client.post(
        "/api/installations/test-installation/disabled",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["installation_id"] == "test-installation"

    for unit_name in ("chlorine", "ph"):
        unit = data[unit_name]
        assert unit["status"] == "ok"
        assert unit["pattern_detected"] == "disabled"
        assert unit["blinking_leds"] == []
        assert unit["solid_leds"] == []
        assert unit["action_required"] is False
        assert unit["summary"] == "Installation disabled"
        assert unit["recommended_action"] == "No action needed"

    db = SessionLocal()
    try:
        latest = (
            db.query(Measurement)
            .filter(Measurement.installation_id == "test-installation")
            .order_by(Measurement.captured_at.desc())
            .first()
        )

        assert latest is not None
        assert latest.chlorine_status == "ok"
        assert latest.chlorine_pattern == "disabled"
        assert latest.chlorine_blinking == []
        assert latest.chlorine_solid == []
        assert latest.chlorine_action is False
        assert latest.chlorine_summary == "Installation disabled"
        assert latest.chlorine_recommended == "No action needed"
        assert latest.ph_status == "ok"
        assert latest.ph_pattern == "disabled"
        assert latest.ph_blinking == []
        assert latest.ph_solid == []
        assert latest.ph_action is False
        assert latest.ph_summary == "Installation disabled"
        assert latest.ph_recommended == "No action needed"
    finally:
        db.close()


def test_legacy_disabled_endpoint_alias_still_works():
    response = client.post(
        "/installations/test-installation/disabled",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["installation_id"] == "test-installation"
