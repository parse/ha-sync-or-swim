---
name: pool-roi-calibration
description: >
  Calibrate the LED Region-of-Interest (ROI) coordinate system in cv_engine.py
  for the Pool-Park chlorine/pH dosing monitor. Use this skill whenever the
  user uploads a new camera image or burst and wants to resync, recalibrate, or
  update ROIS or PRIVACY_MASK_ROIS after the camera has moved.
---

# Pool LED ROI Calibration

## What This Skill Does

This skill recalibrates LED ROI coordinates from a raw Pool-Park camera image
or burst folder. The preferred flow is semi-automatic:

1. Build the same rotated/cropped `1300x500` image used by production.
2. Median-stack burst frames so stable LEDs are easy to locate.
3. Find the stable LED 4 anchor independently for chlorine and pH.
4. Shift each 7-LED row independently while preserving spacing and ROI size.
5. Save a clean overlay for visual verification.
6. Patch `cv_engine.py` only after the overlay looks correct.

For current grayscale/light-off captures, target `PRIVACY_MASK_ROIS` first.

## Prerequisites

- `backend/src/cv_engine.py` is present, or the user provides `--engine`.
- `opencv-python` and `numpy` are available in the active Python environment.
- The input is either a full-frame image or a folder of full-frame burst images.

## Recommended Workflow

### Step 1 - Run A Dry-Run Calibration

From the repository root:

```bash
python .agent/skills/pool-roi-calibration/scripts/calibrate_rois.py \
    backend/tests/fixtures/burst_10_light_off_bw \
    --engine backend/src/cv_engine.py \
    --mode privacy-mask \
    --target privacy-mask-rois \
    --output /tmp/pool_privacy_rois.jpg
```

The script will:

- Parse `CROP_X`, `CROP_Y`, `CROP_WIDTH`, `CROP_HEIGHT`, and
  `PRIVACY_MASK_ROIS` from `cv_engine.py`.
- Rotate and crop each image exactly like `cv_engine.preprocess_image`.
- Build a median crop when the input is a burst folder.
- Detect LED 4 for chlorine and pH near the current privacy-mask ROI row.
- Shift chlorine and pH independently; it never applies one global offset.
- Save a clean overlay with chlorine boxes in green and pH boxes in blue.
- Print proposed `PRIVACY_MASK_ROIS`, anchors, per-device offsets, and input
  details.

### Step 2 - Inspect The Overlay

Open or display the generated overlay and verify:

- The green chlorine boxes sit over all 7 physical diode positions.
- The blue pH boxes sit over all 7 physical diode positions.
- LED 4 is centered in both rows when the burst is known to be stable LED 4.

For more diagnostics, add `--verbose`; the overlay will include the old boxes
and LED 4 anchor crosses.

### Step 3 - Use Manual Anchors If Needed

If automatic LED 4 detection chooses the wrong bright point, rerun with manual
anchors in processed-crop coordinates:

```bash
python .agent/skills/pool-roi-calibration/scripts/calibrate_rois.py \
    backend/tests/fixtures/burst_10_light_off_bw \
    --engine backend/src/cv_engine.py \
    --target privacy-mask-rois \
    --chlorine-anchor 642,247 \
    --ph-anchor 1167,241 \
    --output /tmp/pool_privacy_rois.jpg
```

### Step 4 - Patch Only After Verification

Once the overlay is correct:

```bash
python .agent/skills/pool-roi-calibration/scripts/calibrate_rois.py \
    backend/tests/fixtures/burst_10_light_off_bw \
    --engine backend/src/cv_engine.py \
    --target privacy-mask-rois \
    --output /tmp/pool_privacy_rois.jpg \
    --patch
```

Patching is intentionally narrow: it replaces only the `PRIVACY_MASK_ROIS`
assignment in `cv_engine.py`.

### Step 5 - Verify Runtime Behavior

After patching, run:

```bash
pytest backend/tests/test_cv_fixtures.py -q
```

If a new authoritative fixture has been added, make sure its expected result
matches the known panel state. For `burst_10_light_off_bw`, both chlorine and
pH should be stable LED 4 / Auto mode.

## Troubleshooting

### The Overlay Finds The Wrong Point

- Use `--verbose` to see old boxes and LED 4 anchors.
- Supply `--chlorine-anchor x,y` and/or `--ph-anchor x,y`.
- Prefer burst folders over single frames so the median crop suppresses noise.

### The Crop Region Is Wrong

If the controllers are not inside the `1300x500` output, update the production
`CROP_*` constants first, then rerun calibration. The current script assumes the
crop is still valid and focuses on LED ROI movement.

### Primary Color ROIS Need Recalibration

This flow currently focuses on `PRIVACY_MASK_ROIS`, because grayscale/light-off
captures do not contain reliable HSV color information. Recalibrate primary
`ROIS` separately from a color capture with visible colored LEDs.

## What Not To Change

- Do not edit `SHIFTED_ROIS` directly; it derives from `ROIS`.
- Do not change `COLOR_MASKS` during spatial recalibration.
- Do not patch before inspecting the overlay.

## Key Constants Reference

| Constant | Meaning |
|---|---|
| `CROP_X`, `CROP_Y`, `CROP_WIDTH`, `CROP_HEIGHT` | Full-frame production crop |
| `ROIS` | Primary color LED positions |
| `PRIVACY_MASK_ROIS` | Grayscale/privacy-mask LED positions |
| `SHIFTED_ROIS` | Runtime-derived fallback from `ROIS` |
