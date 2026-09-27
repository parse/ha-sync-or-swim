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

from .entry_types import SyncOrSwimConfigEntry, require_runtime_coordinator
from .problem_attributes import (
    DOSING_PROBLEM_ERROR,
    DOSING_PROBLEM_OK,
    DOSING_PROBLEM_WARNING,
    dosing_problem_attributes,
)

if TYPE_CHECKING:
    from .coordinator import SyncOrSwimCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyncOrSwimConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = require_runtime_coordinator(entry)
    async_add_entities([SyncOrSwimDosingProblemBinarySensor(coordinator, entry)])


class SyncOrSwimDosingProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "SyncOrSwim Dosing Problem Active"

    def __init__(
        self, coordinator: SyncOrSwimCoordinator, entry: SyncOrSwimConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_problem_binary"

    @property
    def is_on(self) -> bool | None:
        data = self._coordinator.data
        if not data:
            return None

        # The backend always sends dosing_problem; without it there is no state.
        dosing_problem = data.get("dosing_problem")
        if not dosing_problem:
            return None

        state = dosing_problem.get("state")
        if state in (DOSING_PROBLEM_WARNING, DOSING_PROBLEM_ERROR):
            return True
        # Local staleness covers readings kept while the backend is unreachable.
        if data.get("stale", False):
            return True
        if state == DOSING_PROBLEM_OK:
            return False
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data
        if not data:
            return {}

        return dosing_problem_attributes(data)
