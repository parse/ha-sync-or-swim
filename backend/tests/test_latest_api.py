from datetime import datetime, timezone

from db.models import Installation, Measurement
from db.session import SessionLocal
from fastapi.testclient import TestClient
from main import app
from measurement_service import as_utc

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


def test_latest_checks_auth_before_installation_id():
    response = client.get("/api/latest/Bad_Installation")

    assert response.status_code == 401


def test_latest_rejects_bad_installation_id_before_query_validation():
    response = client.get(
        "/api/latest/Bad_Installation",
        params={"staleness_threshold_minutes": "abc"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid installation ID"


def latest_read_events(caplog) -> list[dict]:
    import json

    return [
        payload
        for record in caplog.records
        if record.name == "sync_or_swim.request_timing"
        and (payload := json.loads(record.getMessage()))["event"] == "latest_read"
    ]


def test_latest_logs_read_summary(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="sync_or_swim.request_timing")
    add_measurement()

    response = client.get(
        "/api/latest/test-installation",
        params={"staleness_threshold_minutes": 120},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    [event] = latest_read_events(caplog)
    assert event["found"] is True
    logged = datetime.fromisoformat(event["captured_at"])
    assert logged.tzinfo is not None
    assert logged == as_utc(datetime.fromisoformat(response.json()["captured_at"]))
    assert event["stale"] is False
    assert event["dosing_problem"] == response.json()["dosing_problem"]["state"]
    assert event["sensor_count"] == 0
    assert event["duration_ms"] >= 0


def test_latest_logs_missing_measurement(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="sync_or_swim.request_timing")

    response = client.get(
        "/api/latest/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    [event] = latest_read_events(caplog)
    assert event["found"] is False
