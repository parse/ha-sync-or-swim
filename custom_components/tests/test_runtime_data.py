import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PACKAGE_PATH = Path(__file__).resolve().parents[1] / "sync_or_swim"


class DuplicateEntryConfigured(Exception):
    pass


def stub_modules():
    modules = {
        "aiohttp": types.ModuleType("aiohttp"),
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.components": types.ModuleType("homeassistant.components"),
        "homeassistant.components.camera": types.ModuleType(
            "homeassistant.components.camera"
        ),
        "homeassistant.components.sensor": types.ModuleType(
            "homeassistant.components.sensor"
        ),
        "homeassistant.components.binary_sensor": types.ModuleType(
            "homeassistant.components.binary_sensor"
        ),
        "homeassistant.components.switch": types.ModuleType(
            "homeassistant.components.switch"
        ),
        "homeassistant.components.button": types.ModuleType(
            "homeassistant.components.button"
        ),
        "homeassistant.config_entries": types.ModuleType(
            "homeassistant.config_entries"
        ),
        "homeassistant.core": types.ModuleType("homeassistant.core"),
        "homeassistant.helpers": types.ModuleType("homeassistant.helpers"),
        "homeassistant.helpers.aiohttp_client": types.ModuleType(
            "homeassistant.helpers.aiohttp_client"
        ),
        "homeassistant.helpers.entity_platform": types.ModuleType(
            "homeassistant.helpers.entity_platform"
        ),
        "homeassistant.helpers.selector": types.ModuleType(
            "homeassistant.helpers.selector"
        ),
        "homeassistant.helpers.update_coordinator": types.ModuleType(
            "homeassistant.helpers.update_coordinator"
        ),
        "voluptuous": types.ModuleType("voluptuous"),
    }

    class StubConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        async def async_set_unique_id(self, unique_id):
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            if getattr(self, "_duplicate_configured", False):
                raise DuplicateEntryConfigured

    class StubEntitySelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class StubEntitySelector:
        def __init__(self, config):
            self.config = config

    class StubConfigEntry:
        pass

    class StubCameraImage:
        content = b""
        content_type = "image/jpeg"

    class StubDataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        pass

    class StubCoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    modules["aiohttp"].ClientSession = object
    modules["aiohttp"].FormData = object
    modules["homeassistant.components.camera"].async_get_image = AsyncMock(
        return_value=StubCameraImage()
    )
    modules["homeassistant.components.sensor"].SensorEntity = object
    modules["homeassistant.components.binary_sensor"].BinarySensorEntity = object
    modules[
        "homeassistant.components.binary_sensor"
    ].BinarySensorDeviceClass = SimpleNamespace(PROBLEM="problem")
    modules["homeassistant.components.switch"].SwitchEntity = object
    modules["homeassistant.components.button"].ButtonEntity = object
    modules["homeassistant.config_entries"].ConfigEntry = StubConfigEntry
    modules["homeassistant.config_entries"].ConfigFlow = StubConfigFlow
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = (
        lambda hass: None
    )
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
    modules["homeassistant.helpers.selector"].EntitySelector = StubEntitySelector
    modules[
        "homeassistant.helpers.selector"
    ].EntitySelectorConfig = StubEntitySelectorConfig
    modules[
        "homeassistant.helpers.update_coordinator"
    ].CoordinatorEntity = StubCoordinatorEntity
    modules[
        "homeassistant.helpers.update_coordinator"
    ].DataUpdateCoordinator = StubDataUpdateCoordinator
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception
    modules["voluptuous"].Schema = lambda value: value
    modules["voluptuous"].Required = lambda value: ("required", value)
    modules["voluptuous"].Optional = lambda value, default=None: (
        "optional",
        value,
        default,
    )
    modules["voluptuous"].In = lambda value: ("in", tuple(value))

    sys.modules.update(modules)


def load_module(module_name):
    stub_modules()
    package = types.ModuleType("custom_components.sync_or_swim")
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules["custom_components.sync_or_swim"] = package
    sys.modules.pop(f"custom_components.sync_or_swim.{module_name}", None)
    return importlib.import_module(f"custom_components.sync_or_swim.{module_name}")


def make_flow(config_flow):
    flow = config_flow.SyncOrSwimMonitorConfigFlow()
    flow.hass = SimpleNamespace(
        states={
            "camera.pool": object(),
            "light.pool": object(),
        }
    )
    return flow


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "coordinator_cls"),
    [
        ("producer", "ProducerCoordinator"),
        ("consumer", "ConsumerCoordinator"),
    ],
)
async def test_async_setup_entry_uses_runtime_data_and_unload_clears_it(
    monkeypatch, role, coordinator_cls
):
    integration = load_module("__init__")

    class FakeProducerCoordinator:
        def __init__(self, hass, entry):
            self.hass = hass
            self.entry = entry
            self.async_config_entry_first_refresh = AsyncMock()

    class FakeConsumerCoordinator(FakeProducerCoordinator):
        pass

    monkeypatch.setattr(integration, "ProducerCoordinator", FakeProducerCoordinator)
    monkeypatch.setattr(integration, "ConsumerCoordinator", FakeConsumerCoordinator)

    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Pool",
        data={"role": role},
        options={},
        runtime_data=None,
    )
    hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(),
            async_unload_platforms=AsyncMock(return_value=True),
        ),
    )

    assert await integration.async_setup_entry(hass, entry) is True

    expected_cls = (
        FakeProducerCoordinator
        if coordinator_cls == "ProducerCoordinator"
        else FakeConsumerCoordinator
    )
    assert isinstance(entry.runtime_data, expected_cls)
    entry.runtime_data.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, integration.PLATFORMS
    )
    assert hass.data == {}

    assert await integration.async_unload_entry(hass, entry) is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, integration.PLATFORMS
    )
    assert entry.runtime_data is None


@pytest.mark.asyncio
async def test_config_flow_user_routes_to_role_specific_step(monkeypatch):
    config_flow = load_module("config_flow")
    flow = config_flow.SyncOrSwimMonitorConfigFlow()
    producer = AsyncMock(return_value="producer-step")
    consumer = AsyncMock(return_value="consumer-step")
    monkeypatch.setattr(flow, "async_step_producer", producer)
    monkeypatch.setattr(flow, "async_step_consumer", consumer)

    result = await flow.async_step_user({"role": "consumer"})

    assert result == "consumer-step"
    consumer.assert_awaited_once()
    producer.assert_not_awaited()


@pytest.mark.asyncio
async def test_config_flow_producer_creates_entry(monkeypatch):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)

    backend = AsyncMock(return_value=True)
    created = {}

    async def fake_set_unique_id(value):
        created["unique_id"] = value

    def fake_abort():
        created["aborted"] = True

    def fake_create_entry(**kwargs):
        created.update(kwargs)
        return {"type": "create_entry", **kwargs}

    monkeypatch.setattr(flow, "async_set_unique_id", fake_set_unique_id)
    monkeypatch.setattr(flow, "_abort_if_unique_id_configured", fake_abort)
    monkeypatch.setattr(flow, "_test_backend_url", backend)
    monkeypatch.setattr(flow, "async_create_entry", fake_create_entry)

    result = await flow.async_step_producer(
        {
            "installation_id": "pool-1",
            "camera_entity": "camera.pool",
            "light_entity": "light.pool",
            "push_token": "token",
            "backend_url": "http://backend",
            "scan_interval": 45,
            "staleness_threshold": 120,
        }
    )

    assert result["type"] == "create_entry"
    assert created["title"] == "pool-1"
    assert created["data"]["installation_id"] == "pool-1"
    assert created["data"]["camera_entity"] == "camera.pool"
    assert created["data"]["scan_interval"] == 45
    assert created["unique_id"] == "pool-1"
    assert created["aborted"] is True
    backend.assert_awaited_once_with("http://backend")


@pytest.mark.asyncio
async def test_config_flow_consumer_creates_entry(monkeypatch):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)
    backend = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, "_test_backend_url", backend)

    result = await flow.async_step_consumer(
        {
            "installation_id": "pool-1",
            "push_token": "token",
            "backend_url": "http://backend",
            "poll_interval": 15,
            "staleness_threshold": 90,
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "pool-1"
    assert result["data"]["installation_id"] == "pool-1"
    assert result["data"]["poll_interval"] == 15
    backend.assert_awaited_once_with("http://backend")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_name", "user_input", "expected_step"),
    [
        (
            "async_step_producer",
            {
                "installation_id": "Bad_Installation",
                "camera_entity": "camera.pool",
                "light_entity": "light.pool",
                "push_token": "token",
                "backend_url": "http://backend",
                "scan_interval": 45,
                "staleness_threshold": 120,
            },
            "producer",
        ),
        (
            "async_step_consumer",
            {
                "installation_id": "Bad_Installation",
                "push_token": "token",
                "backend_url": "http://backend",
                "poll_interval": 15,
                "staleness_threshold": 90,
            },
            "consumer",
        ),
    ],
)
async def test_config_flow_rejects_invalid_installation_id(
    monkeypatch, step_name, user_input, expected_step
):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)
    backend = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, "_test_backend_url", backend)

    result = await getattr(flow, step_name)(user_input)

    assert result["type"] == "form"
    assert result["step_id"] == expected_step
    assert result["errors"] == {"installation_id": "invalid_installation_id"}
    backend.assert_not_awaited()


@pytest.mark.asyncio
async def test_config_flow_reports_backend_connection_failure(monkeypatch):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)
    backend = AsyncMock(return_value=False)
    monkeypatch.setattr(flow, "_test_backend_url", backend)

    result = await flow.async_step_consumer(
        {
            "installation_id": "pool-1",
            "push_token": "token",
            "backend_url": "http://backend",
            "poll_interval": 15,
            "staleness_threshold": 90,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "consumer"
    assert result["errors"] == {"base": "cannot_connect"}
    backend.assert_awaited_once_with("http://backend")


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "expected"), [(200, True), (500, False)])
async def test_config_flow_backend_check_uses_shared_session(
    monkeypatch, status, expected
):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)

    class FakeResponse:
        def __init__(self, response_status):
            self.status = response_status

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse(status)

    session = FakeSession()
    monkeypatch.setattr(
        config_flow,
        "async_get_clientsession",
        lambda hass: session,
    )

    assert await flow._test_backend_url("http://backend/") is expected
    assert session.calls == [("http://backend/api/health", {"timeout": 10})]


@pytest.mark.asyncio
async def test_config_flow_aborts_duplicate_installation():
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)
    flow._duplicate_configured = True

    with pytest.raises(DuplicateEntryConfigured):
        await flow.async_step_consumer(
            {
                "installation_id": "pool-1",
                "push_token": "token",
                "backend_url": "http://backend",
                "poll_interval": 15,
                "staleness_threshold": 90,
            }
        )
