import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ROLE, DOMAIN, ROLE_PRODUCER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    if entry.data.get(CONF_ROLE) != ROLE_PRODUCER:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PahlenAnalyzeButton(coordinator, entry)])


class PahlenAnalyzeButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Pahlen Analyze Now"
    _attr_icon = "mdi:camera-refresh"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_analyze_now"

    async def async_press(self) -> None:
        _LOGGER.debug("Manual analysis requested via button")
        await self.coordinator.async_request_refresh()
