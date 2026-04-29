#!/usr/bin/env python3
"""
Pool LED ROI calibration tool.

The default flow is a dry-run privacy-mask calibration:
  1. Load one full-frame image or all images in a burst folder.
  2. Rotate and crop exactly like cv_engine.preprocess_image.
  3. Median-stack the crop so stable LEDs stand out.
  4. Find LED 4 for each device near the existing ROI.
  5. Shift each device row independently and write a clean overlay.

Patching is opt-in and intentionally narrow:
    --patch --target privacy-mask-rois
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

DeviceName = Literal["chlorine", "ph"]
RoiMap = dict[DeviceName, list[list[int]]]
TargetName = Literal["rois", "privacy-mask-rois"]

CROP_X = 3500
CROP_Y = 800
CROP_WIDTH = 1300
CROP_HEIGHT = 500

DEFAULT_ROIS: RoiMap = {
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

DEFAULT_PRIVACY_MASK_ROIS: RoiMap = {
    "chlorine": [
        [579, 227, 14, 14],
        [600, 227, 14, 14],
        [621, 227, 14, 14],
        [644, 227, 14, 14],
        [662, 227, 14, 14],
        [681, 227, 14, 14],
        [700, 227, 14, 14],
    ],
    "ph": [
        [1111, 225, 14, 14],
        [1129, 225, 14, 14],
        [1147, 225, 14, 14],
        [1166, 225, 14, 14],
        [1182, 225, 14, 14],
        [1199, 225, 14, 14],
        [1216, 225, 14, 14],
    ],
}

ASSIGNMENT_BY_TARGET: dict[TargetName, str] = {
    "rois": "ROIS",
    "privacy-mask-rois": "PRIVACY_MASK_ROIS",
}

COLOR_BY_DEVICE = {
    "chlorine": (40, 255, 40),
    "ph": (255, 80, 0),
}


@dataclass(frozen=True)
class Crop:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class AnchorCandidate:
    x: float
    y: float
    area: float
    mean_value: float
    score: float


@dataclass(frozen=True)
class CalibrationResult:
    target: TargetName
    crop: Crop
    base_rois: RoiMap
    proposed_rois: RoiMap
    anchors: dict[DeviceName, tuple[float, float]]
    offsets: dict[DeviceName, tuple[int, int]]
    image_paths: list[Path]
    candidate_counts: dict[DeviceName, int]


def parse_engine(engine_path: Path) -> dict[str, Any]:
    src = engine_path.read_text()
    parsed: dict[str, Any] = {}
    names = {
        "CROP_X",
        "CROP_Y",
        "CROP_WIDTH",
        "CROP_HEIGHT",
        "ROIS",
        "PRIVACY_MASK_ROIS",
    }
    tree = ast.parse(src)
    for node in ast.walk(tree):
        target_name = None
        value_node = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    target_name = target.id
                    value_node = node.value
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in names:
                target_name = node.target.id
                value_node = node.value

        if target_name and value_node is not None:
            parsed[target_name] = ast.literal_eval(value_node)

    return parsed


def crop_from_engine(engine_params: dict[str, Any]) -> Crop:
    return Crop(
        x=engine_params.get("CROP_X", CROP_X),
        y=engine_params.get("CROP_Y", CROP_Y),
        w=engine_params.get("CROP_WIDTH", CROP_WIDTH),
        h=engine_params.get("CROP_HEIGHT", CROP_HEIGHT),
    )


def rois_from_engine(engine_params: dict[str, Any], target: TargetName) -> RoiMap:
    if target == "privacy-mask-rois":
        return engine_params.get("PRIVACY_MASK_ROIS", DEFAULT_PRIVACY_MASK_ROIS)
    return engine_params.get("ROIS", DEFAULT_ROIS)


def image_paths_from_input(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise SystemExit(f"[ERROR] Input path does not exist: {input_path}")

    extensions = {".jpg", ".jpeg", ".png"}
    image_paths = sorted(
        path for path in input_path.iterdir() if path.suffix.lower() in extensions
    )
    if not image_paths:
        raise SystemExit(f"[ERROR] No JPG/PNG images found in: {input_path}")
    return image_paths


def preprocess_image(image_path: Path, crop: Crop) -> np.ndarray:
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"[ERROR] Cannot read image: {image_path}")

    img = cv2.rotate(img, cv2.ROTATE_180)
    cropped = img[crop.y : crop.y + crop.h, crop.x : crop.x + crop.w]
    if cropped.size == 0:
        raise SystemExit(
            "[ERROR] Crop region is empty: "
            f"x={crop.x} y={crop.y} w={crop.w} h={crop.h}"
        )
    return cropped


def build_median_crop(image_paths: list[Path], crop: Crop) -> np.ndarray:
    crops = [preprocess_image(image_path, crop) for image_path in image_paths]
    return np.median(np.stack(crops, axis=0), axis=0).astype(np.uint8)


def roi_center(roi: list[int]) -> tuple[float, float]:
    x, y, w, h = roi
    return x + w / 2, y + h / 2


def parse_anchor(value: str) -> tuple[float, float]:
    try:
        x_text, y_text = value.split(",", maxsplit=1)
        return float(x_text), float(y_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("anchor must be formatted as x,y") from exc


def find_led4_anchor(
    crop_img: np.ndarray,
    led4_roi: list[int],
    *,
    search_radius_x: int,
    search_radius_y: int,
) -> tuple[tuple[float, float], list[AnchorCandidate]]:
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    expected_x, expected_y = roi_center(led4_roi)

    x1 = max(0, int(round(expected_x - search_radius_x)))
    x2 = min(gray.shape[1], int(round(expected_x + search_radius_x)))
    y1 = max(0, int(round(expected_y - search_radius_y)))
    y2 = min(gray.shape[0], int(round(expected_y + search_radius_y)))
    search = gray[y1:y2, x1:x2]
    if search.size == 0:
        raise SystemExit("[ERROR] LED 4 search window is empty")

    threshold = max(float(np.percentile(search, 99.6)), float(search.mean() + search.std()))
    mask = np.where(search >= threshold, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[AnchorCandidate] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not 3 <= area <= 300:
            continue
        moment = cv2.moments(contour)
        if moment["m00"] == 0:
            continue

        local_x = moment["m10"] / moment["m00"]
        local_y = moment["m01"] / moment["m00"]
        anchor_x = x1 + local_x
        anchor_y = y1 + local_y
        contour_mask = np.zeros(search.shape, dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
        mean_value = float(cv2.mean(search, mask=contour_mask)[0])
        distance = ((anchor_x - expected_x) ** 2 + (anchor_y - expected_y) ** 2) ** 0.5
        score = mean_value + area * 1.5 - distance * 0.15
        candidates.append(AnchorCandidate(anchor_x, anchor_y, area, mean_value, score))

    if not candidates:
        raise SystemExit(
            "[ERROR] Could not find a bright LED 4 anchor near "
            f"({expected_x:.1f},{expected_y:.1f})"
        )

    best = max(candidates, key=lambda candidate: candidate.score)
    return (best.x, best.y), candidates


def shift_device_rois(
    rois: list[list[int]], anchor: tuple[float, float]
) -> tuple[list[list[int]], tuple[int, int]]:
    old_x, old_y = roi_center(rois[3])
    dx = int(round(anchor[0] - old_x))
    dy = int(round(anchor[1] - old_y))
    return [[x + dx, y + dy, w, h] for x, y, w, h in rois], (dx, dy)


def calibrate(
    input_path: Path,
    *,
    engine_path: Path,
    target: TargetName,
    chlorine_anchor: tuple[float, float] | None = None,
    ph_anchor: tuple[float, float] | None = None,
    search_radius_x: int = 90,
    search_radius_y: int = 60,
) -> CalibrationResult:
    engine_params = parse_engine(engine_path) if engine_path.exists() else {}
    crop = crop_from_engine(engine_params)
    base_rois = rois_from_engine(engine_params, target)
    image_paths = image_paths_from_input(input_path)
    median_crop = build_median_crop(image_paths, crop)

    manual_anchors: dict[DeviceName, tuple[float, float] | None] = {
        "chlorine": chlorine_anchor,
        "ph": ph_anchor,
    }
    anchors: dict[DeviceName, tuple[float, float]] = {}
    offsets: dict[DeviceName, tuple[int, int]] = {}
    proposed_rois: RoiMap = {"chlorine": [], "ph": []}
    candidate_counts: dict[DeviceName, int] = {}

    for device in ("chlorine", "ph"):
        anchor = manual_anchors[device]
        candidates: list[AnchorCandidate] = []
        if anchor is None:
            anchor, candidates = find_led4_anchor(
                median_crop,
                base_rois[device][3],
                search_radius_x=search_radius_x,
                search_radius_y=search_radius_y,
            )
        anchors[device] = anchor
        proposed_rois[device], offsets[device] = shift_device_rois(
            base_rois[device], anchor
        )
        candidate_counts[device] = len(candidates)

    return CalibrationResult(
        target=target,
        crop=crop,
        base_rois=base_rois,
        proposed_rois=proposed_rois,
        anchors=anchors,
        offsets=offsets,
        image_paths=image_paths,
        candidate_counts=candidate_counts,
    )


def ensure_rois_inside_crop(rois: RoiMap, crop: Crop) -> None:
    for device, device_rois in rois.items():
        if len(device_rois) != 7:
            raise SystemExit(f"[ERROR] {device} must have 7 ROIs")
        for index, (x, y, w, h) in enumerate(device_rois, start=1):
            if x < 0 or y < 0 or x + w > crop.w or y + h > crop.h:
                raise SystemExit(
                    f"[ERROR] {device} LED {index} ROI is outside crop: "
                    f"{[x, y, w, h]}"
                )


def draw_overlay(
    crop_img: np.ndarray,
    result: CalibrationResult,
    *,
    verbose: bool,
) -> np.ndarray:
    out = crop_img.copy()

    if verbose:
        for device_rois in result.base_rois.values():
            for x, y, w, h in device_rois:
                cv2.rectangle(out, (x, y), (x + w, y + h), (60, 60, 255), 1)

    for device, device_rois in result.proposed_rois.items():
        color = COLOR_BY_DEVICE[device]
        for x, y, w, h in device_rois:
            cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)

    if verbose:
        for device, anchor in result.anchors.items():
            color = COLOR_BY_DEVICE[device]
            cv2.drawMarker(
                out,
                (int(round(anchor[0])), int(round(anchor[1]))),
                color,
                markerType=cv2.MARKER_CROSS,
                markerSize=18,
                thickness=2,
            )
            cv2.putText(
                out,
                f"{device} LED4",
                (int(round(anchor[0])) + 8, int(round(anchor[1])) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1,
            )

    return out


def format_assignment(name: str, rois: RoiMap) -> str:
    lines = [f"{name}: RoiMap = {{"]
    for device in ("chlorine", "ph"):
        lines.append(f'    "{device}": [')
        for roi in rois[device]:
            lines.append(f"        {roi},")
        lines.append("    ],")
    lines.append("}")
    return "\n".join(lines)


def find_assignment_span(src: str, name: str) -> tuple[int, int]:
    tree = ast.parse(src)
    for node in tree.body:
        target_name = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    target_name = target.id
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                target_name = node.target.id

        if target_name == name and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            lines = src.splitlines(keepends=True)
            start = sum(len(line) for line in lines[: node.lineno - 1])
            end = sum(len(line) for line in lines[: node.end_lineno])
            return start, end

    raise SystemExit(f"[ERROR] Could not locate {name} assignment")


def patch_engine(engine_path: Path, target: TargetName, new_rois: RoiMap) -> None:
    assignment_name = ASSIGNMENT_BY_TARGET[target]
    src = engine_path.read_text()
    start, end = find_assignment_span(src, assignment_name)
    new_block = format_assignment(assignment_name, new_rois)
    engine_path.write_text(src[:start] + new_block + src[end:])


def print_result(result: CalibrationResult) -> None:
    assignment_name = ASSIGNMENT_BY_TARGET[result.target]
    print(f"[INFO] Target: {assignment_name}")
    print(
        "[INFO] Crop: "
        f"x={result.crop.x} y={result.crop.y} w={result.crop.w} h={result.crop.h}"
    )
    print(f"[INFO] Images: {len(result.image_paths)}")
    print(f"[INFO] First image: {result.image_paths[0]}")
    for device in ("chlorine", "ph"):
        anchor = result.anchors[device]
        offset = result.offsets[device]
        print(
            f"[INFO] {device} LED4 anchor: "
            f"x={anchor[0]:.1f} y={anchor[1]:.1f} "
            f"offset dx={offset[0]:+d} dy={offset[1]:+d} "
            f"candidates={result.candidate_counts[device]}"
        )

    print("\n" + "=" * 72)
    print(f"Proposed {assignment_name} (dry-run output)")
    print("=" * 72)
    print(format_assignment(assignment_name, result.proposed_rois))
    print("=" * 72 + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate Pool-Park LED ROIs from a full-frame image or burst folder."
    )
    parser.add_argument("input", help="Full-frame image or folder of burst images")
    parser.add_argument(
        "--engine",
        default="backend/src/cv_engine.py",
        help="Path to cv_engine.py",
    )
    parser.add_argument(
        "--mode",
        choices=["privacy-mask"],
        default="privacy-mask",
        help="Calibration mode. Currently privacy-mask recalibrates PRIVACY_MASK_ROIS.",
    )
    parser.add_argument(
        "--target",
        choices=["privacy-mask-rois"],
        default="privacy-mask-rois",
        help="Assignment to print or patch.",
    )
    parser.add_argument(
        "--chlorine-anchor",
        type=parse_anchor,
        help="Manual chlorine LED 4 anchor as x,y in processed crop coordinates",
    )
    parser.add_argument(
        "--ph-anchor",
        type=parse_anchor,
        help="Manual pH LED 4 anchor as x,y in processed crop coordinates",
    )
    parser.add_argument(
        "--output",
        default="debug_rois.jpg",
        help="Path for the clean overlay image",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Draw old boxes and LED 4 anchor crosses on the overlay",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Patch cv_engine.py. Requires --target privacy-mask-rois.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    engine_path = Path(args.engine)
    target: TargetName = args.target
    if args.patch and target != "privacy-mask-rois":
        raise SystemExit("[ERROR] --patch currently only supports privacy-mask-rois")

    result = calibrate(
        input_path,
        engine_path=engine_path,
        target=target,
        chlorine_anchor=args.chlorine_anchor,
        ph_anchor=args.ph_anchor,
    )
    ensure_rois_inside_crop(result.proposed_rois, result.crop)

    median_crop = build_median_crop(result.image_paths, result.crop)
    overlay = draw_overlay(median_crop, result, verbose=args.verbose)
    cv2.imwrite(args.output, overlay)

    print_result(result)
    print(f"[INFO] Overlay saved to: {args.output}")

    if args.patch:
        patch_engine(engine_path, target, result.proposed_rois)
        print(f"[INFO] Patched {ASSIGNMENT_BY_TARGET[target]} in {engine_path}")
    else:
        print("[INFO] Dry run only. Add --patch --target privacy-mask-rois to patch.")


if __name__ == "__main__":
    main()
