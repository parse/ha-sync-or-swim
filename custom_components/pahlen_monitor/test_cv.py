import os

from cv_engine import ROIS, analyze_burst


def run_test(folder_path, rois, expected_chlorine_blinking=None):
    print(f"--- Running Test: {folder_path} ---")
    images = []
    filenames = sorted([f for f in os.listdir(folder_path) if f.endswith(".jpg")])
    for filename in filenames:
        with open(os.path.join(folder_path, filename), "rb") as f:
            images.append(f.read())

    result = analyze_burst(images, rois)
    print(f"Result: {result}")

    if expected_chlorine_blinking is not None:
        chl_blinking = result["chlorine"]["blinking"]
        assert expected_chlorine_blinking in chl_blinking, (
            f"Chlorine LED {expected_chlorine_blinking} should be blinking, but got {chl_blinking}"
        )
        assert len(chl_blinking) == 1, (
            f"Expected only 1 LED to blink, but got {chl_blinking}"
        )

    print("Test passed!")


run_test("custom_components/pahlen_monitor/fixtures/burst_5_light_off/", ROIS, 2)
