from __future__ import annotations

from typing import Any

import aiohttp

from .camera_payload import CameraPayload
from .contract_validation import LatestMeasurement, validate_latest_measurement


class PahlenApiError(Exception):
    """Raised when the Pahlen backend returns an unexpected response."""


class PahlenApiNotFound(PahlenApiError):
    """Raised when the backend has no measurement for an installation."""


class PahlenApiClient:
    """Small Home Assistant-friendly aiohttp client for the backend API."""

    def __init__(self, backend_url: str, token: str | None) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def get_latest(self, installation_id: str) -> LatestMeasurement:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._backend_url}/latest/{installation_id}",
                headers=self._auth_headers(),
                timeout=10,
            ) as response:
                if response.status == 404:
                    raise PahlenApiNotFound("No data found for installation")
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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._backend_url}/api/analyze/{installation_id}/burst",
                data=form_data,
                headers=self._auth_headers(),
                timeout=60,
            ) as response:
                await self._raise_for_status(response, "Backend analysis failed")
                return validate_latest_measurement(await response.json())

    async def store_disabled_state(self, installation_id: str) -> LatestMeasurement:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._backend_url}/installations/{installation_id}/disabled",
                headers=self._auth_headers(),
                timeout=10,
            ) as response:
                await self._raise_for_status(
                    response, "Backend disabled-state update failed"
                )
                return validate_latest_measurement(await response.json())

    async def _raise_for_status(self, response: Any, message: str) -> None:
        if response.status == 200:
            return

        response_body = await response.text()
        raise PahlenApiError(f"{message}: {response.status} {response_body}")
