from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ROLE, ROLE_PRODUCER
from .entry_types import PahlenConfigEntry, require_runtime_coordinator

if TYPE_CHECKING:
    from .coordinator import PahlenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PahlenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if entry.data.get(CONF_ROLE) != ROLE_PRODUCER:
        return

    coordinator = require_runtime_coordinator(entry)
    async_add_entities(
        [
            PahlenAnalyzeButton(coordinator, entry),
            PahlenFetchLatestButton(coordinator, entry),
        ]
    )


class PahlenAnalyzeButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Pahlen Analyze Now"
    _attr_icon = "mdi:camera-refresh"

    def __init__(
        self, coordinator: PahlenCoordinator, entry: PahlenConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_analyze_now"

    @property
    def available(self) -> bool:
        return self._coordinator.installation_enabled

    async def async_press(self) -> None:
        _LOGGER.debug("Manual analysis requested via button")
        await self._coordinator.async_request_refresh()


class PahlenFetchLatestButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Pahlen Fetch Latest"
    _attr_icon = "mdi:cloud-refresh"

    def __init__(
        self, coordinator: PahlenCoordinator, entry: PahlenConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_fetch_latest"

    @property
    def available(self) -> bool:
        return self._coordinator.installation_enabled

    async def async_press(self) -> None:
        _LOGGER.debug("Manual latest-data fetch requested via button")
        await self._coordinator.async_fetch_latest()
