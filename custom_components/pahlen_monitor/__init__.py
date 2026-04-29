import logging

from homeassistant.core import HomeAssistant

from .const import PLATFORMS, ROLE_PRODUCER
from .coordinator import ConsumerCoordinator, ProducerCoordinator
from .entry_types import PahlenConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PahlenConfigEntry) -> bool:
    role = entry.data["role"]

    if role == ROLE_PRODUCER:
        _LOGGER.debug("Setting up producer for %s", entry.title)
        coordinator = ProducerCoordinator(hass, entry)
    else:
        _LOGGER.debug("Setting up consumer for %s", entry.title)
        coordinator = ConsumerCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PahlenConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None
    return bool(unload_ok)
