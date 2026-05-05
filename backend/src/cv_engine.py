import logging
from typing import Literal

import numpy as np
from schemas.models import (
    CVAnalysisResult,
    CVBaseUnitResult,
    CVUnitAnalysisPayload,
)

_LOGGER = logging.getLogger(__name__)
DeviceName = Literal["chlorine", "ph"]
RoiMap = dict[DeviceName, list[list[int]]]
DEVICE_NAMES: tuple[DeviceName, DeviceName] = ("chlorine", "ph")
LED_COUNT = 7
TIMEOUT_BLINK_LEDS = [1, 2, 3, 5, 6, 7]

CROP_X = 3500
CROP_Y = 800
CROP_WIDTH = 1300
CROP_HEIGHT = 500

# Calibrated ROIs based on actual LED spots (x, y, w, h)
ROIS: RoiMap = {
    "chlorine": [
        [540, 245, 12, 12],
        [558, 245, 12, 12],
        [576, 245, 12, 12],
        [594, 245, 12, 12],
        [612, 245, 12, 12],
        [630, 245, 12, 12],
        [648, 245, 12, 12],
    ],
    "ph": [
        [1012, 238, 12, 12],
        [1029, 238, 12, 12],
        [1046, 238, 12, 12],
        [1063, 238, 12, 12],
        [1078, 238, 10, 10],
        [1097, 238, 10, 10],
        [1112, 238, 10, 10],
    ],
}

# HSV ranges
COLOR_MASKS = {
    "RED": [((0, 100, 100), (10, 255, 255)), ((170, 100, 100), (180, 255, 255))],
    "YELLOW": [((20, 100, 100), (35, 255, 255))],
    "GREEN": [((40, 100, 100), (85, 255, 255))],
}
LED_COLOR_MASK_RATIO_THRESHOLD = 0.25
BRIGHT_LED_MASK_LOWER = (0, 0, 200)
BRIGHT_LED_MASK_UPPER = (180, 80, 255)
SOLID_LED_FRAME_RATIO_THRESHOLD = 0.75
BLINK_MIN_TRANSITIONS = 2
BLINK_MIN_ON_FRAMES = 2
BLINK_MAX_ON_FRAMES = 5
BLINK_MIN_OFF_FRAMES = 3
PH_TIMEOUT_BAND_Y = slice(210, 270)
PH_TIMEOUT_BAND_X = slice(1040, 1230)
PH_TIMEOUT_COLOR_RATIO_THRESHOLD = 0.02
PH_TIMEOUT_MIN_RED_OR_YELLOW_FRAMES = 3
PH_TIMEOUT_MIN_GREEN_FRAMES = 2
PRIVACY_PANEL_Y = slice(120, 310)
PRIVACY_PANEL_X = slice(450, 1250)
PRIVACY_COLORFUL_SATURATION_THRESHOLD = 80
PRIVACY_COLORFUL_VALUE_THRESHOLD = 80
PRIVACY_COLORFUL_RATIO_THRESHOLD = 0.01
PRIVACY_TIMEOUT_MIN_FRAME_RATIO = 0.7

SHIFTED_ROIS: RoiMap = {
    device: [[x + 50, y, w, h] for x, y, w, h in rois] for device, rois in ROIS.items()
}

PRIVACY_MASK_ROIS: RoiMap = {
    "chlorine": [
        [570, 240, 14, 14],
        [591, 240, 14, 14],
        [612, 240, 14, 14],
        [635, 240, 14, 14],
        [653, 240, 14, 14],
        [672, 240, 14, 14],
        [691, 240, 14, 14],
    ],
    "ph": [
        [1105, 234, 14, 14],
        [1123, 234, 14, 14],
        [1141, 234, 14, 14],
        [1160, 234, 14, 14],
        [1176, 234, 14, 14],
        [1193, 234, 14, 14],
        [1210, 234, 14, 14],
    ],
}


def get_led_color(idx: int) -> Literal["RED", "YELLOW", "GREEN"]:
    if idx in [0, 6]:
        return "RED"
    if idx == 3:
        return "GREEN"
    return "YELLOW"


def mask_ratio(mask: np.ndarray, area: int) -> float:
    import cv2

    return float(cv2.countNonZero(mask) / area)


def color_mask_ratio(
    hsv_area: np.ndarray, color_type: str, denominator: int | None = None
) -> float:
    import cv2

    area = denominator or hsv_area.shape[0] * hsv_area.shape[1]
    return sum(
        mask_ratio(cv2.inRange(hsv_area, np.array(lower), np.array(upper)), area)
        for lower, upper in COLOR_MASKS[color_type]
    )


def is_led_lit(roi_hsv: np.ndarray, color_type: str) -> bool:
    import cv2

    area = roi_hsv.shape[0] * roi_hsv.shape[1]
    color_is_lit = any(
        mask_ratio(cv2.inRange(roi_hsv, np.array(lower), np.array(upper)), area)
        > LED_COLOR_MASK_RATIO_THRESHOLD
        for lower, upper in COLOR_MASKS[color_type]
    )
    if color_is_lit:
        return True

    bright_mask = cv2.inRange(
        roi_hsv,
        np.array(BRIGHT_LED_MASK_LOWER),
        np.array(BRIGHT_LED_MASK_UPPER),
    )
    return mask_ratio(bright_mask, area) > LED_COLOR_MASK_RATIO_THRESHOLD


def empty_unit_payload() -> CVUnitAnalysisPayload:
    return {
        "level": None,
        "mode": "unknown",
        "status": "unknown",
        "diagnosis": "Unknown pattern",
        "led_states": [False] * LED_COUNT,
        "blinking": [],
    }


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    img = cv2.rotate(img, cv2.ROTATE_180)
    return img[CROP_Y : CROP_Y + CROP_HEIGHT, CROP_X : CROP_X + CROP_WIDTH]


def derive_level(led_states: list[bool]) -> int | None:
    for i, state in enumerate(led_states):
        if state:
            return i + 1
    return None


def detect_led_on_frames(
    processed_images: list[np.ndarray], rois: RoiMap
) -> dict[DeviceName, list[list[bool]]]:
    import cv2

    led_on_frames: dict[DeviceName, list[list[bool]]] = {
        "chlorine": [[] for _ in range(LED_COUNT)],
        "ph": [[] for _ in range(LED_COUNT)],
    }

    for img in processed_images:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        for device in DEVICE_NAMES:
            for i, roi in enumerate(rois[device]):
                x, y, w, h = roi
                roi_hsv = hsv[y : y + h, x : x + w]
                led_on_frames[device][i].append(is_led_lit(roi_hsv, get_led_color(i)))

    return led_on_frames


def summarize_led_frames(
    frames_by_led: list[list[bool]],
) -> tuple[list[bool], list[int]]:
    total_frames = len(frames_by_led[0])
    led_on_counts = np.zeros(LED_COUNT)
    blink_leds = []

    for i, led_frames in enumerate(frames_by_led):
        frames = np.array(led_frames)
        on_count = np.sum(frames)
        led_on_counts[i] = on_count
        off_count = total_frames - on_count

        transitions = np.sum(np.diff(frames.astype(int)) != 0)
        if (
            transitions >= BLINK_MIN_TRANSITIONS
            and BLINK_MIN_ON_FRAMES <= on_count <= BLINK_MAX_ON_FRAMES
            and off_count >= BLINK_MIN_OFF_FRAMES
        ):
            blink_leds.append(i + 1)

    led_states = [False] * LED_COUNT
    if any(led_on_counts > 0):
        best_led_idx = int(np.argmax(led_on_counts))
        if (
            led_on_counts[best_led_idx] / total_frames
            >= SOLID_LED_FRAME_RATIO_THRESHOLD
        ):
            led_states[best_led_idx] = True

    return led_states, blink_leds


def build_result(
    device: DeviceName, led_states: list[bool], blink_leds: list[int]
) -> CVBaseUnitResult:
    blink_set = set(blink_leds)

    if blink_set.issuperset({1, 2, 3, 5, 6, 7}) and 4 not in blink_set:
        return {
            "level": derive_level(led_states),
            "mode": "error",
            "status": "error",
            "diagnosis": "Time-out (dosing stopped)",
        }

    if blink_leds:
        level: int | None
        if device == "chlorine":
            level = blink_leds[0]
        else:
            level = derive_level(led_states)

        if blink_set.intersection({1, 2}):
            diagnosis = "Low (Standby)"
        elif blink_set.intersection({6, 7}):
            diagnosis = "High (Standby)"
        else:
            diagnosis = "Standby mode"

        return {
            "level": level,
            "mode": "standby",
            "status": "warning",
            "diagnosis": diagnosis,
        }

    level = derive_level(led_states)
    if led_states[3] and sum(led_states) == 1:
        return {
            "level": level,
            "mode": "auto",
            "status": "ok",
            "diagnosis": "Auto mode",
        }

    if any(led_states):
        if level in {1, 2, 3}:
            return {
                "level": level,
                "mode": "dosing" if device == "chlorine" else "unknown",
                "status": "warning",
                "diagnosis": "Below target",
            }

        if level in {5, 6, 7}:
            return {
                "level": level,
                "mode": "dosing" if device == "ph" else "unknown",
                "status": "warning",
                "diagnosis": "Above target",
            }

        return {
            "level": level,
            "mode": "unknown",
            "status": "warning",
            "diagnosis": "Unknown pattern",
        }

    return {
        "level": None,
        "mode": "unknown",
        "status": "warning",
        "diagnosis": "Unknown pattern",
    }


def result_score(result: CVAnalysisResult) -> int:
    score = 0
    for unit_result in (result["chlorine"], result["ph"]):
        if unit_result["level"] is not None:
            score += 2
        score += len(unit_result["blinking"])
        if unit_result["mode"] != "unknown":
            score += 1
    return score


def detect_shifted_ph_timeout(processed_images: list[np.ndarray]) -> bool:
    import cv2

    red_or_yellow_frames = 0
    green_frames = 0

    for img in processed_images:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        timeout_band = hsv[PH_TIMEOUT_BAND_Y, PH_TIMEOUT_BAND_X]

        red_or_yellow_ratio = color_mask_ratio(
            timeout_band, "RED", timeout_band.size
        ) + color_mask_ratio(timeout_band, "YELLOW", timeout_band.size)
        green_ratio = color_mask_ratio(timeout_band, "GREEN", timeout_band.size)

        if red_or_yellow_ratio > PH_TIMEOUT_COLOR_RATIO_THRESHOLD:
            red_or_yellow_frames += 1
        if green_ratio > PH_TIMEOUT_COLOR_RATIO_THRESHOLD:
            green_frames += 1

    return (
        red_or_yellow_frames >= PH_TIMEOUT_MIN_RED_OR_YELLOW_FRAMES
        and green_frames >= PH_TIMEOUT_MIN_GREEN_FRAMES
    )


def timeout_ph_result() -> CVUnitAnalysisPayload:
    return {
        "level": None,
        "mode": "error",
        "status": "error",
        "diagnosis": "Time-out (dosing stopped)",
        "led_states": [False] * LED_COUNT,
        "blinking": list(TIMEOUT_BLINK_LEDS),
    }


def detect_privacy_mask_ph_timeout(processed_images: list[np.ndarray]) -> bool:
    frames_by_led = detect_led_on_frames(processed_images, PRIVACY_MASK_ROIS)["ph"]
    total_frames = len(frames_by_led[0])
    min_on_frames = max(
        BLINK_MIN_ON_FRAMES,
        int(np.ceil(total_frames * PRIVACY_TIMEOUT_MIN_FRAME_RATIO)),
    )

    return all(
        sum(frames_by_led[led - 1]) >= min_on_frames for led in TIMEOUT_BLINK_LEDS
    )


def is_grayscale_privacy_frame(processed_images: list[np.ndarray]) -> bool:
    import cv2

    colorful_ratios = []
    for img in processed_images:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        panel_area = hsv[PRIVACY_PANEL_Y, PRIVACY_PANEL_X]
        saturation = panel_area[:, :, 1]
        value = panel_area[:, :, 2]
        colorful_ratio = (
            np.count_nonzero(
                (saturation > PRIVACY_COLORFUL_SATURATION_THRESHOLD)
                & (value > PRIVACY_COLORFUL_VALUE_THRESHOLD)
            )
            / saturation.size
        )
        colorful_ratios.append(colorful_ratio)

    return bool(max(colorful_ratios, default=0) < PRIVACY_COLORFUL_RATIO_THRESHOLD)


def analyze_with_rois(
    processed_images: list[np.ndarray], rois: RoiMap
) -> CVAnalysisResult:
    led_on_frames = detect_led_on_frames(processed_images, rois)
    final_results: CVAnalysisResult = {
        "chlorine": empty_unit_payload(),
        "ph": empty_unit_payload(),
    }

    for device in DEVICE_NAMES:
        led_states, blink_leds = summarize_led_frames(led_on_frames[device])
        result = build_result(device, led_states, blink_leds)

        final_results[device] = {
            **result,
            "led_states": led_states,
            "blinking": blink_leds,
        }

    return final_results


def candidate_roi_sets(processed_images: list[np.ndarray]) -> list[RoiMap]:
    if is_grayscale_privacy_frame(processed_images):
        return [PRIVACY_MASK_ROIS]
    return [SHIFTED_ROIS]


def best_analysis_result(
    processed_images: list[np.ndarray], initial_result: CVAnalysisResult
) -> CVAnalysisResult:
    result = initial_result
    for candidate_rois in candidate_roi_sets(processed_images):
        candidate_result = analyze_with_rois(processed_images, candidate_rois)
        if result_score(candidate_result) > result_score(result):
            result = candidate_result
    return result


def analyze_burst(images_bytes: list[bytes], rois: RoiMap = ROIS) -> CVAnalysisResult:
    processed_images = [preprocess_image(img) for img in images_bytes]

    result = analyze_with_rois(processed_images, rois)

    if rois is ROIS:
        result = best_analysis_result(processed_images, result)

    if detect_shifted_ph_timeout(processed_images) or (
        rois is ROIS
        and is_grayscale_privacy_frame(processed_images)
        and detect_privacy_mask_ph_timeout(processed_images)
    ):
        result["ph"] = timeout_ph_result()

    return result
