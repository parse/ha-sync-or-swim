from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities([PahlenInstallationEnabledSwitch(coordinator, entry)])


class PahlenInstallationEnabledSwitch(CoordinatorEntity, SwitchEntity):
    _attr_name = "Pahlen Installation Enabled"
    _attr_icon = "mdi:pool"

    def __init__(
        self, coordinator: PahlenCoordinator, entry: PahlenConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_installation_enabled"

    @property
    def is_on(self) -> bool:
        return self._coordinator.installation_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug("Enabling Pahlen installation monitoring")
        await self._coordinator.async_set_installation_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.debug("Disabling Pahlen installation monitoring")
        await self._coordinator.async_set_installation_enabled(False)
