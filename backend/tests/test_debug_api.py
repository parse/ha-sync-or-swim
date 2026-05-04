from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_debug_endpoint_returns_latest_measurement_contract():
    response = client.get(
        "/api/debug/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "installation_id",
        "captured_at",
        "pushed_at",
        "pool",
        "sensors",
        "raw_response",
    }
    assert data["installation_id"] == "test-installation"
    assert data["raw_response"] is None
    assert data["pool"]["chlorine"]["status"] == "ok"
    assert data["pool"]["ph"]["status"] == "warning"


def test_debug_endpoint_rejects_bad_installation_id():
    response = client.get(
        "/api/debug/Bad_Installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid installation ID"


def test_legacy_debug_endpoint_alias_still_works():
    response = client.get(
        "/debug/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["installation_id"] == "test-installation"
