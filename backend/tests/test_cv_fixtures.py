import pytest
from cv_engine import analyze_burst
from fixture_cases import FIXTURE_CASES, FixtureCase


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
def test_cv_logic_fixtures(case: FixtureCase, fixture_image_loader):
    result = analyze_burst(fixture_image_loader(case.folder))

    for device, expected in case.expected.items():
        assert result[device]["level"] == expected["level"], f"{device} level mismatch"
        assert result[device]["status"] == expected["status"], (
            f"{device} status mismatch"
        )
        assert result[device]["diagnosis"] == expected["diagnosis"], (
            f"{device} diagnosis mismatch"
        )
        assert result[device]["led_states"] == expected["led_states"], (
            f"{device} led_states mismatch"
        )
        assert result[device]["blinking"] == expected["blinking"], (
            f"{device} blinking mismatch"
        )
