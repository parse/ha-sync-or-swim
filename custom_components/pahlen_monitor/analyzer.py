import asyncio
import base64
import json
import logging
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from openai import AsyncOpenAI

from .const import (
    BURST_COUNT,
    BURST_INTERVAL_SECONDS,
    CONF_CAMERA_ENTITY,
    CONF_IMAGE_DETAIL,
    CONF_LIGHT_ENTITY,
    CONF_OPENAI_API_KEY,
    LIGHT_WARMUP_SECONDS,
)
from .contract_validation import AnalysisResult, validate_analysis_result

_LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at analyzing pool dosing equipment. Your task is to look at a burst of images from two Pahlen MiniMaster dosing units (one for Free Chlorine and one for pH) and determine their status based on the LEDs.

IMPORTANT CAMERA ORIENTATION NOTE:
The camera may be mounted upside down (rotated 180 degrees).

This means:
- The image may appear inverted vertically (top ↔ bottom).
- The device itself is still correctly oriented in reality.
- Do NOT treat the image as mirrored — left/right directions are unchanged.

Before analyzing, mentally rotate the image 180 degrees so the device appears upright.

Then interpret LED positions, flashing patterns, and sequences based on the corrected orientation.

The 2 units have 7 LEDs each:
- LED 1 (Leftmost, Red): Critically Low
- LED 2 (Yellow): Low
- LED 3 (Yellow): Slightly Low
- LED 4 (Center, Green): OK (Setpoint)
- LED 5 (Yellow): Slightly High
- LED 6 (Yellow): High
- LED 7 (Rightmost, Red): Critically High

Behavior from Manual:
- Single Steady LED: Automatic mode - Dosing is active.
- Single Flashing LED: Standby mode - Measuring only, no dosing.
- Rolling LEDs in sequence: Forced dosing (Boost).
- LEDs 1 & 7 (Red) Flashing: Flow Error (Too high or too low flow - dosing disabled).
- LEDs 1 & 7 (Red) Flashing (Short): Not Calibrated (Dosing disabled).
- All Red/Yellow LEDs Flashing (LED 4 Green is OFF): Time-Out Error (Continuous dosing > 90 min - dosing disabled).

ANALYZE USING BURST LOGIC (VERY IMPORTANT):
You are given multiple images taken in sequence. You MUST compare them to determine true LED behavior over time.

BURST CONSISTENCY RULE:
- Determine LED states based on the MOST COMMON observation across all frames
- Ignore single-frame anomalies or outliers
- Do not infer blinking or state changes from one or two inconsistent frames

BLINKING DETECTION RULE (CRITICAL):
A LED is only considered blinking if ALL conditions are met:
- The LED is clearly ON in some frames AND OFF in other frames within the burst
- The ON/OFF change is consistent across at least 2 transitions
- The pattern is clearly distinguishable from brightness variation or noise

Do NOT classify a LED as blinking if:
- It only shows slight brightness changes
- It varies due to exposure, glare, or camera noise
- Evidence is inconsistent across frames

If uncertain → treat as SOLID.

CHLORINE UNIT SAFETY RULE:
Only classify chlorine as blinking or abnormal if there is strong multi-frame evidence.

If chlorine LED behavior is uncertain:
- Default status to "ok"
- Avoid reporting errors or warnings unless clearly confirmed across multiple frames
- Prefer false negatives over false positives for chlorine alerts

ANALYZE EACH UNIT INDEPENDENTLY:
- Chlorine and pH units must be analyzed separately
- Do not transfer assumptions or motion patterns between them

LOCATION CONTEXT:
The chlorine unit is on the left (marked "Klordosering") and the pH unit is on the right (marked "Syradosering").

Return the result as JSON:
{
  "chlorine": {
    "status": "ok" | "warning" | "error" | "unknown",
    "diagnosis": "Short description (e.g. Dosing, Standby, Flow Error, Time-Out)",
    "pattern_detected": "Which LEDs are on/flashing (e.g. LED 4 solid)",
    "blinking_leds": ["LED 1", ...],
    "solid_leds": ["LED 4", ...],
    "summary": "Natural language summary of the state",
    "action_required": true | false,
    "recommended_action": "What the user should do"
  },
  "ph": {
    "status": "ok" | "warning" | "error" | "unknown",
    "diagnosis": "...",
    "pattern_detected": "...",
    "blinking_leds": [],
    "solid_leds": [],
    "summary": "...",
    "action_required": true | false,
    "recommended_action": "..."
  }
}
"""


class PahlenAnalyzer:
    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]):
        self.hass = hass
        self.entry_data = entry_data
        self.client = AsyncOpenAI(api_key=entry_data[CONF_OPENAI_API_KEY])

    async def analyze(self) -> AnalysisResult:
        images = await self._capture_burst()
        result = await self._call_openai(images)
        return result

    async def _capture_burst(self) -> list[bytes]:
        camera_entity = self.entry_data[CONF_CAMERA_ENTITY]
        light_entity = self.entry_data[CONF_LIGHT_ENTITY]

        _LOGGER.debug("Turning on light: %s", light_entity)
        await self.hass.services.async_call(
            "light", SERVICE_TURN_ON, {ATTR_ENTITY_ID: light_entity}, blocking=True
        )

        try:
            await asyncio.sleep(LIGHT_WARMUP_SECONDS)

            images = []
            for i in range(BURST_COUNT):
                _LOGGER.debug("Capturing image %d/%d", i + 1, BURST_COUNT)
                image = await async_get_image(self.hass, camera_entity)
                images.append(image.content)
                if i < BURST_COUNT - 1:
                    await asyncio.sleep(BURST_INTERVAL_SECONDS)

            if not images:
                raise RuntimeError("Failed to capture any images from camera")

            return images
        finally:
            _LOGGER.debug("Turning off light: %s", light_entity)
            await self.hass.services.async_call(
                "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: light_entity}, blocking=True
            )

    async def _call_openai(self, images: list[bytes]) -> AnalysisResult:
        content_list = [
            {
                "type": "text",
                "text": "Analyze these images of the Pahlen dosing units and provide the status in JSON format.",
            }
        ]

        for img_bytes in images:
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            content_list.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_img}",
                        "detail": self.entry_data.get(CONF_IMAGE_DETAIL, "low"),
                    },
                }
            )

        _LOGGER.debug("Calling OpenAI API")
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content_list},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty response from OpenAI")

        _LOGGER.debug("OpenAI response: %s", content)
        data = json.loads(content)
        data["raw_response"] = content

        return validate_analysis_result(data)
