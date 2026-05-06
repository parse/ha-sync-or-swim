from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from .const import (
    CONF_SHARED_SENSOR_INTERVALS,
    CONF_SHARED_SENSORS,
    DEFAULT_SHARED_SENSORS_INTERVAL,
)
from .entry_types import SyncOrSwimConfigEntry

T = TypeVar("T")


def effective_entry_value(entry: SyncOrSwimConfigEntry, key: str, default: T) -> T:
    """Return an option value, falling back to config entry data and a default."""
    options = cast(Mapping[str, Any], entry.options)
    data = cast(Mapping[str, Any], entry.data)
    if key in options:
        return cast(T, options[key])
    return cast(T, data.get(key, default))


def effective_shared_sensors(entry: SyncOrSwimConfigEntry) -> list[str]:
    """Return shared sensor entity IDs from options or legacy entry data."""
    default_sensors: list[str] = []
    value = effective_entry_value(entry, CONF_SHARED_SENSORS, default_sensors)
    return list(value)


def parse_shared_sensor_intervals(raw_value: Any) -> dict[str, int]:
    """Parse one entity_id=minutes mapping per line."""
    if raw_value in (None, ""):
        return {}
    if not isinstance(raw_value, str):
        raise ValueError("Shared sensor intervals must be text")

    intervals: dict[str, int] = {}
    for line in raw_value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "=" not in stripped:
            raise ValueError("Use entity_id=minutes for each shared sensor interval")
        entity_id, minutes_raw = stripped.split("=", 1)
        entity_id = entity_id.strip()
        minutes_raw = minutes_raw.strip()
        if not entity_id or not minutes_raw:
            raise ValueError("Shared sensor interval entries must include both fields")
        try:
            minutes = int(minutes_raw)
        except ValueError as exc:
            raise ValueError("Shared sensor intervals must be whole minutes") from exc
        if minutes < 1:
            raise ValueError("Shared sensor intervals must be at least 1 minute")
        intervals[entity_id] = minutes

    return intervals


def shared_sensor_interval_minutes(entry: SyncOrSwimConfigEntry, entity_id: str) -> int:
    """Return the configured interval for one shared sensor."""
    raw_value = effective_entry_value(entry, CONF_SHARED_SENSOR_INTERVALS, "")
    intervals = parse_shared_sensor_intervals(raw_value)
    return intervals.get(entity_id, DEFAULT_SHARED_SENSORS_INTERVAL)
