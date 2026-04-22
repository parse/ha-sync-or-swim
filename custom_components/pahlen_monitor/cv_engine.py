import logging

import cv2
import numpy as np

_LOGGER = logging.getLogger(__name__)

# Calibrated ROIs based on actual LED spots (x, y, w, h)
ROIS = {
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

# Define target HSV ranges for LED colors
COLOR_MASKS = {
    "RED": [((0, 100, 100), (10, 255, 255)), ((170, 100, 100), (180, 255, 255))],
    "YELLOW": [((20, 100, 100), (35, 255, 255))],
    "GREEN": [((40, 100, 100), (85, 255, 255))],
}


def get_led_color(led_idx):
    # LED index 0-6 (1-7)
    # Red: 1, 7. Yellow: 2, 3, 5, 6. Green: 4.
    if led_idx in [0, 6]:
        return "RED"
    if led_idx == 3:
        return "GREEN"
    return "YELLOW"


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    # Rotate 180 degrees
    img = cv2.rotate(img, cv2.ROTATE_180)
    # Apply fixed crop based on calibration [y:y+h, x:x+w]
    return img[800:1300, 3500:4800]


def analyze_burst(images_bytes: list[bytes], rois: dict = ROIS):
    processed_images = [preprocess_image(img) for img in images_bytes]

    # Store results per frame per led
    led_on_frames = {"chlorine": [[] for _ in range(7)], "ph": [[] for _ in range(7)]}

    for img in processed_images:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        for device in ["chlorine", "ph"]:
            for i, roi in enumerate(rois[device]):
                x, y, w, h = roi
                roi_hsv = hsv[y : y + h, x : x + w]

                # Check for color
                color_type = get_led_color(i)
                masks = COLOR_MASKS[color_type]

                is_lit = False
                for lower, upper in masks:
                    mask = cv2.inRange(roi_hsv, lower, upper)
                    if cv2.countNonZero(mask) > 5:  # Threshold for "ON" (pixel count)
                        is_lit = True
                        break
                led_on_frames[device][i].append(is_lit)

    final_results = {}
    for device in ["chlorine", "ph"]:
        led_states = []
        blink_leds = []

        for i in range(7):
            on_frames = np.array(led_on_frames[device][i])
            is_on = np.mean(on_frames) >= 0.5
            led_states.append(bool(is_on))

            transitions = np.sum(np.diff(on_frames.astype(int)) != 0)
            if transitions >= 2:
                blink_leds.append(i + 1)
        # Pahlen state machine logic
        on_count = sum(led_states)
        if 1 in blink_leds or 7 in blink_leds:
            status, diagnosis = "error", "Flow Error"
        elif led_states[0] or led_states[6]:  # Steady red
            status, diagnosis = "error", "Critically High/Low"
        elif all(led_states) and on_count >= 5:  # Threshold for all LEDs
            status, diagnosis = "error", "Time-Out Error"
        elif any(led_states):
            status = "ok"
            diagnosis = "Standby mode" if len(blink_leds) > 0 else "Dosing active"
        else:
            status, diagnosis = "ok", "Stable setpoint"

        final_results[device] = {
            "led_states": led_states,
            "blinking": blink_leds,
            "status": status,
            "diagnosis": diagnosis,
        }

    return final_results
