import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ROLE,
    DOMAIN,
    PLATFORMS,
    ROLE_PRODUCER,
)
from .coordinator import ConsumerCoordinator, ProducerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    role = entry.data[CONF_ROLE]

    if role == ROLE_PRODUCER:
        _LOGGER.debug("Setting up producer for %s", entry.title)
        coordinator = ProducerCoordinator(hass, entry)
    else:
        _LOGGER.debug("Setting up consumer for %s", entry.title)
        coordinator = ConsumerCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
