from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import STATUS_ERROR, STATUS_WARNING
from .entry_types import SyncOrSwimConfigEntry, require_runtime_coordinator

if TYPE_CHECKING:
    from .coordinator import SyncOrSwimCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyncOrSwimConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = require_runtime_coordinator(entry)
    async_add_entities([SyncOrSwimProblemSensor(coordinator, entry)])


class SyncOrSwimProblemSensor(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "SyncOrSwim Dosing Problem"

    def __init__(
        self, coordinator: SyncOrSwimCoordinator, entry: SyncOrSwimConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_problem"

    @property
    def is_on(self) -> bool | None:
        data = self._coordinator.data
        if not data:
            return None

        pool = data.get("pool")
        if not pool:
            return cast(bool | None, data.get("stale", False))

        chlorine_status = pool.get("chlorine", {}).get("status")
        ph_status = pool.get("ph", {}).get("status")

        if chlorine_status in (None, "unknown") or ph_status in (None, "unknown"):
            return None

        return (
            chlorine_status in (STATUS_WARNING, STATUS_ERROR)
            or ph_status in (STATUS_WARNING, STATUS_ERROR)
            or data.get("stale", False)
        )

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
