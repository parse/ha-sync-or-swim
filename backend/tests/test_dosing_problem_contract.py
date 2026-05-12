from datetime import datetime, timedelta, timezone

import pytest
from db.models import Measurement
from measurement_service import latest_schema_from_measurement, unit_from_cv


def measurement(
    *,
    chlorine_status: str = "ok",
    ph_status: str = "ok",
    captured_at: datetime | None = None,
) -> Measurement:
    return Measurement(
        installation_id="test-installation",
        captured_at=captured_at or datetime.now(timezone.utc),
        chlorine_status=chlorine_status,
        chlorine_diagnosis=None,
        chlorine_pattern="auto",
        chlorine_blinking=[],
        chlorine_solid=[],
        chlorine_summary="Chlorine summary",
        chlorine_action=chlorine_status in {"warning", "error"},
        chlorine_recommended="",
        ph_status=ph_status,
        ph_diagnosis=None,
        ph_pattern="auto",
        ph_blinking=[],
        ph_solid=[],
        ph_summary="pH summary",
        ph_action=ph_status in {"warning", "error"},
        ph_recommended="",
        raw_response=None,
    )


@pytest.mark.parametrize(
    ("chlorine_status", "ph_status", "expected_state", "expected_reason"),
    [
        ("ok", "ok", "OK", "none"),
        ("warning", "ok", "Warning", "chlorine_warning"),
        ("ok", "warning", "Warning", "ph_warning"),
        ("error", "ok", "Error", "chlorine_error"),
        ("ok", "error", "Error", "ph_error"),
        ("error", "warning", "Error", "multiple_units"),
        ("warning", "warning", "Warning", "multiple_units"),
        ("unknown", "ok", None, "unknown"),
    ],
)
def test_latest_schema_includes_dosing_problem_state(
    chlorine_status: str,
    ph_status: str,
    expected_state: str | None,
    expected_reason: str,
):
    latest = latest_schema_from_measurement(
        measurement(chlorine_status=chlorine_status, ph_status=ph_status)
    )

    assert latest.dosing_problem is not None
    assert latest.dosing_problem.state == expected_state
    assert latest.dosing_problem.reason == expected_reason
    assert latest.dosing_problem.chlorine_status == chlorine_status
    assert latest.dosing_problem.ph_status == ph_status


def test_latest_schema_marks_stale_measurement_as_warning():
    latest = latest_schema_from_measurement(
        measurement(captured_at=datetime.now(timezone.utc) - timedelta(minutes=121)),
        staleness_threshold_minutes=120,
    )

    assert latest.dosing_problem is not None
    assert latest.dosing_problem.state == "Warning"
    assert latest.dosing_problem.reason == "stale_data"
    assert latest.dosing_problem.stale is True


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "status": "error",
                "mode": "error",
                "diagnosis": "Time-out (dosing stopped)",
                "level": None,
                "led_states": [False] * 7,
                "blinking": [1, 2, 3, 5, 6, 7],
            },
            "Dosing stopped after timeout. Check the dosing unit and circulation.",
        ),
        (
            {
                "status": "warning",
                "mode": "standby",
                "diagnosis": "Standby mode",
                "level": 4,
                "led_states": [False] * 7,
                "blinking": [4],
            },
            "Unit is in standby. Check that circulation is running.",
        ),
        (
            {
                "status": "warning",
                "mode": "dosing",
                "diagnosis": "Below target",
                "level": 2,
                "led_states": [False, True, False, False, False, False, False],
                "blinking": [],
            },
            "Value is below target. Check the dosing unit and current pool value.",
        ),
        (
            {
                "status": "warning",
                "mode": "dosing",
                "diagnosis": "Above target",
                "level": 6,
                "led_states": [False, False, False, False, False, True, False],
                "blinking": [],
            },
            "Value is above target. Check the dosing unit and current pool value.",
        ),
        (
            {
                "status": "warning",
                "mode": "unknown",
                "diagnosis": "Unknown pattern",
                "level": None,
                "led_states": [False] * 7,
                "blinking": [],
            },
            "Check dosing unit LED pattern.",
        ),
        (
            {
                "status": "ok",
                "mode": "auto",
                "diagnosis": "Auto mode",
                "level": 4,
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "",
        ),
    ],
)
def test_unit_from_cv_recommends_specific_actions(payload, expected):
    assert unit_from_cv(payload).recommended_action == expected
