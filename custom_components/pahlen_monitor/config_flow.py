from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BACKEND_URL,
    CONF_CAMERA_ENTITY,
    CONF_INSTALLATION_ID,
    CONF_LIGHT_ENTITY,
    CONF_POLL_INTERVAL,
    CONF_PUSH_TOKEN,
    CONF_ROLE,
    CONF_SCAN_INTERVAL,
    CONF_STALENESS_THRESHOLD,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALENESS_THRESHOLD,
    DOMAIN,
    INSTALLATION_ID_PATTERN,
    ROLE_CONSUMER,
    ROLE_PRODUCER,
)

INSTALLATION_ID_REGEX = re.compile(INSTALLATION_ID_PATTERN)


class PahlenMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
            if not self.hass.states.get(user_input[CONF_LIGHT_ENTITY]):
                errors[CONF_LIGHT_ENTITY] = "invalid_entity"

            if not errors:
                self._data.update(user_input)
                return self.async_create_entry(title=installation_id, data=self._data)

        return self.async_show_form(
            step_id="producer",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATION_ID): str,
                    vol.Required(CONF_CAMERA_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera")
                    ),
                    vol.Required(CONF_LIGHT_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="light")
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
                self._data.update(user_input)
                return self.async_create_entry(title=installation_id, data=self._data)

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
