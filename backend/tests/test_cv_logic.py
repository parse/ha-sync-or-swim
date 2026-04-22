import glob
import os

import pytest
from cv_engine import analyze_burst


def get_fixture_dir(burst_folder):
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
    return os.path.join(backend_root, "tests/fixtures", burst_folder)


@pytest.mark.parametrize(
    "burst_folder,expected_chlorine_blinking,expected_status,expected_diagnosis,expected_ph_diagnosis",
    [
        ("burst_5_light_off", [2], "warning", "Low (Standby)", "Auto mode"),
        ("burst_6_light_off", [1], "warning", "Low (Standby)", "Auto mode"),
    ],
)
def test_cv_logic_fixtures(
    burst_folder,
    expected_chlorine_blinking,
    expected_status,
    expected_diagnosis,
    expected_ph_diagnosis,
):
    fixture_dir = get_fixture_dir(burst_folder)
    image_paths = sorted(glob.glob(os.path.join(fixture_dir, "*.jpg")))

    if not image_paths:
        pytest.fail(f"No images found in {fixture_dir}")

    images_bytes = []
    for path in image_paths:
        with open(path, "rb") as f:
            images_bytes.append(f.read())

    result = analyze_burst(images_bytes)

    chl = result["chlorine"]
    assert chl["status"] == expected_status
    assert chl["diagnosis"] == expected_diagnosis

    ph = result["ph"]
    assert ph["diagnosis"] == expected_ph_diagnosis

    if expected_chlorine_blinking:
        for led in expected_chlorine_blinking:
            assert led in chl["blinking"]
    else:
        assert len(chl["blinking"]) == 0
