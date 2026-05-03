from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_debug_endpoint_returns_latest_measurement_contract():
    response = client.get(
        "/debug/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "installation_id",
        "captured_at",
        "pushed_at",
        "chlorine",
        "ph",
        "raw_response",
    }
    assert data["installation_id"] == "test-installation"
    assert data["raw_response"] is None
    assert data["chlorine"]["status"] == "ok"
    assert data["ph"]["status"] == "warning"


def test_debug_endpoint_rejects_bad_installation_id():
    response = client.get(
        "/debug/Bad_Installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid installation ID"
