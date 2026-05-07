from db.models import Installation
from db.session import SessionLocal
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_serves_web_ui():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "text/html" in response.headers["content-type"]
    assert "SyncOrSwim" in response.text
    assert "Shared Sensors" in response.text
    assert "Clear saved access" in response.text
    assert "updateAccessView" in response.text
    assert "removeItem" in response.text
    assert 'href="/static/ui.css"' in response.text
    assert "/ui/sensors/latest-fragment" in response.text
    assert "htmx.org@2.0.10" in response.text
    assert "/sensors/latest" in response.text
    assert "requestSubmit" not in response.text
    assert 'params.get("installation_id")' in response.text
    assert "htmx.ajax" in response.text
    assert "Intl.DateTimeFormat" in response.text
    assert "time[datetime]" in response.text


def test_ui_alias_serves_web_ui():
    root_response = client.get("/")
    alias_response = client.get("/ui")

    assert alias_response.status_code == 200
    assert alias_response.headers["cache-control"] == "no-store"
    assert alias_response.text == root_response.text


def test_static_css_is_served():
    response = client.get("/static/ui.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert "page-header" in response.text
    assert "secondary-button" in response.text
    assert "grid-template-columns" in response.text


def test_latest_sensors_accepts_web_ui_token():
    sensor_response = client.post(
        "/api/installations/test-installation/sensors",
        headers={"Authorization": "Bearer test-token"},
        json=[
            {
                "key": "sensor.cellar_temperature",
                "label": "Cellar temperature",
                "value": "12.3",
                "unit": "C",
                "device_class": "temperature",
                "state_class": "measurement",
            }
        ],
    )
    assert sensor_response.status_code == 200

    response = client.get(
        "/api/installations/test-installation/sensors/latest",
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "key": "sensor.cellar_temperature",
            "label": "Cellar temperature",
            "value": "12.3",
            "unit": "C",
            "device_class": "temperature",
            "state_class": "measurement",
            "updated_at": sensor_response.json()[0]["updated_at"],
        }
    ]


def test_latest_sensors_fragment_returns_sensor_table():
    client.post(
        "/api/installations/test-installation/sensors",
        headers={"Authorization": "Bearer test-token"},
        json=[
            {
                "key": "sensor.cellar_temperature",
                "label": "Cellar temperature",
                "value": "12.3",
                "unit": "C",
                "device_class": "temperature",
                "state_class": "measurement",
            }
        ],
    )

    response = client.get(
        "/ui/sensors/latest-fragment",
        params={"installation_id": "test-installation"},
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Cellar temperature" in response.text
    assert "12.3 C" in response.text
    assert "<time datetime=" in response.text
    assert "+00:00" in response.text


def test_latest_sensors_fragment_escapes_sensor_values():
    client.post(
        "/api/installations/test-installation/sensors",
        headers={"Authorization": "Bearer test-token"},
        json=[
            {
                "key": "sensor.html",
                "label": "<b>Label</b>",
                "value": "<script>alert(1)</script>",
            }
        ],
    )

    response = client.get(
        "/ui/sensors/latest-fragment",
        params={"installation_id": "test-installation"},
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 200
    assert "&lt;b&gt;Label&lt;/b&gt;" in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text


def test_latest_sensors_fragment_rejects_missing_wrong_and_push_tokens():
    for headers in (
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "Bearer test-token"},
    ):
        response = client.get(
            "/ui/sensors/latest-fragment",
            params={"installation_id": "test-installation"},
            headers=headers,
        )

        assert response.status_code == 401


def test_latest_sensors_fragment_returns_ui_errors_as_html():
    bad_id_response = client.get(
        "/ui/sensors/latest-fragment",
        params={"installation_id": "Bad_Installation"},
        headers={"Authorization": "Bearer web-test-token"},
    )
    missing_response = client.get(
        "/ui/sensors/latest-fragment",
        params={"installation_id": "unknown-installation"},
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert bad_id_response.status_code == 200
    assert "Invalid installation ID" in bad_id_response.text
    assert missing_response.status_code == 200
    assert "Installation not found." in missing_response.text


def test_latest_sensors_rejects_missing_wrong_and_push_tokens():
    for headers in (
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "Bearer test-token"},
    ):
        response = client.get(
            "/api/installations/test-installation/sensors/latest",
            headers=headers,
        )

        assert response.status_code == 401


def test_latest_sensors_requires_configured_web_ui_token(monkeypatch):
    monkeypatch.delenv("WEB_UI_TOKEN")

    response = client.get(
        "/api/installations/test-installation/sensors/latest",
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "WEB_UI_TOKEN not configured on server"


def test_latest_sensors_returns_empty_for_known_installation_without_sensors():
    with SessionLocal() as db:
        db.add(Installation(id="empty-installation"))
        db.commit()

    response = client.get(
        "/api/installations/empty-installation/sensors/latest",
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_latest_sensors_rejects_bad_installation_id():
    response = client.get(
        "/api/installations/Bad_Installation/sensors/latest",
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid installation ID"


def test_latest_sensors_returns_not_found_for_unknown_installation():
    response = client.get(
        "/api/installations/unknown-installation/sensors/latest",
        headers={"Authorization": "Bearer web-test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Installation not found"


def test_legacy_fragment_route_redirects_to_ui_path():
    for old_path in (
        "/installations/sensors/latest-fragment",
        "/api/installations/sensors/latest-fragment",
    ):
        response = client.get(
            old_path,
            params={"installation_id": "test-installation"},
            follow_redirects=False,
        )

        assert response.status_code == 308, f"{old_path} should redirect"
        assert response.headers["location"] == (
            "/ui/sensors/latest-fragment?installation_id=test-installation"
        )
