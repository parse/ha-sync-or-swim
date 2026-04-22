import asyncio  # Added import for asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from homeassistant.components import camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BURST_COUNT,
    BURST_INTERVAL_SECONDS,
    CONF_BACKEND_URL,
    CONF_CAMERA_ENTITY,
    CONF_INSTALLATION_ID,
    CONF_LIGHT_ENTITY,
    CONF_POLL_INTERVAL,
    CONF_PUSH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_STALENESS_THRESHOLD,
    DOMAIN,
    LIGHT_WARMUP_SECONDS,
    STATUS_UNKNOWN,
)
from .contract_validation import (
    PahlenData,
    validate_latest_measurement,
)

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


def unknown_data() -> PahlenData:
    """Return data for an unknown state."""
    return {
        "installation_id": "",
        "pushed_at": None,
        "raw_response": None,
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
        "captured_at": None,
        "stale": False,
        "error": None,
    }


class ProducerCoordinator(DataUpdateCoordinator[PahlenData]):
    """Data coordinator for the producer role."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        interval_minutes = entry.data[
            CONF_SCAN_INTERVAL
        ]  # Assuming SCAN_INTERVAL is for producer
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_producer_{entry.data[CONF_INSTALLATION_ID]}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._entry = entry
        self._backend_url = entry.data[CONF_BACKEND_URL].rstrip("/")
        self._installation_id = entry.data[CONF_INSTALLATION_ID]
        self._staleness_minutes = entry.data[CONF_STALENESS_THRESHOLD]

    async def _async_update_data(self) -> PahlenData:
        try:
            _LOGGER.debug("Starting producer analysis via backend")

            # 1. Capture Images (Burst)
            camera_entity_id = self._entry.data.get(CONF_CAMERA_ENTITY)
            light_entity_id = self._entry.data.get(
                CONF_LIGHT_ENTITY
            )  # Assuming light entity is configured

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
                image_bytes = await camera.async_get_image(camera_entity_id, timeout=30)
                images.append(image_bytes)

                if i < BURST_COUNT - 1:
                    await asyncio.sleep(BURST_INTERVAL_SECONDS)

            _LOGGER.debug("Captured %d images.", len(images))
            if (
                not images or not images[0]
            ):  # Check if capture returned an empty list or empty bytes
                raise UpdateFailed("No image data captured from camera.")

            # 2. Call the new FastAPI backend endpoint for analysis
            async with aiohttp.ClientSession() as session:
                token = self._entry.data.get(CONF_PUSH_TOKEN)
                headers = {"Authorization": f"Bearer {token}"} if token else {}

                # Prepare multipart/form-data
                data = aiohttp.FormData()
                for i, img_bytes in enumerate(images):
                    data.add_field(
                        "files",
                        img_bytes,
                        filename=f"frame_{i}.jpg",
                        content_type="image/jpeg",
                    )

                async with session.post(
                    f"{self._backend_url}/api/analyze/burst",
                    data=data,
                    headers=headers,
                    timeout=60,
                ) as response:
                    response_body = await response.text()
                    if response.status != 200:
                        _LOGGER.error(
                            "Backend analysis failed: %s %s",
                            response.status,
                            response_body,
                        )
                        raise UpdateFailed(
                            f"Backend analysis failed: {response.status}"
                        )

                    analysis = await response.json()

            # 3. Process results from backend
            captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            result: PahlenData = {
                "installation_id": self._installation_id,
                "captured_at": captured_at,
                "pushed_at": captured_at,
                "chlorine": analysis["chlorine"],
                "ph": analysis["ph"],
                "stale": False,
                "raw_response": None,
                "error": None,
            }

            _LOGGER.debug("Results received from backend and processed.")
            return result

        except Exception as exc:
            _LOGGER.exception("Error in producer update")
            raise UpdateFailed(f"Analysis failed: {exc}") from exc


class ConsumerCoordinator(DataUpdateCoordinator[PahlenData]):
    """Data coordinator for the consumer role."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        interval_minutes = entry.data[CONF_POLL_INTERVAL]
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_consumer_{entry.data[CONF_INSTALLATION_ID]}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._entry = entry
        self._backend_url = entry.data[CONF_BACKEND_URL].rstrip("/")
        self._installation_id = entry.data[CONF_INSTALLATION_ID]
        self._staleness_minutes = entry.data[CONF_STALENESS_THRESHOLD]

    async def _async_update_data(self) -> PahlenData:
        try:
            _LOGGER.debug("Polling backend for latest data: %s", self._backend_url)
            async with aiohttp.ClientSession() as session:
                token = self._entry.data.get(CONF_PUSH_TOKEN)
                headers = {"Authorization": f"Bearer {token}"} if token else {}

                async with session.get(
                    f"{self._backend_url}/latest/{self._installation_id}",
                    headers=headers,
                    timeout=10,
                ) as response:
                    if response.status == 404:
                        _LOGGER.info(
                            "No data found for installation %s", self._installation_id
                        )
                        return unknown_data()

                    if response.status != 200:
                        raise UpdateFailed(f"Backend returned status {response.status}")

                    remote_data = validate_latest_measurement(await response.json())
                    data: PahlenData = {
                        **remote_data,
                        "stale": compute_stale(
                            remote_data.get("captured_at"), self._staleness_minutes
                        ),
                        "error": None,
                    }
                    return data
        except Exception as exc:
            _LOGGER.exception("Error polling backend")
            if isinstance(exc, UpdateFailed):
                raise
            raise UpdateFailed(f"Failed to fetch data: {exc}") from exc
