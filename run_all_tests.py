import os
from cv_engine import analyze_burst, ROIS


def run_test_on_folder(folder_path):
    print(f"--- Running Test: {folder_path} ---")
    if not os.path.exists(folder_path):
        print(f"Skipping: Folder does not exist: {folder_path}")
        return

    images = []
    filenames = sorted([f for f in os.listdir(folder_path) if f.endswith(".jpg")])
    for filename in filenames:
        with open(os.path.join(folder_path, filename), "rb") as f:
            images.append(f.read())

    result = analyze_burst(images, ROIS)
    print(f"Result: {result}")


base_path = "custom_components/pahlen_monitor/fixtures/"
for folder in sorted(os.listdir(base_path)):
    if "light_off" in folder:
        run_test_on_folder(os.path.join(base_path, folder))
