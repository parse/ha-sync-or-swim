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
        "homeassistant.helpers.event": types.ModuleType("homeassistant.helpers.event"),
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

        def _abort_if_unique_id_mismatch(self):
            return None

        def _get_reconfigure_entry(self):
            return self._reconfigure_entry

        def async_update_reload_and_abort(self, entry, data_updates):
            updated = dict(entry.data)
            updated.update(data_updates)
            entry.data = updated
            return {"type": "abort", "reason": "reconfigure_successful"}

    class StubOptionsFlowWithReload:
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    class StubEntitySelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class StubEntitySelector:
        def __init__(self, config):
            self.config = config

    class StubTextSelectorConfig(StubEntitySelectorConfig):
        pass

    class StubTextSelector(StubEntitySelector):
        pass

    class StubConfigEntry:
        pass

    class StubCameraImage:
        content = b""
        content_type = "image/jpeg"

    class StubSensorDeviceClass:
        TIMESTAMP = "timestamp"

    class StubDataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

        def async_set_updated_data(self, data):
            self.data = data

    class StubCoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    modules["aiohttp"].ClientSession = object
    modules["aiohttp"].FormData = object
    modules["homeassistant.components.camera"].async_get_image = AsyncMock(
        return_value=StubCameraImage()
    )
    modules["homeassistant.components.sensor"].SensorEntity = object
    modules["homeassistant.components.sensor"].SensorDeviceClass = StubSensorDeviceClass
    modules["homeassistant.components.binary_sensor"].BinarySensorEntity = object
    modules[
        "homeassistant.components.binary_sensor"
    ].BinarySensorDeviceClass = SimpleNamespace(PROBLEM="problem")
    modules["homeassistant.components.switch"].SwitchEntity = object
    modules["homeassistant.components.button"].ButtonEntity = object
    modules["homeassistant.config_entries"].ConfigEntry = StubConfigEntry
    modules["homeassistant.config_entries"].ConfigFlow = StubConfigFlow
    modules["homeassistant.config_entries"].OptionsFlow = StubOptionsFlowWithReload
    modules[
        "homeassistant.config_entries"
    ].OptionsFlowWithReload = StubOptionsFlowWithReload
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.core"].callback = lambda func: func
    modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = (
        lambda hass: None
    )
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
    modules["homeassistant.helpers.selector"].EntitySelector = StubEntitySelector
    modules[
        "homeassistant.helpers.selector"
    ].EntitySelectorConfig = StubEntitySelectorConfig
    modules["homeassistant.helpers.selector"].TextSelector = StubTextSelector
    modules[
        "homeassistant.helpers.selector"
    ].TextSelectorConfig = StubTextSelectorConfig
    modules["homeassistant.helpers.event"].async_track_time_interval = (
        lambda hass, action, interval: lambda: None
    )
    modules[
        "homeassistant.helpers.update_coordinator"
    ].CoordinatorEntity = StubCoordinatorEntity
    modules[
        "homeassistant.helpers.update_coordinator"
    ].DataUpdateCoordinator = StubDataUpdateCoordinator
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception
    modules["voluptuous"].Schema = lambda value: value
    modules["voluptuous"].Required = lambda value, default=None: (
        "required",
        value,
        repr(default),
    )
    modules["voluptuous"].Optional = lambda value, default=None: (
        "optional",
        value,
        repr(default),
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
async def test_migrate_entry_moves_runtime_settings_to_options():
    integration = load_module("__init__")
    updates = {}
    entry = SimpleNamespace(
        version=1,
        data={
            "role": "producer",
            "installation_id": "pool-1",
            "backend_url": "http://backend",
            "push_token": "token",
            "camera_entity": "camera.pool",
            "light_entity": "light.pool",
            "scan_interval": 45,
            "staleness_threshold": 120,
            "shared_sensors": ["sensor.pool"],
        },
        options={},
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda entry, **kwargs: updates.update(kwargs)
        )
    )

    assert await integration.async_migrate_entry(hass, entry) is True

    assert updates["version"] == 2
    assert updates["data"] == {
        "role": "producer",
        "installation_id": "pool-1",
        "backend_url": "http://backend",
        "push_token": "token",
        "camera_entity": "camera.pool",
    }
    assert updates["options"]["scan_interval"] == 45
    assert updates["options"]["staleness_threshold"] == 120
    assert updates["options"]["shared_sensors"] == ["sensor.pool"]
    assert updates["options"]["installation_enabled"] is True


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


def test_shared_sensor_update_from_state_skips_unavailable_values():
    coordinator = load_module("coordinator")
    unavailable_state = SimpleNamespace(
        state="unavailable",
        attributes={
            "friendly_name": "Temperature",
            "unit_of_measurement": "C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    )

    assert (
        coordinator.shared_sensor_update_from_state(
            "sensor.temp_sensor_cellar_temperature", unavailable_state
        )
        is None
    )
    assert (
        coordinator.shared_sensor_update_from_state(
            "sensor.temp_sensor_cellar_temperature", None
        )
        is None
    )


def test_shared_sensor_update_from_state_preserves_available_values():
    coordinator = load_module("coordinator")
    state = SimpleNamespace(
        state="12.3",
        attributes={
            "friendly_name": "Temperature",
            "unit_of_measurement": "C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    )

    assert coordinator.shared_sensor_update_from_state(
        "sensor.temp_sensor_cellar_temperature", state
    ) == {
        "key": "sensor.temp_sensor_cellar_temperature",
        "label": "Temperature",
        "value": "12.3",
        "unit": "C",
        "device_class": "temperature",
        "state_class": "measurement",
    }


def test_effective_entry_value_prefers_options_over_data():
    config_helpers = load_module("config_helpers")
    entry = SimpleNamespace(
        data={"scan_interval": 60, "shared_sensors": ["sensor.old"]},
        options={"scan_interval": 15, "shared_sensors": ["sensor.new"]},
    )

    assert config_helpers.effective_entry_value(entry, "scan_interval", 30) == 15
    assert config_helpers.effective_shared_sensors(entry) == ["sensor.new"]


def test_shared_sensor_interval_parser_rejects_invalid_lines():
    config_helpers = load_module("config_helpers")

    with pytest.raises(ValueError):
        config_helpers.parse_shared_sensor_intervals("sensor.pool_temperature")

    with pytest.raises(ValueError):
        config_helpers.parse_shared_sensor_intervals("sensor.pool_temperature=0")


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
    assert "scan_interval" not in created["data"]
    assert created["options"]["scan_interval"] == 45
    assert created["options"]["installation_enabled"] is True
    assert created["unique_id"] == "pool-1"
    assert created["aborted"] is True
    backend.assert_awaited_once_with("http://backend")


@pytest.mark.asyncio
async def test_reconfigure_updates_existing_entry_without_installation_id(monkeypatch):
    config_flow = load_module("config_flow")
    flow = make_flow(config_flow)
    flow._reconfigure_entry = SimpleNamespace(
        data={
            "role": "producer",
            "installation_id": "pool-1",
            "camera_entity": "camera.pool",
            "push_token": "old-token",
            "backend_url": "http://old-backend",
        },
        options={},
    )
    backend = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, "_test_backend_url", backend)

    result = await flow.async_step_reconfigure(
        {
            "camera_entity": "camera.pool",
            "push_token": "new-token",
            "backend_url": "http://new-backend",
        }
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    assert flow._reconfigure_entry.data["installation_id"] == "pool-1"
    assert flow._reconfigure_entry.data["backend_url"] == "http://new-backend"
    assert flow._reconfigure_entry.data["push_token"] == "new-token"
    backend.assert_awaited_once_with("http://new-backend")


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
    assert "poll_interval" not in result["data"]
    assert result["options"]["poll_interval"] == 15
    backend.assert_awaited_once_with("http://backend")


@pytest.mark.asyncio
async def test_options_flow_rejects_invalid_shared_sensor_intervals():
    config_flow = load_module("config_flow")
    entry = SimpleNamespace(
        data={"role": "producer", "scan_interval": 60, "staleness_threshold": 120},
        options={},
    )
    options_flow = config_flow.SyncOrSwimOptionsFlowHandler(entry)

    result = await options_flow.async_step_init(
        {
            "scan_interval": 30,
            "staleness_threshold": 120,
            "installation_enabled": True,
            "shared_sensors": ["sensor.pool"],
            "shared_sensor_intervals": "sensor.pool=soon",
        }
    )

    assert result["type"] == "form"
    assert result["errors"] == {
        "shared_sensor_intervals": "invalid_shared_sensor_intervals"
    }


@pytest.mark.asyncio
async def test_options_flow_consumer_stores_poll_interval():
    config_flow = load_module("config_flow")
    entry = SimpleNamespace(
        data={"role": "consumer", "poll_interval": 30, "staleness_threshold": 120},
        options={},
    )
    options_flow = config_flow.SyncOrSwimOptionsFlowHandler(entry)

    result = await options_flow.async_step_init(
        {"poll_interval": 5, "staleness_threshold": 90}
    )

    assert result == {
        "type": "create_entry",
        "data": {"poll_interval": 5, "staleness_threshold": 90},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_name", "user_input", "expected_step"),
    [
        (
            "async_step_producer",
            {
                "installation_id": "Bad_Installation",
                "camera_entity": "camera.pool",
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


def producer_entry(**overrides):
    data = {
        "role": "producer",
        "installation_id": "pool-1",
        "camera_entity": "camera.pool",
        "push_token": "token",
        "backend_url": "http://backend",
        "scan_interval": 60,
        "staleness_threshold": 120,
    }
    data.update(overrides.pop("data", {}))
    return SimpleNamespace(
        data=data,
        options=overrides.pop("options", {}),
        async_on_unload=overrides.pop("async_on_unload", lambda callback: None),
    )


class FakeApiClient:
    def __init__(self, backend_url, token, session):
        self.backend_url = backend_url
        self.token = token
        self.session = session
        self.shared_sensor_calls = []
        self.analyze_calls = []

    async def analyze_burst(self, installation_id, images):
        self.analyze_calls.append((installation_id, images))
        return {
            "installation_id": installation_id,
            "captured_at": "2026-04-28T18:16:36Z",
            "pushed_at": None,
            "raw_response": None,
            "pool": {
                "chlorine": {"status": "ok"},
                "ph": {"status": "ok"},
            },
            "sensors": [],
        }

    async def push_shared_sensors(self, installation_id, sensors):
        self.shared_sensor_calls.append((installation_id, sensors))


def make_hass(states=None):
    def fake_create_task(coro):
        coro.close()
        return SimpleNamespace(cancel=lambda: None)

    return SimpleNamespace(
        states=states or {},
        async_create_task=fake_create_task,
        config_entries=SimpleNamespace(async_update_entry=lambda *args, **kwargs: None),
    )


def install_fake_api(monkeypatch, coordinator):
    clients = []

    def fake_client(*args):
        client = FakeApiClient(*args)
        clients.append(client)
        return client

    monkeypatch.setattr(coordinator, "SyncOrSwimApiClient", fake_client)
    return clients


def test_producer_shared_sensor_timers_register_configured_intervals(monkeypatch):
    coordinator = load_module("coordinator")
    clients = install_fake_api(monkeypatch, coordinator)
    timers = []
    cleanups = []

    def fake_track_time_interval(hass, action, interval):
        timers.append((action, interval))
        return lambda: None

    monkeypatch.setattr(
        coordinator, "async_track_time_interval", fake_track_time_interval
    )
    entry = producer_entry(
        data={"shared_sensors": ["sensor.pool", "sensor.air"]},
        options={"shared_sensor_intervals": "sensor.pool=7"},
        async_on_unload=cleanups.append,
    )

    producer = coordinator.ProducerCoordinator(make_hass(), entry)

    assert producer.update_interval.total_seconds() == 60 * 60
    assert clients[0].backend_url == "http://backend"
    assert [timer[1].total_seconds() for timer in timers] == [7 * 60, 15 * 60]
    assert len(cleanups) == 4


@pytest.mark.asyncio
async def test_shared_sensor_push_sends_available_value_and_skips_unavailable(
    monkeypatch,
):
    coordinator = load_module("coordinator")
    clients = install_fake_api(monkeypatch, coordinator)
    entry = producer_entry()
    hass = make_hass(
        {
            "sensor.pool": SimpleNamespace(
                state="12.3",
                attributes={"friendly_name": "Pool temperature"},
            ),
            "sensor.offline": SimpleNamespace(state="unavailable", attributes={}),
        }
    )
    producer = coordinator.ProducerCoordinator(hass, entry)

    await producer._async_push_shared_sensor("sensor.pool")
    await producer._async_push_shared_sensor("sensor.offline")

    assert clients[0].shared_sensor_calls == [
        (
            "pool-1",
            [
                {
                    "key": "sensor.pool",
                    "label": "Pool temperature",
                    "value": "12.3",
                    "unit": None,
                    "device_class": None,
                    "state_class": None,
                }
            ],
        )
    ]


@pytest.mark.asyncio
async def test_producer_analysis_no_longer_pushes_shared_sensors(monkeypatch):
    coordinator = load_module("coordinator")
    clients = install_fake_api(monkeypatch, coordinator)
    entry = producer_entry(data={"shared_sensors": ["sensor.pool"]})
    hass = make_hass(
        {
            "sensor.pool": SimpleNamespace(
                state="12.3",
                attributes={"friendly_name": "Pool temperature"},
            )
        }
    )
    monkeypatch.setattr(
        coordinator.camera,
        "async_get_image",
        AsyncMock(
            return_value=SimpleNamespace(content=b"image", content_type="image/jpeg")
        ),
    )

    producer = coordinator.ProducerCoordinator(hass, entry)
    await producer._async_update_data()

    assert len(clients[0].analyze_calls) == 1
    assert clients[0].shared_sensor_calls == []


@pytest.mark.asyncio
async def test_producer_update_keeps_existing_data_on_analysis_error(monkeypatch):
    coordinator = load_module("coordinator")
    install_fake_api(monkeypatch, coordinator)
    entry = producer_entry()
    producer = coordinator.ProducerCoordinator(make_hass(), entry)
    existing_data = coordinator.unknown_data()
    existing_data.update(
        {
            "installation_id": "pool-1",
            "captured_at": "2099-01-01T00:00:00Z",
        }
    )
    producer.data = existing_data
    producer._api_client.analyze_burst = AsyncMock(side_effect=RuntimeError("boom"))

    result = await producer._async_update_data()

    assert result["installation_id"] == "pool-1"
    assert result["captured_at"] == "2099-01-01T00:00:00Z"
    assert result["error"] == "boom"
    assert result["pool"] == existing_data["pool"]


@pytest.mark.asyncio
async def test_producer_update_raises_when_no_existing_data(monkeypatch):
    coordinator = load_module("coordinator")
    install_fake_api(monkeypatch, coordinator)
    entry = producer_entry()
    producer = coordinator.ProducerCoordinator(make_hass(), entry)
    producer._api_client.analyze_burst = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(Exception, match="Analysis failed: boom"):
        await producer._async_update_data()


def test_consumer_poll_interval_prefers_options(monkeypatch):
    coordinator = load_module("coordinator")
    install_fake_api(monkeypatch, coordinator)
    entry = SimpleNamespace(
        data={
            "role": "consumer",
            "installation_id": "pool-1",
            "push_token": "token",
            "backend_url": "http://backend",
            "poll_interval": 30,
            "staleness_threshold": 120,
        },
        options={"poll_interval": 5},
    )

    consumer = coordinator.ConsumerCoordinator(make_hass(), entry)

    assert consumer.update_interval.total_seconds() == 5 * 60
