from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_health_alias():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
