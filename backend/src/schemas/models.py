import re
from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field

StatusLiteral = Literal["ok", "warning", "error", "unknown"]
DosingProblemLiteral = Literal["OK", "Warning", "Error"]
DosingProblemReasonLiteral = Literal[
    "stale_data",
    "chlorine_error",
    "ph_error",
    "chlorine_warning",
    "ph_warning",
    "multiple_units",
    "unknown",
    "none",
]
ModeLiteral = Literal["auto", "standby", "dosing", "error", "unknown", "disabled"]


class CVBaseUnitResult(TypedDict):
    level: int | None
    mode: ModeLiteral
    status: StatusLiteral
    diagnosis: str


class CVUnitAnalysisPayload(CVBaseUnitResult):
    led_states: list[bool]
    blinking: list[int]


class CVAnalysisResult(TypedDict):
    chlorine: CVUnitAnalysisPayload
    ph: CVUnitAnalysisPayload


class UnitAnalysis(BaseModel):
    status: StatusLiteral = Field(..., description="ok | warning | error | unknown")
    diagnosis: str | None = None
    pattern_detected: str | None = None
    blinking_leds: list[str] = Field(default_factory=list)
    solid_leds: list[str] = Field(default_factory=list)
    summary: str
    action_required: bool
    recommended_action: str


class SharedSensorSchema(BaseModel):
    key: str
    label: str
    preferred_alias: str | None = None
    value: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    updated_at: datetime | None = None


class PoolAnalysisSchema(BaseModel):
    chlorine: UnitAnalysis
    ph: UnitAnalysis


class DosingProblemSchema(BaseModel):
    state: DosingProblemLiteral | None = None
    reason: DosingProblemReasonLiteral | None = None
    message: str | None = None
    stale: bool = False
    chlorine_status: StatusLiteral | None = None
    ph_status: StatusLiteral | None = None


class LatestMeasurementSchema(BaseModel):
    installation_id: str
    captured_at: datetime | None = None
    pushed_at: datetime | None = None
    pool: PoolAnalysisSchema | None = None
    dosing_problem: DosingProblemSchema | None = None
    sensors: list[SharedSensorSchema] = Field(default_factory=list)
    raw_response: str | None = None


class InstallationResponseSchema(BaseModel):
    id: str
    last_seen: datetime | None
    created_at: datetime | None


class SharedSensorUpdateSchema(BaseModel):
    key: str
    label: str
    value: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None


def validate_installation_id(v: str) -> str:
    if not re.match(r"^[a-z0-9-]{1,64}$", v):
        raise ValueError("Invalid installation ID")
    return v
