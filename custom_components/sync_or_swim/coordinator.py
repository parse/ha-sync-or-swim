from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from homeassistant.components import camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import SyncOrSwimApiClient, SyncOrSwimApiNotFound
from .camera_payload import normalize_camera_payload
from .const import (
    BURST_COUNT,
    BURST_INTERVAL_SECONDS,
    CONF_INSTALLATION_ENABLED,
    CONF_SHARED_SENSORS,
    DEFAULT_INSTALLATION_ENABLED,
    DOMAIN,
    LIGHT_WARMUP_SECONDS,
    STATUS_UNKNOWN,
)
from .contract_validation import SyncOrSwimData
from .entry_types import SyncOrSwimConfigEntry

_LOGGER = logging.getLogger(__name__)


def compute_stale(captured_at_iso: str | None, threshold_minutes: int) -> bool:
    if not captured_at_iso:
        return False
    try:
        captured = datetime.fromisoformat(captured_at_iso.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        age = datetime.now(tz=timezone.utc) - captured
        return age.total_seconds() > threshold_minutes * 60
    except Exception:
        return True


def unknown_data() -> SyncOrSwimData:
    """Return data for an unknown state."""
    return {
        "installation_id": "",
        "pushed_at": None,
        "raw_response": None,
        "pool": {
            "chlorine": {
                "status": STATUS_UNKNOWN,
                "diagnosis": None,
                "pattern_detected": None,
                "blinking_leds": [],
                "solid_leds": [],
                "summary": "Unknown status",
                "action_required": False,
                "recommended_action": "",
            },
            "ph": {
                "status": STATUS_UNKNOWN,
                "diagnosis": None,
                "pattern_detected": None,
                "blinking_leds": [],
                "solid_leds": [],
                "summary": "Unknown status",
                "action_required": False,
                "recommended_action": "",
            },
        },
        "sensors": [],
        "captured_at": None,
        "stale": False,
        "error": None,
    }


class ProducerCoordinator(DataUpdateCoordinator[SyncOrSwimData]):
    """Data coordinator for the producer role."""

    def __init__(self, hass: HomeAssistant, entry: SyncOrSwimConfigEntry):
        entry_data = entry.data
        interval_minutes = entry_data["scan_interval"]
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_producer_{entry_data['installation_id']}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._entry = entry
        self._entry_data = entry_data
        self._installation_id = entry_data["installation_id"]
        self._staleness_minutes = entry_data["staleness_threshold"]
        self._api_client = SyncOrSwimApiClient(
            entry_data["backend_url"],
            entry_data.get("push_token"),
            async_get_clientsession(hass),
        )

    @property
    def installation_enabled(self) -> bool:
        return self._entry.options.get(
            "installation_enabled", DEFAULT_INSTALLATION_ENABLED
        )

    async def _async_update_data(self) -> SyncOrSwimData:
        try:
            if not self.installation_enabled:
                _LOGGER.debug("Producer analysis skipped because installation disabled")
                return await self._async_store_disabled_state()

            _LOGGER.debug("Starting producer analysis via backend")

            # 1. Capture Images (Burst)
            camera_entity_id = self._entry_data.get("camera_entity")
            light_entity_id = self._entry_data.get("light_entity")

            if not camera_entity_id:
                _LOGGER.error(
                    "Camera entity is not configured in integration settings."
                )
                raise UpdateFailed("Camera entity is not configured.")

            if not light_entity_id:
                _LOGGER.warning(
                    "Light entity is not configured. Proceeding without light control."
                )

            images = []

            # Wait for light to stabilize if warmup is configured
            if LIGHT_WARMUP_SECONDS > 0:
                await asyncio.sleep(LIGHT_WARMUP_SECONDS)

            # Capture burst of images
            for i in range(BURST_COUNT):
                _LOGGER.debug("Capturing image %d/%d", i + 1, BURST_COUNT)
                # Use HA's camera service to get image bytes
                image = await camera.async_get_image(
                    self.hass, camera_entity_id, timeout=30
                )
                images.append(normalize_camera_payload(image))

                if i < BURST_COUNT - 1:
                    await asyncio.sleep(BURST_INTERVAL_SECONDS)

            _LOGGER.debug("Captured %d images.", len(images))
            if (
                not images or not images[0]
            ):  # Check if capture returned an empty list or empty bytes
                raise UpdateFailed("No image data captured from camera.")

            # 2. Call the FastAPI backend endpoint for analysis.
            remote_data = await self._api_client.analyze_burst(
                self._installation_id, images
            )

            # 3. Push shared sensors if any
            shared_sensor_entities = cast(
                list[str], self._entry_data.get(CONF_SHARED_SENSORS, [])
            )
            if shared_sensor_entities:
                _LOGGER.debug("Pushing shared sensors: %s", shared_sensor_entities)
                sensor_updates = []
                for entity_id in shared_sensor_entities:
                    state = self.hass.states.get(entity_id)
                    if state:
                        sensor_updates.append(
                            {
                                "key": entity_id,
                                "label": state.attributes.get(
                                    "friendly_name", entity_id
                                ),
                                "value": state.state,
                                "unit": state.attributes.get("unit_of_measurement"),
                                "device_class": state.attributes.get("device_class"),
                                "state_class": state.attributes.get("state_class"),
                            }
                        )
                if sensor_updates:
                    await self._api_client.push_shared_sensors(
                        self._installation_id, sensor_updates
                    )

            # 4. Process results from backend
            result: SyncOrSwimData = {
                **remote_data,
                "stale": False,
                "error": None,
            }

            _LOGGER.debug("Results received from backend and processed.")
            return result

        except Exception as exc:
            _LOGGER.exception("Error in producer update")
            raise UpdateFailed(f"Analysis failed: {exc}") from exc

    async def async_fetch_latest(self) -> None:
        """Fetch the latest backend measurement without taking new camera images."""
        remote_data = await self._async_fetch_latest_data()
        self.async_set_updated_data(remote_data)

    async def _async_fetch_latest_data(self) -> SyncOrSwimData:
        try:
            _LOGGER.debug("Fetching latest backend data for producer")
            remote_data = await self._api_client.get_latest(self._installation_id)
            return {
                **remote_data,
                "stale": compute_stale(
                    remote_data.get("captured_at"), self._staleness_minutes
                ),
                "error": None,
            }
        except SyncOrSwimApiNotFound:
            return unknown_data()
        except Exception as exc:
            _LOGGER.exception("Error fetching latest backend data")
            if isinstance(exc, UpdateFailed):
                raise
            raise UpdateFailed(f"Failed to fetch latest data: {exc}") from exc

    async def async_set_installation_enabled(self, enabled: bool) -> None:
        """Persist installation enabled state and publish matching coordinator data."""
        new_options = dict(self._entry.options)
        new_options[CONF_INSTALLATION_ENABLED] = enabled
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

        if enabled:
            await self.async_request_refresh()
            return

        disabled_state = await self._async_store_disabled_state()
        self.async_set_updated_data(disabled_state)

    async def _async_store_disabled_state(self) -> SyncOrSwimData:
        try:
            remote_data = await self._api_client.store_disabled_state(
                self._installation_id
            )
            return {
                **remote_data,
                "stale": False,
                "error": None,
            }
        except Exception as exc:
            _LOGGER.exception("Error storing disabled state")
            if isinstance(exc, UpdateFailed):
                raise
            raise UpdateFailed(f"Failed to store disabled state: {exc}") from exc


class ConsumerCoordinator(DataUpdateCoordinator[SyncOrSwimData]):
    """Data coordinator for the consumer role."""

    def __init__(self, hass: HomeAssistant, entry: SyncOrSwimConfigEntry):
        entry_data = entry.data
        interval_minutes = entry_data["poll_interval"]
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_consumer_{entry_data['installation_id']}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._entry = entry
        self._entry_data = entry_data
        self._installation_id = entry_data["installation_id"]
        self._staleness_minutes = entry_data["staleness_threshold"]
        self._api_client = SyncOrSwimApiClient(
            entry_data["backend_url"],
            entry_data.get("push_token"),
            async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> SyncOrSwimData:
        try:
            _LOGGER.debug("Polling backend for latest data")
            remote_data = await self._api_client.get_latest(self._installation_id)
            data: SyncOrSwimData = {
                **remote_data,
                "stale": compute_stale(
                    remote_data.get("captured_at"), self._staleness_minutes
                ),
                "error": None,
            }
            return data
        except SyncOrSwimApiNotFound:
            _LOGGER.info("No data found for installation %s", self._installation_id)
            return unknown_data()
        except Exception as exc:
            _LOGGER.exception("Error polling backend")
            if isinstance(exc, UpdateFailed):
                raise
            raise UpdateFailed(f"Failed to fetch data: {exc}") from exc


SyncOrSwimCoordinator = ProducerCoordinator | ConsumerCoordinator
