import json
import logging
from time import perf_counter
from typing import Any

_LOGGER = logging.getLogger("sync_or_swim.request_timing")


def log_timing(event: str, **fields: Any) -> None:
    """Write a queryable timing event without credentials or sensor readings."""
    _LOGGER.info("%s", json.dumps({"event": event, **fields}, default=str))


def elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 1)
