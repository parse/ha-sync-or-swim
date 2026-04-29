from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FixtureCase:
    folder: str
    expected: dict[str, dict[str, Any]]
    enabled: bool = True
    disabled_reason: str | None = None


FIXTURE_CASES = [
    FixtureCase(
        folder="burst_5_light_off",
        enabled=False,
        disabled_reason="Legacy color/old-mask calibration fixture",
        expected={
            "chlorine": {
                "level": 2,
                "status": "warning",
                "diagnosis": "Low (Standby)",
                "led_states": [False, False, False, False, False, False, False],
                "blinking": [2],
            },
            "ph": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
        },
    ),
    FixtureCase(
        folder="burst_6_light_off",
        enabled=False,
        disabled_reason="Legacy color/old-mask calibration fixture",
        expected={
            "chlorine": {
                "level": 1,
                "status": "warning",
                "diagnosis": "Low (Standby)",
                "led_states": [False, False, False, False, False, False, False],
                "blinking": [1],
            },
            "ph": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
        },
    ),
    FixtureCase(
        folder="burst_7_light_off",
        enabled=False,
        disabled_reason="Legacy color/old-mask calibration fixture",
        expected={
            "chlorine": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "ph": {
                "level": 5,
                "status": "ok",
                "diagnosis": "High (Standby)",
                "led_states": [False, False, False, False, True, False, False],
                "blinking": [7],
            },
        },
    ),
    FixtureCase(
        folder="burst_8_light_off",
        enabled=False,
        disabled_reason="Legacy color/old-mask calibration fixture",
        expected={
            "chlorine": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "ph": {
                "level": None,
                "status": "error",
                "diagnosis": "Time-out (dosing stopped)",
                "led_states": [False, False, False, False, False, False, False],
                "blinking": [1, 2, 3, 5, 6, 7],
            },
        },
    ),
    FixtureCase(
        folder="burst_9_light_off_bw",
        enabled=False,
        expected={
            "chlorine": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "ph": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
        },
    ),
    FixtureCase(
        folder="burst_10_light_off_bw",
        expected={
            "chlorine": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "ph": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
        },
    ),
    FixtureCase(
        folder="burst_11_light_off_bw",
        expected={
            "chlorine": {
                "level": 4,
                "status": "ok",
                "diagnosis": "Auto mode",
                "led_states": [False, False, False, True, False, False, False],
                "blinking": [],
            },
            "ph": {
                "level": None,
                "status": "error",
                "diagnosis": "Time-out (dosing stopped)",
                "led_states": [False, False, False, False, False, False, False],
                "blinking": [1, 2, 3, 5, 6, 7],
            },
        },
    ),
]


FIXTURE_IDS = [case.folder for case in FIXTURE_CASES]
