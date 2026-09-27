import os
import subprocess
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"


def run_app_logging(code: str) -> str:
    """Run code after importing main in a clean interpreter, outside pytest's
    log capture, and return what reached stderr."""
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "PYTHONPATH": str(BACKEND_SRC),
    }
    result = subprocess.run(
        [sys.executable, "-c", f"import main\n{code}"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stderr


def test_request_timing_events_reach_the_log_output():
    stderr = run_app_logging(
        "from request_timing import log_timing\nlog_timing('probe', value=1)"
    )

    assert '"event": "probe"' in stderr


def test_third_party_info_logs_stay_quiet():
    stderr = run_app_logging(
        "import logging\nlogging.getLogger('some.library').info('noise')"
    )

    assert "noise" not in stderr
