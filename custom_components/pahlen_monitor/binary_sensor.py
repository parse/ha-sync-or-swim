from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import STATUS_ERROR, STATUS_WARNING
from .entry_types import PahlenConfigEntry, require_runtime_coordinator

if TYPE_CHECKING:
    from .coordinator import PahlenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PahlenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = require_runtime_coordinator(entry)
    async_add_entities([PahlenProblemSensor(coordinator, entry)])


class PahlenProblemSensor(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Pahlen Dosing Problem"

    def __init__(
        self, coordinator: PahlenCoordinator, entry: PahlenConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_problem"

    @property
    def is_on(self) -> bool | None:
        data = self._coordinator.data
        if not data:
            return None

        chlorine_status = data.get("chlorine", {}).get("status")
        ph_status = data.get("ph", {}).get("status")

        if chlorine_status in (None, "unknown") or ph_status in (None, "unknown"):
            return None

        return (
            chlorine_status in (STATUS_WARNING, STATUS_ERROR)
            or ph_status in (STATUS_WARNING, STATUS_ERROR)
            or chlorine_status in (None, "unknown")
            or ph_status in (None, "unknown")
            or data.get("stale", False)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data
        if not data:
            return {}

        return {
            "chlorine_status": data["chlorine"]["status"],
            "ph_status": data["ph"]["status"],
            "stale": data.get("stale", False),
            "stale_since": data.get("captured_at") if data.get("stale") else None,
            "error": data.get("error"),
        }
