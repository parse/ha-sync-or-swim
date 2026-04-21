import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analyzer import PahlenAnalyzer
from .const import (
    CONF_BACKEND_URL,
    CONF_INSTALLATION_ID,
    CONF_POLL_INTERVAL,
    CONF_PUSH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_STALENESS_THRESHOLD,
    DOMAIN,
    STATUS_UNKNOWN,
)


class UnitAnalysis(TypedDict):
    """Analysis data for a single unit."""

    status: str
    diagnosis: str | None
    pattern_detected: str | None
    blinking_leds: list[str]
    solid_leds: list[str]
    summary: str
    action_required: bool
    recommended_action: str


class PahlenData(TypedDict):
    """The root data structure for the integration."""

    installation_id: str | None
    captured_at: str | None
    pushed_at: str | None
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    stale: bool
    raw_response: str | None
    error: str | None


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
        "installation_id": None,
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
        interval_minutes = entry.data[CONF_SCAN_INTERVAL]
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_producer_{entry.data[CONF_INSTALLATION_ID]}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._entry = entry
        self._analyzer = PahlenAnalyzer(hass, entry.data)
        self._backend_url = entry.data[CONF_BACKEND_URL].rstrip("/")
        self._installation_id = entry.data[CONF_INSTALLATION_ID]
        self._staleness_minutes = entry.data[CONF_STALENESS_THRESHOLD]

    async def _async_update_data(self) -> PahlenData:
        try:
            _LOGGER.debug("Starting producer analysis")
            result = await self._analyzer.analyze()
            result["captured_at"] = datetime.now(tz=timezone.utc).isoformat()
            result["stale"] = False
            result["installation_id"] = self._installation_id
            result["pushed_at"] = result["captured_at"]
            result["raw_response"] = result.get("raw_response")
            result["error"] = None

            _LOGGER.debug("Pushing results to backend: %s", self._backend_url)
            async with aiohttp.ClientSession() as session:
                payload = {
                    "captured_at": result["captured_at"],
                    "chlorine": result["chlorine"],
                    "ph": result["ph"],
                }
                token = self._entry.data.get(CONF_PUSH_TOKEN)
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                async with session.post(
                    f"{self._backend_url}/push/{self._installation_id}",
                    json=payload,
                    headers=headers,
                    timeout=30,
                ) as response:
                    if response.status not in (200, 201):
                        _LOGGER.error("Failed to push to backend: %s", response.status)

            # Ensure we return PahlenData
            return result  # type: ignore

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
        self._backend_url = entry.data[CONF_BACKEND_URL].rstrip("/")
        self._installation_id = entry.data[CONF_INSTALLATION_ID]
        self._staleness_minutes = entry.data[CONF_STALENESS_THRESHOLD]

    async def _async_update_data(self) -> PahlenData:
        try:
            _LOGGER.debug("Polling backend for latest data: %s", self._backend_url)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._backend_url}/latest/{self._installation_id}", timeout=10
                ) as response:
                    if response.status == 404:
                        _LOGGER.info(
                            "No data found for installation %s", self._installation_id
                        )
                        return unknown_data()

                    if response.status != 200:
                        raise UpdateFailed(f"Backend returned status {response.status}")

                    data: PahlenData = await response.json()
                    data["stale"] = compute_stale(
                        data.get("captured_at"), self._staleness_minutes
                    )
                    data["error"] = None
                    return data
        except Exception as exc:
            _LOGGER.exception("Error polling backend")
            if isinstance(exc, UpdateFailed):
                raise
            raise UpdateFailed(f"Failed to fetch data: {exc}") from exc
