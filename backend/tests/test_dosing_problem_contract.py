from datetime import datetime, timedelta, timezone

import pytest
from db.models import Measurement
from measurement_service import latest_schema_from_measurement


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
    ("chlorine_status", "ph_status", "expected"),
    [
        ("ok", "ok", "OK"),
        ("warning", "ok", "Warning"),
        ("ok", "warning", "Warning"),
        ("error", "ok", "Error"),
        ("ok", "error", "Error"),
        ("unknown", "ok", None),
    ],
)
def test_latest_schema_includes_dosing_problem_state(
    chlorine_status: str, ph_status: str, expected: str | None
):
    latest = latest_schema_from_measurement(
        measurement(chlorine_status=chlorine_status, ph_status=ph_status)
    )

    assert latest.dosing_problem is not None
    assert latest.dosing_problem.state == expected
    assert latest.dosing_problem.chlorine_status == chlorine_status
    assert latest.dosing_problem.ph_status == ph_status


def test_latest_schema_marks_stale_measurement_as_warning():
    latest = latest_schema_from_measurement(
        measurement(captured_at=datetime.now(timezone.utc) - timedelta(minutes=121)),
        staleness_threshold_minutes=120,
    )

    assert latest.dosing_problem is not None
    assert latest.dosing_problem.state == "Warning"
    assert latest.dosing_problem.stale is True
