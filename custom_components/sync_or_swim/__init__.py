import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_BACKEND_URL,
    CONF_CAMERA_ENTITY,
    CONF_INSTALLATION_ENABLED,
    CONF_POLL_INTERVAL,
    CONF_PUSH_TOKEN,
    CONF_ROLE,
    CONF_SCAN_INTERVAL,
    CONF_SHARED_SENSOR_INTERVALS,
    CONF_SHARED_SENSORS,
    CONF_STALENESS_THRESHOLD,
    DEFAULT_INSTALLATION_ENABLED,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALENESS_THRESHOLD,
    PLATFORMS,
    ROLE_PRODUCER,
)
from .coordinator import ConsumerCoordinator, ProducerCoordinator
from .entry_types import SyncOrSwimConfigEntry

_LOGGER = logging.getLogger(__name__)
LEGACY_CONF_LIGHT_ENTITY = "light_entity"


async def async_migrate_entry(
    hass: HomeAssistant, entry: SyncOrSwimConfigEntry
) -> bool:
    """Migrate legacy config entries to the current data/options split."""
    if entry.version > 2:
        return False

    if entry.version == 2:
        return True

    data = dict(entry.data)
    options: dict[str, Any] = dict(entry.options)
    role = data[CONF_ROLE]

    data.pop(LEGACY_CONF_LIGHT_ENTITY, None)

    for key in (CONF_BACKEND_URL, CONF_PUSH_TOKEN, CONF_CAMERA_ENTITY):
        if key in options:
            data[key] = options.pop(key)

    if CONF_INSTALLATION_ENABLED not in options:
        options[CONF_INSTALLATION_ENABLED] = DEFAULT_INSTALLATION_ENABLED

    if role == ROLE_PRODUCER:
        for key, default in (
            (CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            (CONF_STALENESS_THRESHOLD, DEFAULT_STALENESS_THRESHOLD),
            (CONF_SHARED_SENSORS, []),
        ):
            if key not in options:
                options[key] = data.get(key, default)
            data.pop(key, None)
        options.setdefault(CONF_SHARED_SENSOR_INTERVALS, "")
    else:
        for key, default in (
            (CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            (CONF_STALENESS_THRESHOLD, DEFAULT_STALENESS_THRESHOLD),
        ):
            if key not in options:
                options[key] = data.get(key, default)
            data.pop(key, None)

    hass.config_entries.async_update_entry(
        entry,
        data=data,
        options=options,
        version=2,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SyncOrSwimConfigEntry) -> bool:
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


async def async_unload_entry(hass: HomeAssistant, entry: SyncOrSwimConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None
    return bool(unload_ok)
