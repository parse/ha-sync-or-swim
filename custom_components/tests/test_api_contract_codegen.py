import subprocess
import sys


def test_generated_api_types_match_backend_openapi():
    subprocess.run(
        [sys.executable, "scripts/generate_api_types.py", "--check"],
        check=True,
    )
