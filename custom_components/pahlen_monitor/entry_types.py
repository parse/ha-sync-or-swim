from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import PahlenCoordinator


class PahlenConfigEntryData(TypedDict):
    role: str
    installation_id: str
    backend_url: str
    push_token: str
    camera_entity: NotRequired[str]
    light_entity: NotRequired[str]
    scan_interval: NotRequired[int]
    poll_interval: NotRequired[int]
    staleness_threshold: NotRequired[int]


class PahlenConfigEntryOptions(TypedDict, total=False):
    installation_enabled: bool


class PahlenConfigEntry(ConfigEntry):
    data: PahlenConfigEntryData
    options: PahlenConfigEntryOptions
    runtime_data: PahlenCoordinator | None


def require_runtime_coordinator(entry: PahlenConfigEntry) -> PahlenCoordinator:
    coordinator = entry.runtime_data
    if coordinator is None:
        raise RuntimeError("Pahlen coordinator has not been initialized")
    return coordinator
