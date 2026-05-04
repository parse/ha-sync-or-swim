from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import SyncOrSwimCoordinator


class SyncOrSwimConfigEntryData(TypedDict):
    role: str
    installation_id: str
    backend_url: str
    push_token: str
    camera_entity: NotRequired[str]
    light_entity: NotRequired[str]
    scan_interval: NotRequired[int]
    poll_interval: NotRequired[int]
    staleness_threshold: NotRequired[int]


class SyncOrSwimConfigEntryOptions(TypedDict, total=False):
    installation_enabled: bool


class SyncOrSwimConfigEntry(ConfigEntry):
    data: SyncOrSwimConfigEntryData
    options: SyncOrSwimConfigEntryOptions
    runtime_data: SyncOrSwimCoordinator | None


def require_runtime_coordinator(entry: SyncOrSwimConfigEntry) -> SyncOrSwimCoordinator:
    coordinator = entry.runtime_data
    if coordinator is None:
        raise RuntimeError("SyncOrSwim coordinator has not been initialized")
    return coordinator
