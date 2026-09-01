from __future__ import annotations

import asyncio
import logging
import random
from time import monotonic
from typing import Any
from uuid import uuid4

import aiohttp

from .camera_payload import CameraPayload
from .contract_validation import LatestMeasurement, validate_latest_measurement

_LOGGER = logging.getLogger(__name__)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class SyncOrSwimApiError(Exception):
    """Raised when the SyncOrSwim backend returns an unexpected response."""


class SyncOrSwimApiNotFound(SyncOrSwimApiError):
    """Raised when the backend has no measurement for an installation."""


class SyncOrSwimApiClient:
    """Small Home Assistant-friendly aiohttp client for the backend API."""

    def __init__(
        self,
        backend_url: str,
        token: str | None,
        session: aiohttp.ClientSession,
        *,
        sensor_push_connect_timeout: float = 10,
        sensor_push_total_timeout: float = 30,
        sensor_push_attempts: int = 3,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._token = token
        self._session = session
        self._sensor_push_timeout = aiohttp.ClientTimeout(
            connect=sensor_push_connect_timeout,
            total=sensor_push_total_timeout,
        )
        self._sensor_push_attempts = sensor_push_attempts

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def get_latest(
        self, installation_id: str, staleness_threshold_minutes: int | None = None
    ) -> LatestMeasurement:
        params = (
            {"staleness_threshold_minutes": staleness_threshold_minutes}
            if staleness_threshold_minutes is not None
            else None
        )
        async with self._session.get(
            f"{self._backend_url}/api/latest/{installation_id}",
            headers=self._auth_headers(),
            params=params,
            timeout=10,
        ) as response:
            if response.status == 404:
                raise SyncOrSwimApiNotFound("No data found for installation")
            await self._raise_for_status(response, "Backend latest fetch failed")
            return validate_latest_measurement(await response.json())

    async def analyze_burst(
        self, installation_id: str, images: list[CameraPayload]
    ) -> LatestMeasurement:
        form_data = aiohttp.FormData()
        for index, image in enumerate(images):
            form_data.add_field(
                "files",
                image.content,
                filename=f"frame_{index}.jpg",
                content_type=image.content_type,
            )

        async with self._session.post(
            f"{self._backend_url}/api/analyze/{installation_id}/burst",
            data=form_data,
            headers=self._auth_headers(),
            timeout=60,
        ) as response:
            await self._raise_for_status(response, "Backend analysis failed")
            return validate_latest_measurement(await response.json())

    async def store_disabled_state(self, installation_id: str) -> LatestMeasurement:
        async with self._session.post(
            f"{self._backend_url}/api/installations/{installation_id}/disabled",
            headers=self._auth_headers(),
            timeout=10,
        ) as response:
            await self._raise_for_status(
                response, "Backend disabled-state update failed"
            )
            return validate_latest_measurement(await response.json())

    async def push_shared_sensors(
        self, installation_id: str, sensors: list[dict[str, Any]]
    ) -> None:
        entity_ids = [str(sensor.get("key", "")) for sensor in sensors]
        idempotency_key = str(uuid4())
        url = f"{self._backend_url}/api/installations/{installation_id}/sensors"

        for attempt in range(1, self._sensor_push_attempts + 1):
            started = monotonic()
            status_code: int | None = None
            failure_category: str | None = None
            try:
                headers = {
                    **self._auth_headers(),
                    "Idempotency-Key": idempotency_key,
                }
                async with self._session.post(
                    url,
                    json=sensors,
                    headers=headers,
                    timeout=self._sensor_push_timeout,
                ) as response:
                    status_code = response.status
                    if response.status in _RETRYABLE_STATUSES:
                        failure_category = "retryable_http"
                        if attempt < self._sensor_push_attempts:
                            await response.text()
                            self._log_sensor_push(
                                installation_id,
                                entity_ids,
                                attempt,
                                started,
                                status_code,
                                failure_category,
                            )
                            await self._retry_delay(attempt)
                            continue
                    await self._raise_for_status(response, "Backend sensor push failed")
                self._log_sensor_push(
                    installation_id,
                    entity_ids,
                    attempt,
                    started,
                    status_code,
                    "success",
                )
                return
            except (TimeoutError, aiohttp.ClientConnectionError) as exc:
                failure_category = (
                    "timeout" if isinstance(exc, TimeoutError) else "connection"
                )
                self._log_sensor_push(
                    installation_id,
                    entity_ids,
                    attempt,
                    started,
                    status_code,
                    failure_category,
                )
                if attempt >= self._sensor_push_attempts:
                    raise
                await self._retry_delay(attempt)
            except SyncOrSwimApiError:
                self._log_sensor_push(
                    installation_id,
                    entity_ids,
                    attempt,
                    started,
                    status_code,
                    failure_category or "permanent_http",
                )
                raise

    async def _retry_delay(self, attempt: int) -> None:
        """Wait using capped exponential backoff with jitter."""
        delay = min(8.0, 2 ** (attempt - 1) + random.uniform(0, 0.5))
        await asyncio.sleep(delay)

    def _log_sensor_push(
        self,
        installation_id: str,
        entity_ids: list[str],
        attempt: int,
        started: float,
        status_code: int | None,
        failure_category: str,
    ) -> None:
        _LOGGER.info(
            "Shared sensor push installation_id=%s sensor_entity_ids=%s "
            "duration_ms=%.1f attempt=%d status_code=%s failure_category=%s",
            installation_id,
            ",".join(entity_ids),
            (monotonic() - started) * 1000,
            attempt,
            status_code,
            failure_category,
        )

    async def _raise_for_status(
        self, response: aiohttp.ClientResponse, message: str
    ) -> None:
        if response.status == 200:
            return

        response_body = await response.text()
        raise SyncOrSwimApiError(f"{message}: {response.status} {response_body}")
