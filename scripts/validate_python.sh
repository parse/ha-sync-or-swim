#!/usr/bin/env bash
set -euo pipefail

# If running in CI, don't capture output
if [ "${CI:-}" = "true" ]; then
  echo "Running in CI mode (verbose output)"

  python -m ruff check custom_components backend scripts
  python -m ruff format --check custom_components backend scripts
  python -m mypy backend/src custom_components/sync_or_swim
  python scripts/generate_api_types.py --check
  python -m compileall -q backend/src custom_components/sync_or_swim scripts

  PYTHONPATH=backend/src \
  DATABASE_URL=sqlite+pysqlite:///:memory: \
  PUSH_TOKEN=test-token \
  python -m pytest

  exit 0
fi

# --- Local mode (quiet unless failure) ---

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

FAILED=0

run_check() {
  local name="$1"
  shift
  local outfile="$TMPDIR/$(echo "$name" | tr ' ' '_')"

  printf "%s... " "$name"
  if "$@" >"$outfile" 2>&1; then
    echo "✓"
  else
    echo "✗"
    echo ""
    echo "$name failed:"
    echo "----------------------------------------"
    cat "$outfile"
    echo "----------------------------------------"
    echo ""
    FAILED=1
  fi
}

run_check "ruff" python -m ruff check custom_components backend scripts
run_check "format" python -m ruff format --check custom_components backend scripts
run_check "mypy" python -m mypy backend/src custom_components/sync_or_swim
run_check "api types" python scripts/generate_api_types.py --check
run_check "compile" python -m compileall -q backend/src custom_components/sync_or_swim scripts
run_check "tests" env \
  PYTHONPATH=backend/src \
  DATABASE_URL=sqlite+pysqlite:///:memory: \
  PUSH_TOKEN=test-token \
  python -m pytest

exit $FAILED
