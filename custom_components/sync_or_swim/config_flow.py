from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_helpers import effective_entry_value, parse_shared_sensor_intervals
from .const import (
    CONF_BACKEND_URL,
    CONF_CAMERA_ENTITY,
    CONF_INSTALLATION_ENABLED,
    CONF_INSTALLATION_ID,
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
    DOMAIN,
    INSTALLATION_ID_PATTERN,
    ROLE_CONSUMER,
    ROLE_PRODUCER,
)

INSTALLATION_ID_REGEX = re.compile(INSTALLATION_ID_PATTERN)


class SyncOrSwimMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_ROLE] == ROLE_PRODUCER:
                return await self.async_step_producer()
            return await self.async_step_consumer()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ROLE): vol.In([ROLE_PRODUCER, ROLE_CONSUMER])}
            ),
        )

    async def async_step_producer(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors = {}
        if user_input is not None:
            installation_id = user_input[CONF_INSTALLATION_ID]
            if not INSTALLATION_ID_REGEX.fullmatch(installation_id):
                errors[CONF_INSTALLATION_ID] = "invalid_installation_id"

            await self.async_set_unique_id(installation_id)
            self._abort_if_unique_id_configured()

            # Validate backend URL
            if not errors and not await self._test_backend_url(
                user_input[CONF_BACKEND_URL]
            ):
                errors["base"] = "cannot_connect"

            # Validate entities
            if not self.hass.states.get(user_input[CONF_CAMERA_ENTITY]):
                errors[CONF_CAMERA_ENTITY] = "invalid_entity"
            if not errors:
                return self.async_create_entry(
                    title=installation_id,
                    data={
                        CONF_ROLE: self._data.get(CONF_ROLE, ROLE_PRODUCER),
                        CONF_INSTALLATION_ID: installation_id,
                        CONF_CAMERA_ENTITY: user_input[CONF_CAMERA_ENTITY],
                        CONF_PUSH_TOKEN: user_input[CONF_PUSH_TOKEN],
                        CONF_BACKEND_URL: user_input[CONF_BACKEND_URL],
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                        CONF_STALENESS_THRESHOLD: user_input.get(
                            CONF_STALENESS_THRESHOLD, DEFAULT_STALENESS_THRESHOLD
                        ),
                        CONF_SHARED_SENSORS: user_input.get(CONF_SHARED_SENSORS, []),
                        CONF_INSTALLATION_ENABLED: DEFAULT_INSTALLATION_ENABLED,
                        CONF_SHARED_SENSOR_INTERVALS: "",
                    },
                )

        return self.async_show_form(
            step_id="producer",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATION_ID): str,
                    vol.Required(CONF_CAMERA_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera")
                    ),
                    vol.Optional(CONF_SHARED_SENSORS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", multiple=True)
                    ),
                    vol.Required(CONF_PUSH_TOKEN): str,
                    vol.Required(CONF_BACKEND_URL): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): int,
                    vol.Optional(
                        CONF_STALENESS_THRESHOLD, default=DEFAULT_STALENESS_THRESHOLD
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_consumer(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors = {}
        if user_input is not None:
            installation_id = user_input[CONF_INSTALLATION_ID]
            if not INSTALLATION_ID_REGEX.fullmatch(installation_id):
                errors[CONF_INSTALLATION_ID] = "invalid_installation_id"

            await self.async_set_unique_id(installation_id)
            self._abort_if_unique_id_configured()

            # Validate backend URL
            if not errors and not await self._test_backend_url(
                user_input[CONF_BACKEND_URL]
            ):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=installation_id,
                    data={
                        CONF_ROLE: self._data.get(CONF_ROLE, ROLE_CONSUMER),
                        CONF_INSTALLATION_ID: installation_id,
                        CONF_PUSH_TOKEN: user_input[CONF_PUSH_TOKEN],
                        CONF_BACKEND_URL: user_input[CONF_BACKEND_URL],
                    },
                    options={
                        CONF_POLL_INTERVAL: user_input.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                        CONF_STALENESS_THRESHOLD: user_input.get(
                            CONF_STALENESS_THRESHOLD, DEFAULT_STALENESS_THRESHOLD
                        ),
                    },
                )

        return self.async_show_form(
            step_id="consumer",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATION_ID): str,
                    vol.Required(CONF_PUSH_TOKEN): str,
                    vol.Required(CONF_BACKEND_URL): str,
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                    ): int,
                    vol.Optional(
                        CONF_STALENESS_THRESHOLD, default=DEFAULT_STALENESS_THRESHOLD
                    ): int,
                }
            ),
            errors=errors,
        )

    async def _test_backend_url(self, url: str) -> bool:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{url.rstrip('/')}/api/health", timeout=10
            ) as response:
                return bool(response.status == 200)
        except Exception:
            return False

    @staticmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SyncOrSwimOptionsFlowHandler(config_entry)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Update connection and entity settings for an existing entry."""
        entry = self._get_reconfigure_entry()
        role = entry.data[CONF_ROLE]
        errors: dict[str, str] = {}
        await self.async_set_unique_id(entry.data[CONF_INSTALLATION_ID])
        self._abort_if_unique_id_mismatch()

        if user_input is not None:
            if not await self._test_backend_url(user_input[CONF_BACKEND_URL]):
                errors["base"] = "cannot_connect"

            if role == ROLE_PRODUCER:
                if not self.hass.states.get(user_input[CONF_CAMERA_ENTITY]):
                    errors[CONF_CAMERA_ENTITY] = "invalid_entity"

            if not errors:
                data_updates = {
                    CONF_BACKEND_URL: user_input[CONF_BACKEND_URL],
                    CONF_PUSH_TOKEN: user_input[CONF_PUSH_TOKEN],
                }
                if role == ROLE_PRODUCER:
                    data_updates[CONF_CAMERA_ENTITY] = user_input[CONF_CAMERA_ENTITY]
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reconfigure_schema(entry),
            errors=errors,
        )


class SyncOrSwimOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle SyncOrSwim options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._config_entry.data[CONF_ROLE] == ROLE_PRODUCER:
                try:
                    parse_shared_sensor_intervals(
                        user_input.get(CONF_SHARED_SENSOR_INTERVALS, "")
                    )
                except ValueError:
                    errors[CONF_SHARED_SENSOR_INTERVALS] = (
                        "invalid_shared_sensor_intervals"
                    )

            if not errors:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry),
            errors=errors,
        )


def _entry_value(
    entry: config_entries.ConfigEntry, key: str, default: Any | None = None
) -> Any:
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


def _reconfigure_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    role = entry.data[CONF_ROLE]
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_BACKEND_URL, default=_entry_value(entry, CONF_BACKEND_URL)
        ): str,
        vol.Required(
            CONF_PUSH_TOKEN, default=_entry_value(entry, CONF_PUSH_TOKEN)
        ): str,
    }
    if role == ROLE_PRODUCER:
        fields.update(
            {
                vol.Required(
                    CONF_CAMERA_ENTITY,
                    default=_entry_value(entry, CONF_CAMERA_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="camera")
                ),
            }
        )
    return vol.Schema(fields)


def _options_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    role = entry.data[CONF_ROLE]
    fields: dict[Any, Any] = {
        vol.Optional(
            CONF_STALENESS_THRESHOLD,
            default=effective_entry_value(
                entry, CONF_STALENESS_THRESHOLD, DEFAULT_STALENESS_THRESHOLD
            ),
        ): int,
    }

    if role == ROLE_PRODUCER:
        fields.update(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=effective_entry_value(
                        entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    CONF_INSTALLATION_ENABLED,
                    default=effective_entry_value(
                        entry,
                        CONF_INSTALLATION_ENABLED,
                        DEFAULT_INSTALLATION_ENABLED,
                    ),
                ): bool,
                vol.Optional(
                    CONF_SHARED_SENSORS,
                    default=effective_entry_value(entry, CONF_SHARED_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    CONF_SHARED_SENSOR_INTERVALS,
                    default=effective_entry_value(
                        entry, CONF_SHARED_SENSOR_INTERVALS, ""
                    ),
                ): str,
            }
        )
    else:
        fields[
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=effective_entry_value(
                    entry, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                ),
            )
        ] = int

    return vol.Schema(fields)
