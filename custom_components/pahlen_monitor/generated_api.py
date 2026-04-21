"""Generated from backend/openapi.json. Do not edit manually."""

from typing import Literal, NotRequired, TypedDict

Status = Literal["ok", "warning", "error", "unknown"]
VALID_STATUSES = {"ok", "warning", "error", "unknown"}


class UnitAnalysis(TypedDict):
    status: Status
    diagnosis: str | None
    pattern_detected: str | None
    blinking_leds: list[str]
    solid_leds: list[str]
    summary: str
    action_required: bool
    recommended_action: str


class PushBody(TypedDict):
    captured_at: str
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: NotRequired[str | None]


class LatestMeasurement(TypedDict):
    installation_id: str
    captured_at: str | None
    pushed_at: str | None
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: str | None
