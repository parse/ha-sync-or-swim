import pytest
from fastapi.testclient import TestClient
from fixture_cases import FIXTURE_CASES, FixtureCase
from main import app

client = TestClient(app)


def fixture_case_params():
    return [
        pytest.param(
            case,
            id=case.folder,
            marks=pytest.mark.skip(reason=case.disabled_reason),
        )
        if not case.enabled
        else pytest.param(case, id=case.folder)
        for case in FIXTURE_CASES
    ]


@pytest.mark.parametrize("case", fixture_case_params())
def test_analyze_burst_endpoint(case: FixtureCase, multipart_files_builder):
    response = client.post(
        "/api/analyze/test-installation/burst",
        headers={"Authorization": "Bearer test-token"},
        files=multipart_files_builder(case.folder),
    )

    assert response.status_code == 200
    data = response.json()

    pool_data = data.get("pool", {})
    for device, expected in case.expected.items():
        assert pool_data[device]["status"] == expected["status"], (
            f"{device} status mismatch"
        )
        assert pool_data[device]["diagnosis"] == expected["diagnosis"], (
            f"{device} diagnosis mismatch"
        )
        assert pool_data[device]["solid_leds"] == [
            f"LED {idx + 1}"
            for idx, is_on in enumerate(expected["led_states"])
            if is_on
        ], f"{device} solid_leds mismatch"
        assert pool_data[device]["blinking_leds"] == [
            f"LED {led}" for led in expected["blinking"]
        ], f"{device} blinking_leds mismatch"


@pytest.mark.parametrize("case", fixture_case_params())
def test_analyze_burst_endpoint_stores_latest(
    case: FixtureCase, multipart_files_builder
):
    response = client.post(
        "/api/analyze/test-installation/burst",
        headers={"Authorization": "Bearer test-token"},
        files=multipart_files_builder(case.folder),
    )
    assert response.status_code == 200

    latest_response = client.get(
        "/api/latest/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["captured_at"] == response.json()["captured_at"]


@pytest.mark.parametrize("case", fixture_case_params())
def test_legacy_latest_endpoint_alias_still_works(
    case: FixtureCase, multipart_files_builder
):
    response = client.post(
        "/api/analyze/test-installation/burst",
        headers={"Authorization": "Bearer test-token"},
        files=multipart_files_builder(case.folder),
    )
    assert response.status_code == 200

    latest_response = client.get(
        "/latest/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["captured_at"] == response.json()["captured_at"]


def test_analyze_burst_endpoint_rejects_unauthorized(multipart_files_builder):
    response = client.post(
        "/api/analyze/test-installation/burst",
        files=multipart_files_builder("burst_9_light_off_bw"),
    )

    assert response.status_code == 401


def test_analyze_burst_endpoint_rejects_bad_installation_id(multipart_files_builder):
    response = client.post(
        "/api/analyze/Bad_Installation/burst",
        headers={"Authorization": "Bearer test-token"},
        files=multipart_files_builder("burst_9_light_off_bw"),
    )

    assert response.status_code == 400


def test_removed_debug_analyze_endpoint_is_not_found(multipart_files_builder):
    response = client.post(
        "/api/analyze/burst",
        files=multipart_files_builder("burst_9_light_off_bw"),
    )

    assert response.status_code == 404


def test_removed_push_endpoint_is_not_found():
    response = client.post(
        "/push/test-installation",
        headers={"Authorization": "Bearer test-token"},
        json={
            "captured_at": "2026-04-28T00:00:00Z",
            "chlorine": {
                "status": "ok",
                "diagnosis": "Auto mode",
                "pattern_detected": "auto",
                "blinking_leds": [],
                "solid_leds": ["LED 4"],
                "summary": "Auto mode",
                "action_required": False,
                "recommended_action": "",
            },
            "ph": {
                "status": "ok",
                "diagnosis": "Auto mode",
                "pattern_detected": "auto",
                "blinking_leds": [],
                "solid_leds": ["LED 4"],
                "summary": "Auto mode",
                "action_required": False,
                "recommended_action": "",
            },
        },
    )

    assert response.status_code == 404


def test_analyze_burst_endpoint_no_files():
    response = client.post(
        "/api/analyze/test-installation/burst",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_analyze_burst_endpoint_rejects_undecodable_image():
    response = client.post(
        "/api/analyze/test-installation/burst",
        headers={"Authorization": "Bearer test-token"},
        files=[("files", ("frame.jpg", b"not an image", "image/jpeg"))],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Could not decode image bytes"
