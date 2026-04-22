import re
from datetime import datetime

from pydantic import BaseModel, Field


class UnitAnalysis(BaseModel):
    status: str = Field(..., description="ok | warning | error | unknown")
    diagnosis: str | None = None
    pattern_detected: str | None = None
    blinking_leds: list[str] = []
    solid_leds: list[str] = []
    summary: str
    action_required: bool
    recommended_action: str


class PushBodySchema(BaseModel):
    captured_at: datetime
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: str | None = None


class LatestMeasurementSchema(BaseModel):
    installation_id: str
    captured_at: datetime | None = None
    pushed_at: datetime | None = None
    chlorine: UnitAnalysis
    ph: UnitAnalysis
    raw_response: str | None = None


class InstallationResponseSchema(BaseModel):
    id: str
    last_seen: datetime
    created_at: datetime


class PushResponseSchema(BaseModel):
    success: bool
    message: str


def validate_installation_id(v: str) -> str:
    if not re.match(r"^[a-z0-9-]{1,64}$", v):
        raise ValueError("Invalid installation ID")
    return v
