import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PACKAGE_PATH = Path(__file__).resolve().parents[1] / "pahlen_monitor"


class StubCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class StubBinarySensorDeviceClass:
    PROBLEM = "problem"


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
    modules["homeassistant.components.binary_sensor"].BinarySensorEntity = object
    modules[
        "homeassistant.components.binary_sensor"
    ].BinarySensorDeviceClass = StubBinarySensorDeviceClass
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
    package = types.ModuleType("custom_components.pahlen_monitor")
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules["custom_components.pahlen_monitor"] = package
    sys.modules.pop(f"custom_components.pahlen_monitor.{module_name}", None)
    return importlib.import_module(f"custom_components.pahlen_monitor.{module_name}")


def coordinator_data(**overrides):
    data = {
        "captured_at": "2026-04-28T18:16:36Z",
        "stale": False,
        "error": None,
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
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_sensor_setup_creates_pahlen_detail_entities_without_action_sensors():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = SimpleNamespace(data=coordinator_data())
    hass = SimpleNamespace(data={"pahlen_monitor": {"entry-1": coordinator}})
    entities = []

    await sensor.async_setup_entry(hass, entry, entities.extend)

    names = [entity._attr_name for entity in entities]
    assert names == [
        "Pahlen Free Chlorine Status",
        "Pahlen Free Chlorine Summary",
        "Pahlen Free Chlorine Diagnosis",
        "Pahlen Free Chlorine Recommended Action",
        "Pahlen Free Chlorine LEDs",
        "Pahlen pH Status",
        "Pahlen pH Summary",
        "Pahlen pH Diagnosis",
        "Pahlen pH Recommended Action",
        "Pahlen pH LEDs",
    ]
    assert all("Dosing Action" not in name for name in names)


def test_detail_sensors_expose_backend_analysis_fields():
    sensor = load_module("sensor")
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = SimpleNamespace(data=coordinator_data())

    summary = sensor.PahlenDetailSensor(
        coordinator, entry, "chlorine", "Free Chlorine", "summary"
    )
    recommended_action = sensor.PahlenDetailSensor(
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
    entry = SimpleNamespace(entry_id="entry-1")
    data = coordinator_data()
    data["chlorine"]["solid_leds"] = solid_leds
    data["chlorine"]["blinking_leds"] = blinking_leds
    coordinator = SimpleNamespace(data=data)

    leds = sensor.PahlenLedSensor(coordinator, entry, "chlorine", "Free Chlorine")

    assert leds.native_value == expected
    assert leds.extra_state_attributes["solid_leds"] == (solid_leds or [])
    assert leds.extra_state_attributes["blinking_leds"] == (blinking_leds or [])


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        (coordinator_data(chlorine={"status": "unknown"}, stale=True), None),
        (coordinator_data(), True),
        (coordinator_data(stale=True), True),
        (
            coordinator_data(
                chlorine={"status": "ok"},
                ph={"status": "ok"},
                stale=False,
            ),
            False,
        ),
    ],
)
def test_problem_sensor_state_matrix(data, expected):
    binary_sensor = load_module("binary_sensor")
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = SimpleNamespace(data=data)

    problem = binary_sensor.PahlenProblemSensor(coordinator, entry)

    assert problem._attr_name == "Pahlen Dosing Problem"
    assert problem.is_on is expected


def test_button_name_is_pahlen_prefixed():
    button = load_module("button")
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = SimpleNamespace(data=coordinator_data())

    analyze = button.PahlenAnalyzeButton(coordinator, entry)

    assert analyze._attr_name == "Pahlen Analyze Now"
