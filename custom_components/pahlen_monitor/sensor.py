from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entry_types import PahlenConfigEntry, require_runtime_coordinator

if TYPE_CHECKING:
    from .coordinator import PahlenCoordinator

_LOGGER = logging.getLogger(__name__)
UnitName = Literal["chlorine", "ph"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PahlenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = require_runtime_coordinator(entry)

    entities: list[SensorEntity] = []
    for unit in ("chlorine", "ph"):
        name_prefix = "Free Chlorine" if unit == "chlorine" else "pH"
        entities.append(PahlenStatusSensor(coordinator, entry, unit, name_prefix))
        entities.append(
            PahlenDetailSensor(coordinator, entry, unit, name_prefix, "summary")
        )
        entities.append(
            PahlenDetailSensor(coordinator, entry, unit, name_prefix, "diagnosis")
        )
        entities.append(
            PahlenDetailSensor(
                coordinator, entry, unit, name_prefix, "recommended_action"
            )
        )
        entities.append(PahlenLedSensor(coordinator, entry, unit, name_prefix))

    async_add_entities(entities)


class PahlenStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: PahlenCoordinator,
        entry: PahlenConfigEntry,
        unit: UnitName,
        name_prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._attr_name = f"Pahlen {name_prefix} Status"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_status"
        self._attr_icon = "mdi:pool-thermometer" if unit == "chlorine" else "mdi:ph"

    @property
    def native_value(self) -> Any:
        return self._coordinator.data[self._unit]["status"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data[self._unit]
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


class PahlenDetailSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: PahlenCoordinator,
        entry: PahlenConfigEntry,
        unit: UnitName,
        name_prefix: str,
        field: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._field = field
        label, icon = DETAIL_SENSOR_CONFIG[field]
        self._attr_name = f"Pahlen {name_prefix} {label}"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_{field}"
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        return self._coordinator.data[self._unit].get(self._field) or "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data[self._unit]
        return {
            "action_required": data.get("action_required"),
            "recommended_action": data.get("recommended_action"),
            "summary": data.get("summary"),
            "diagnosis": data.get("diagnosis"),
            "captured_at": self._coordinator.data.get("captured_at"),
        }


class PahlenLedSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: PahlenCoordinator,
        entry: PahlenConfigEntry,
        unit: UnitName,
        name_prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unit = unit
        self._attr_name = f"Pahlen {name_prefix} LEDs"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_leds"
        self._attr_icon = "mdi:led-on"

    @property
    def native_value(self) -> Any:
        data = self._coordinator.data[self._unit]
        return format_leds(data.get("solid_leds"), data.get("blinking_leds"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data[self._unit]
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
