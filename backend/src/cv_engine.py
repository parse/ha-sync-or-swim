import logging

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
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    # Rotate 180 degrees
    img = cv2.rotate(img, cv2.ROTATE_180)
    # Apply fixed crop based on calibration [y:y+h, x:x+w]
    return img[800:1300, 3500:4800]


def analyze_burst(images_bytes: list[bytes], rois: dict = ROIS):
    import cv2

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
                    mask = cv2.inRange(roi_hsv, np.array(lower), np.array(upper))
                    if (
                        cv2.countNonZero(mask) > 20
                    ):  # Increased threshold to filter noise
                        is_lit = True
                        break
                led_on_frames[device][i].append(is_lit)

    final_results = {}
    for device in ["chlorine", "ph"]:
        led_states = []
        blink_leds = []

        total_frames = len(processed_images)
        for i in range(7):
            on_frames = np.array(led_on_frames[device][i])
            on_count_led = np.sum(on_frames)
            is_on = (on_count_led / total_frames) >= 0.5
            led_states.append(bool(is_on))

            transitions = np.sum(np.diff(on_frames.astype(int)) != 0)

            # Refined blinking detection for short bursts
            if total_frames <= 10:
                # In short sequences, even 1 transition with at least 1 ON frame
                # is indicative of blinking
                if transitions >= 1 and on_count_led >= 1:
                    blink_leds.append(i + 1)
            else:
                # Longer sequences can use more robust 2-transition rule
                if transitions >= 2 and (on_count_led / total_frames) >= 0.1:
                    blink_leds.append(i + 1)

        on_count = sum(led_states)
        has_blinking = len(blink_leds) > 0

        # Logic refined from manual page 11 (Swedish)
        if 1 in blink_leds and 7 in blink_leds:
            # "De två röda dioderna blinkar" -> Flow Error or "blinkar kort" -> Not calibrated
            status, diagnosis = "error", "Flow Error / Uncalibrated"
        elif set(blink_leds).issuperset({1, 2, 3, 5, 6, 7}) and 4 not in blink_leds:
            # "Alla röda och gula dioder blinkar utom den gröna" -> Time-Out
            status, diagnosis = "error", "Time-Out Error"
        elif has_blinking:
            # "Blinkande diod" -> Standby-läge
            status = (
                "warning"
                if (
                    1 in blink_leds
                    or 2 in blink_leds
                    or 6 in blink_leds
                    or 7 in blink_leds
                )
                else "ok"
            )
            if 1 in blink_leds or 2 in blink_leds:
                diagnosis = "Low (Standby)"
            elif 6 in blink_leds or 7 in blink_leds:
                diagnosis = "High (Standby)"
            else:
                diagnosis = "Standby mode"
        elif any(led_states):
            # "Diod lyser med fast sken" -> Automatikläge
            if on_count >= 5:
                # Sequence 1-7 solid-ish is likely Rolling / Forced dosing
                status, diagnosis = "ok", "Forced Dosing"
            elif led_states[3] and on_count == 1:
                # Solid green LED 4
                status, diagnosis = "ok", "Auto mode"
            elif led_states[0] or led_states[6]:
                # Solid red is not in the manual table but implies extreme levels
                status, diagnosis = "error", "Critically High/Low"
            else:
                status, diagnosis = "ok", "Dosing active"
        else:
            status, diagnosis = "ok", "Stable setpoint"

        final_results[device] = {
            "led_states": led_states,
            "blinking": blink_leds,
            "status": status,
            "diagnosis": diagnosis,
        }

    return final_results
