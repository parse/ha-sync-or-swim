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

_LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at analyzing pool dosing equipment. Your task is to look at a burst of images from two Pahlen MiniMaster dosing units (one for Free Chlorine and one for pH) and determine their status based on the LEDs.

The units have 7 LEDs each:
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

Analyze the images carefully by comparing the burst to detect flashing. The chlorine unit is usually on the left and the pH unit on the right.

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

    async def analyze(self) -> dict[str, Any]:
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

    async def _call_openai(self, images: list[bytes]) -> dict[str, Any]:
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

        # Basic validation
        if "chlorine" not in data or "ph" not in data:
            raise RuntimeError("Invalid JSON response from OpenAI: missing units")

        return data
