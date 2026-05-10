from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entry_types import SyncOrSwimConfigEntry, require_runtime_coordinator

if TYPE_CHECKING:
    from .coordinator import SyncOrSwimCoordinator

_LOGGER = logging.getLogger(__name__)
UnitName = Literal["chlorine", "ph"]
DOSING_PROBLEM_OK = "OK"
DOSING_PROBLEM_WARNING = "Warning"
DOSING_PROBLEM_ERROR = "Error"
INVALID_SHARED_SENSOR_VALUES = {"unknown", "unavailable"}
GENERIC_SHARED_SENSOR_LABELS = {
    "battery",
    "current",
    "energy",
    "humidity",
    "illuminance",
    "power",
    "temperature",
    "voltage",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyncOrSwimConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = require_runtime_coordinator(entry)

    entities: list[SensorEntity] = [
        SyncOrSwimProblemSensor(coordinator, entry),
        SyncOrSwimLastCalibrationReadSensor(coordinator, entry),
    ]
    for unit in ("chlorine", "ph"):
        name_prefix = "Free Chlorine" if unit == "chlorine" else "pH"
        entities.append(SyncOrSwimStatusSensor(coordinator, entry, unit, name_prefix))
        entities.append(
            SyncOrSwimDetailSensor(coordinator, entry, unit, name_prefix, "summary")
        )
        entities.append(
            SyncOrSwimDetailSensor(coordinator, entry, unit, name_prefix, "diagnosis")
        )
        entities.append(
            SyncOrSwimDetailSensor(
                coordinator, entry, unit, name_prefix, "recommended_action"
            )
        )
        entities.append(SyncOrSwimLedSensor(coordinator, entry, unit, name_prefix))

    async_add_entities(entities)

    # Track discovered shared sensors
    known_shared_sensors: set[str] = set()

    def async_check_shared_sensors() -> None:
        """Check for new shared sensors in the coordinator data."""
        new_entities = []
        sensors = coordinator.data.get("sensors", [])
        for sensor_data in sensors:
            key = sensor_data["key"]
            if key not in known_shared_sensors:
                _LOGGER.debug("Found new shared sensor: %s", key)
                new_entities.append(
                    SyncOrSwimSharedSensor(coordinator, entry, sensor_data)
                )
                known_shared_sensors.add(key)

        if new_entities:
            async_add_entities(new_entities)

    # Register listener for coordinator updates
    entry.async_on_unload(coordinator.async_add_listener(async_check_shared_sensors))

    # Initial check
    async_check_shared_sensors()


class SyncOrSwimSharedSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor shared from another installation."""

    def __init__(
        self,
        coordinator: SyncOrSwimCoordinator,
        entry: SyncOrSwimConfigEntry,
        sensor_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._key = sensor_data["key"]
        display_label = shared_sensor_display_label(self._key, sensor_data["label"])
        self._attr_name = f"SyncOrSwim Shared {display_label}"
        self._attr_suggested_object_id = (
            f"syncorswim_shared_{slugify_shared_sensor_name(display_label)}"
        )
        self._attr_unique_id = f"{entry.entry_id}_shared_{self._key}"
        self._attr_device_class = sensor_data.get("device_class")
        self._attr_state_class = sensor_data.get("state_class")
        self._attr_native_unit_of_measurement = sensor_data.get("unit")

    @property
    def native_value(self) -> Any:
        sensors = self._coordinator.data.get("sensors", [])
        for s in sensors:
            if s["key"] == self._key:
                value = s["value"]
                return None if value in INVALID_SHARED_SENSOR_VALUES else value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sensors = self._coordinator.data.get("sensors", [])
        for s in sensors:
            if s["key"] == self._key:
                return {
                    "updated_at": s.get("updated_at"),
                    "original_label": s.get("label"),
                }
        return {}


class SyncOrSwimProblemSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_icon = "mdi:alert-circle-outline"
    _attr_name = "SyncOrSwim Dosing Problem"
    _attr_options = [
        DOSING_PROBLEM_OK,
        DOSING_PROBLEM_WARNING,
        DOSING_PROBLEM_ERROR,
    ]

    def __init__(
        self, coordinator: SyncOrSwimCoordinator, entry: SyncOrSwimConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_problem"

    @property
    def native_value(self) -> str | None:
        data = self._coordinator.data
        if not data:
            return None

        dosing_problem = data.get("dosing_problem")
        if dosing_problem:
            return cast(str | None, dosing_problem.get("state"))

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data
        if not data:
            return {}

        pool = data.get("pool")
        attributes = {
            "stale": data.get("stale", False),
            "stale_since": data.get("captured_at") if data.get("stale") else None,
            "error": data.get("error"),
        }

        if pool:
            attributes.update(
                {
                    "chlorine_status": pool["chlorine"]["status"],
                    "ph_status": pool["ph"]["status"],
                }
            )

        return attributes


class SyncOrSwimLastCalibrationReadSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "SyncOrSwim Last Calibration Read"

    def __init__(
        self, coordinator: SyncOrSwimCoordinator, entry: SyncOrSwimConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_last_calibration_read"

    @property
    def native_value(self) -> datetime | None:
        return parse_backend_timestamp(self._coordinator.data.get("captured_at"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        captured_at = self._coordinator.data.get("captured_at")
        return {
            "captured_at": captured_at,
            "pushed_at": self._coordinator.data.get("pushed_at"),
            "stale": self._coordinator.data.get("stale", False),
            "installation_id": self._coordinator.data.get("installation_id"),
        }


class SyncOrSwimStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SyncOrSwimCoordinator,
        entry: SyncOrSwimConfigEntry,
        unit: UnitName,
        name_prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._attr_name = f"SyncOrSwim {name_prefix} Status"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_status"
        self._attr_icon = "mdi:pool-thermometer" if unit == "chlorine" else "mdi:ph"

    @property
    def native_value(self) -> Any:
        pool = self._coordinator.data.get("pool")
        return pool[self._unit]["status"] if pool else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pool = self._coordinator.data.get("pool")
        if not pool:
            return {"captured_at": self._coordinator.data.get("captured_at")}

        data = pool[self._unit]
        return {
            "diagnosis": data.get("diagnosis"),
            "pattern_detected": data.get("pattern_detected"),
            "blinking_leds": data.get("blinking_leds"),
            "solid_leds": data.get("solid_leds"),
            "summary": data.get("summary"),
            "action_required": data.get("action_required"),
            "recommended_action": data.get("recommended_action"),
            "captured_at": self._coordinator.data.get("captured_at"),
        }


DETAIL_SENSOR_CONFIG = {
    "summary": ("Summary", "mdi:text-box-outline"),
    "diagnosis": ("Diagnosis", "mdi:clipboard-pulse-outline"),
    "recommended_action": ("Recommended Action", "mdi:wrench-outline"),
}


class SyncOrSwimDetailSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SyncOrSwimCoordinator,
        entry: SyncOrSwimConfigEntry,
        unit: UnitName,
        name_prefix: str,
        field: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._field = field
        label, icon = DETAIL_SENSOR_CONFIG[field]
        self._attr_name = f"SyncOrSwim {name_prefix} {label}"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_{field}"
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        pool = self._coordinator.data.get("pool")
        return pool[self._unit].get(self._field) or "none" if pool else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pool = self._coordinator.data.get("pool")
        if not pool:
            return {"captured_at": self._coordinator.data.get("captured_at")}

        data = pool[self._unit]
        return {
            "action_required": data.get("action_required"),
            "recommended_action": data.get("recommended_action"),
            "summary": data.get("summary"),
            "diagnosis": data.get("diagnosis"),
            "captured_at": self._coordinator.data.get("captured_at"),
        }


class SyncOrSwimLedSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SyncOrSwimCoordinator,
        entry: SyncOrSwimConfigEntry,
        unit: UnitName,
        name_prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._attr_name = f"SyncOrSwim {name_prefix} LEDs"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_leds"
        self._attr_icon = "mdi:led-on"

    @property
    def native_value(self) -> Any:
        pool = self._coordinator.data.get("pool")
        if not pool:
            return "none"
        data = pool[self._unit]
        return format_leds(data.get("solid_leds"), data.get("blinking_leds"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pool = self._coordinator.data.get("pool")
        if not pool:
            return {"captured_at": self._coordinator.data.get("captured_at")}

        data = pool[self._unit]
        return {
            "solid_leds": data.get("solid_leds") or [],
            "blinking_leds": data.get("blinking_leds") or [],
            "captured_at": self._coordinator.data.get("captured_at"),
        }


def format_leds(solid_leds: list[str] | None, blinking_leds: list[str] | None) -> str:
    parts = []
    if solid_leds:
        parts.append(f"Solid: {', '.join(solid_leds)}")
    if blinking_leds:
        parts.append(f"Blinking: {', '.join(blinking_leds)}")
    return "; ".join(parts) if parts else "none"


def shared_sensor_display_label(key: str, label: str) -> str:
    if label.strip().lower() not in GENERIC_SHARED_SENSOR_LABELS:
        return label

    object_id = key.split(".", 1)[-1]
    parts = [p for p in object_id.split("_") if p and p not in {"sensor", "temp"}]
    if parts:
        return " ".join(p.capitalize() for p in parts)
    return label


def slugify_shared_sensor_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "sensor"


def parse_backend_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)

    return timestamp
