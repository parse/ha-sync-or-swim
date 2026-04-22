import glob
import os

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize(
    "burst_folder,expected_chlorine_blinking",
    [
        ("burst_5_light_off", 2),
        ("burst_6_light_off", 1),
    ],
)
def test_analyze_burst_endpoint(burst_folder, expected_chlorine_blinking):
    # Get backend root
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
    fixture_dir = os.path.join(backend_root, "tests/fixtures", burst_folder)
    image_paths = sorted(glob.glob(os.path.join(fixture_dir, "*.jpg")))

    if not image_paths:
        pytest.fail(f"No images found in {fixture_dir}")

    files = []
    opened_files = [open(p, "rb") for p in image_paths]
    try:
        files = [
            ("files", (os.path.basename(image_paths[i]), opened_files[i], "image/jpeg"))
            for i in range(len(image_paths))
        ]

        response = client.post("/api/analyze/burst", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "chlorine" in data
        assert "ph" in data
        assert expected_chlorine_blinking in data["chlorine"]["blinking"]
    finally:
        for f in opened_files:
            f.close()


def test_analyze_burst_endpoint_no_files():
    response = client.post("/api/analyze/burst")
    # FastAPI returns 422 Unprocessable Entity when required field is missing
    assert response.status_code == 422
