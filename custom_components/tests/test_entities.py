import importlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PACKAGE_PATH = Path(__file__).resolve().parents[1] / "sync_or_swim"


class StubCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class StubBinarySensorDeviceClass:
    PROBLEM = "problem"


class StubSensorDeviceClass:
    ENUM = "enum"
    TIMESTAMP = "timestamp"


def stub_homeassistant_modules():
    modules = {
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.components": types.ModuleType("homeassistant.components"),
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
        "homeassistant.helpers.entity_platform": types.ModuleType(
            "homeassistant.helpers.entity_platform"
        ),
        "homeassistant.helpers.update_coordinator": types.ModuleType(
            "homeassistant.helpers.update_coordinator"
        ),
    }
    modules["homeassistant.components.sensor"].SensorEntity = object
    modules["homeassistant.components.sensor"].SensorDeviceClass = StubSensorDeviceClass
    modules["homeassistant.components.binary_sensor"].BinarySensorEntity = object
    modules[
        "homeassistant.components.binary_sensor"
    ].BinarySensorDeviceClass = StubBinarySensorDeviceClass
    modules["homeassistant.components.switch"].SwitchEntity = object
    modules["homeassistant.components.button"].ButtonEntity = object
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
    modules[
        "homeassistant.helpers.update_coordinator"
    ].CoordinatorEntity = StubCoordinatorEntity

    sys.modules.update(modules)


def load_module(module_name):
    stub_homeassistant_modules()
    package = types.ModuleType("custom_components.sync_or_swim")
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules["custom_components.sync_or_swim"] = package
    sys.modules.pop(f"custom_components.sync_or_swim.{module_name}", None)
    return importlib.import_module(f"custom_components.sync_or_swim.{module_name}")


def coordinator_data(**overrides):
    data = {
        "captured_at": "2026-04-28T18:16:36Z",
        "installation_enabled": True,
        "stale": False,
        "error": None,
        "pool": {
            "chlorine": {
                "status": "warning",
                "diagnosis": "Low chlorine",
                "pattern_detected": "manual",
                "blinking_leds": ["LED 2"],
                "solid_leds": ["LED 1", "LED 4"],
                "summary": "Chlorine needs attention",
                "action_required": True,
                "recommended_action": "Check chlorine dosing",
            },
            "ph": {
                "status": "ok",
                "diagnosis": None,
                "pattern_detected": "auto",
                "blinking_leds": [],
                "solid_leds": ["LED 4"],
                "summary": "pH is OK",
                "action_required": False,
                "recommended_action": "",
            },
        },
        "sensors": [],
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_sensor_setup_creates_sync_or_swim_detail_entities_without_action_sensors():
    sensor = load_module("sensor")
    entry = SimpleNamespace(
        entry_id="entry-1",
        runtime_data=SimpleNamespace(),
        async_on_unload=lambda callback: None,
    )
    coordinator = SimpleNamespace(
        data=coordinator_data(),
        async_add_listener=lambda callback: None,
    )
    entry.runtime_data = coordinator
    hass = SimpleNamespace(data={})
    entities = []

    await sensor.async_setup_entry(hass, entry, entities.extend)

    names = [entity._attr_name for entity in entities]
    assert names == [
        "SyncOrSwim Dosing Problem",
        "SyncOrSwim Last Calibration Read",
        "SyncOrSwim Free Chlorine Status",
        "SyncOrSwim Free Chlorine Summary",
        "SyncOrSwim Free Chlorine Diagnosis",
        "SyncOrSwim Free Chlorine Recommended Action",
        "SyncOrSwim Free Chlorine LEDs",
        "SyncOrSwim pH Status",
        "SyncOrSwim pH Summary",
        "SyncOrSwim pH Diagnosis",
        "SyncOrSwim pH Recommended Action",
        "SyncOrSwim pH LEDs",
    ]
    assert all("Dosing Action" not in name for name in names)


def test_last_calibration_read_sensor_exposes_backend_capture_timestamp():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            installation_id="pool",
            captured_at="2026-04-28T18:16:36Z",
            pushed_at="2026-04-28T18:17:00Z",
        )
    )
    entry.runtime_data = coordinator

    last_read = sensor.SyncOrSwimLastCalibrationReadSensor(coordinator, entry)

    assert last_read._attr_device_class == "timestamp"
    assert last_read.native_value == datetime(
        2026, 4, 28, 18, 16, 36, tzinfo=timezone.utc
    )
    assert last_read.extra_state_attributes == {
        "captured_at": "2026-04-28T18:16:36Z",
        "pushed_at": "2026-04-28T18:17:00Z",
        "stale": False,
        "installation_id": "pool",
    }


def test_detail_sensors_expose_backend_analysis_fields():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(data=coordinator_data())
    entry.runtime_data = coordinator

    summary = sensor.SyncOrSwimDetailSensor(
        coordinator, entry, "chlorine", "Free Chlorine", "summary"
    )
    recommended_action = sensor.SyncOrSwimDetailSensor(
        coordinator, entry, "ph", "pH", "recommended_action"
    )

    assert summary.native_value == "Chlorine needs attention"
    assert summary.extra_state_attributes["action_required"] is True
    assert recommended_action.native_value == "none"
    assert recommended_action.extra_state_attributes["summary"] == "pH is OK"


@pytest.mark.parametrize(
    ("solid_leds", "blinking_leds", "expected"),
    [
        (["LED 1", "LED 4"], ["LED 2"], "Solid: LED 1, LED 4; Blinking: LED 2"),
        ([], ["LED 3"], "Blinking: LED 3"),
        ([], [], "none"),
        (None, None, "none"),
    ],
)
def test_led_sensor_formats_solid_and_blinking_leds(
    solid_leds, blinking_leds, expected
):
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    data = coordinator_data()
    data["pool"]["chlorine"]["solid_leds"] = solid_leds
    data["pool"]["chlorine"]["blinking_leds"] = blinking_leds
    coordinator = SimpleNamespace(data=data)
    entry.runtime_data = coordinator

    leds = sensor.SyncOrSwimLedSensor(coordinator, entry, "chlorine", "Free Chlorine")

    assert leds.native_value == expected
    assert leds.extra_state_attributes["solid_leds"] == (solid_leds or [])
    assert leds.extra_state_attributes["blinking_leds"] == (blinking_leds or [])


@pytest.mark.parametrize("state", [None, "OK", "Warning", "Error"])
def test_problem_sensor_uses_backend_dosing_problem_state(state):
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            dosing_problem={
                "state": state,
                "reason": "none" if state == "OK" else "chlorine_warning",
                "message": "No dosing problem detected"
                if state == "OK"
                else "Chlorine status is warning",
                "stale": state == "Warning",
                "chlorine_status": "ok",
                "ph_status": "ok",
            },
        )
    )
    entry.runtime_data = coordinator

    problem = sensor.SyncOrSwimProblemSensor(coordinator, entry)

    assert problem._attr_name == "SyncOrSwim Dosing Problem"
    assert problem._attr_device_class == "enum"
    assert problem._attr_options == ["OK", "Warning", "Error"]
    assert problem.native_value == state
    assert problem.extra_state_attributes["problem_reason"] == (
        "none" if state == "OK" else "chlorine_warning"
    )
    assert problem.extra_state_attributes["problem_message"] == (
        "No dosing problem detected" if state == "OK" else "Chlorine status is warning"
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [("OK", "Warning"), ("Warning", "Warning"), ("Error", "Error"), (None, "Warning")],
)
def test_problem_sensor_marks_cached_backend_state_stale(state, expected):
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            stale=True,
            dosing_problem={
                "state": state,
                "reason": "stale_data",
                "message": "Latest reading is stale",
                "stale": False,
                "chlorine_status": "ok",
                "ph_status": "ok",
            },
        )
    )
    entry.runtime_data = coordinator

    problem = sensor.SyncOrSwimProblemSensor(coordinator, entry)

    assert problem.native_value == expected
    assert problem.extra_state_attributes["problem_reason"] == "stale_data"
    assert (
        problem.extra_state_attributes["problem_message"] == "Latest reading is stale"
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [("OK", False), ("Warning", True), ("Error", True), (None, None)],
)
def test_binary_problem_sensor_prefers_backend_dosing_problem_state(state, expected):
    binary_sensor = load_module("binary_sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            pool={
                "chlorine": {"status": "error"},
                "ph": {"status": "error"},
            },
            dosing_problem={
                "state": state,
                "reason": "none" if state == "OK" else "multiple_units",
                "message": "No dosing problem detected"
                if state == "OK"
                else "Multiple dosing units report warnings or errors",
                "stale": False,
                "chlorine_status": "ok",
                "ph_status": "ok",
            },
            stale=False,
        )
    )
    entry.runtime_data = coordinator

    problem = binary_sensor.SyncOrSwimDosingProblemBinarySensor(coordinator, entry)

    assert problem._attr_name == "SyncOrSwim Dosing Problem Active"
    assert problem._attr_unique_id == "entry-1_problem_binary"
    assert problem.is_on is expected
    assert problem.extra_state_attributes["problem_reason"] == (
        "none" if state == "OK" else "multiple_units"
    )
    assert problem.extra_state_attributes["problem_message"] == (
        "No dosing problem detected"
        if state == "OK"
        else "Multiple dosing units report warnings or errors"
    )


def test_problem_sensors_fall_back_for_older_backend_dosing_problem_payloads():
    sensor = load_module("sensor")
    binary_sensor = load_module("binary_sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            stale=True,
            pool={
                "chlorine": {"status": "warning"},
                "ph": {"status": "ok"},
            },
            dosing_problem={
                "state": "OK",
                "stale": False,
            },
        )
    )
    entry.runtime_data = coordinator

    enum_problem = sensor.SyncOrSwimProblemSensor(coordinator, entry)
    binary_problem = binary_sensor.SyncOrSwimDosingProblemBinarySensor(
        coordinator, entry
    )

    for problem in (enum_problem, binary_problem):
        attributes = problem.extra_state_attributes
        assert attributes["problem_reason"] == "stale_data"
        assert attributes["problem_message"] == "Latest reading is stale"
        assert attributes["chlorine_status"] == "warning"
        assert attributes["ph_status"] == "ok"


def test_problem_sensor_does_not_derive_state_without_backend_dosing_problem():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(
            pool={
                "chlorine": {"status": "ok"},
                "ph": {"status": "ok"},
            },
            stale=True,
        )
    )
    entry.runtime_data = coordinator

    problem = sensor.SyncOrSwimProblemSensor(coordinator, entry)

    assert problem.native_value is None


def test_button_name_is_sync_or_swim_prefixed():
    button = load_module("button")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(data=coordinator_data())
    entry.runtime_data = coordinator

    analyze = button.SyncOrSwimAnalyzeButton(coordinator, entry)

    assert analyze._attr_name == "SyncOrSwim Analyze Now"


def test_shared_sensor_exposes_none_for_unavailable_backend_value():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    shared_sensor_data = {
        "key": "sensor.temp_sensor_cellar_temperature",
        "label": "Temperature",
        "value": "unavailable",
        "unit": "C",
        "device_class": "temperature",
        "state_class": "measurement",
        "updated_at": "2026-05-05T10:00:00Z",
    }
    coordinator = SimpleNamespace(data=coordinator_data(sensors=[shared_sensor_data]))
    entry.runtime_data = coordinator

    shared_sensor = sensor.SyncOrSwimSharedSensor(
        coordinator, entry, shared_sensor_data
    )

    assert shared_sensor.native_value is None
    assert shared_sensor.extra_state_attributes["original_label"] == "Temperature"


def test_shared_sensor_uses_specific_name_and_suggested_object_id():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    shared_sensor_data = {
        "key": "sensor.temp_sensor_cellar_temperature",
        "label": "Temperature",
        "value": "12.3",
        "unit": "C",
        "device_class": "temperature",
        "state_class": "measurement",
        "updated_at": "2026-05-05T10:00:00Z",
    }
    coordinator = SimpleNamespace(data=coordinator_data(sensors=[shared_sensor_data]))
    entry.runtime_data = coordinator

    shared_sensor = sensor.SyncOrSwimSharedSensor(
        coordinator, entry, shared_sensor_data
    )

    assert shared_sensor._attr_name == "SyncOrSwim Shared Cellar Temperature"
    assert (
        shared_sensor._attr_suggested_object_id
        == "syncorswim_shared_cellar_temperature"
    )
    assert shared_sensor.native_value == "12.3"


@pytest.mark.asyncio
async def test_producer_controls_reflect_installation_enabled_state():
    button = load_module("button")
    switch = load_module("switch")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        data=coordinator_data(installation_enabled=True),
        installation_enabled=True,
        async_fetch_latest=AsyncMock(),
        async_set_installation_enabled=AsyncMock(),
    )
    entry.runtime_data = coordinator

    fetch_latest = button.SyncOrSwimFetchLatestButton(coordinator, entry)
    installation_enabled = switch.SyncOrSwimInstallationEnabledSwitch(
        coordinator, entry
    )

    assert fetch_latest._attr_name == "SyncOrSwim Fetch Latest"
    assert fetch_latest.available is True
    assert installation_enabled._attr_name == "SyncOrSwim Installation Enabled"
    assert installation_enabled.is_on is True

    await fetch_latest.async_press()
    await installation_enabled.async_turn_off()

    coordinator.async_fetch_latest.assert_awaited_once()
    coordinator.async_set_installation_enabled.assert_awaited_once_with(False)


def test_disabled_installation_keeps_data_non_problematic_and_buttons_offline():
    sensor = load_module("sensor")
    button = load_module("button")
    switch = load_module("switch")
    entry = SimpleNamespace(entry_id="entry-1", runtime_data=SimpleNamespace())
    coordinator = SimpleNamespace(
        installation_enabled=False,
        data=coordinator_data(
            installation_enabled=False,
            pool={
                "chlorine": {"status": "ok"},
                "ph": {"status": "ok"},
            },
            dosing_problem={
                "state": "OK",
                "stale": False,
                "chlorine_status": "ok",
                "ph_status": "ok",
            },
            stale=False,
        ),
    )
    entry.runtime_data = coordinator

    problem = sensor.SyncOrSwimProblemSensor(coordinator, entry)
    analyze = button.SyncOrSwimAnalyzeButton(coordinator, entry)
    fetch_latest = button.SyncOrSwimFetchLatestButton(coordinator, entry)
    installation_enabled = switch.SyncOrSwimInstallationEnabledSwitch(
        coordinator, entry
    )

    assert problem.native_value == "OK"
    assert analyze.available is False
    assert fetch_latest.available is False
    assert installation_enabled.is_on is False


@pytest.mark.asyncio
async def test_consumer_gets_no_producer_controls():
    button = load_module("button")
    switch = load_module("switch")
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={"role": "consumer"},
        runtime_data=SimpleNamespace(),
    )
    coordinator = SimpleNamespace(data=coordinator_data())
    entry.runtime_data = coordinator
    hass = SimpleNamespace(data={})
    entities = []

    await button.async_setup_entry(hass, entry, entities.extend)
    await switch.async_setup_entry(hass, entry, entities.extend)

    assert entities == []
