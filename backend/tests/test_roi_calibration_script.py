import importlib.util
import sys
from pathlib import Path

import pytest
from cv_engine import analyze_burst

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT
    / ".agent"
    / "skills"
    / "pool-roi-calibration"
    / "scripts"
    / "calibrate_rois.py"
)
ENGINE_PATH = REPO_ROOT / "backend" / "src" / "cv_engine.py"
FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "burst_10_light_off_bw"


def load_calibration_module():
    spec = importlib.util.spec_from_file_location("calibrate_rois", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_privacy_mask_calibration_finds_led4_anchors():
    calibrate_rois = load_calibration_module()

    result = calibrate_rois.calibrate(
        FIXTURE_DIR,
        engine_path=ENGINE_PATH,
        target="privacy-mask-rois",
    )

    assert result.anchors["chlorine"] == pytest.approx((641.9, 247.4), abs=0.1)
    assert result.anchors["ph"] == pytest.approx((1167.5, 241.3), abs=0.1)
    assert result.proposed_rois["chlorine"][3] == [635, 240, 14, 14]
    assert result.proposed_rois["ph"][3] == [1160, 234, 14, 14]


def test_privacy_mask_calibration_rois_are_valid_and_read_led4():
    calibrate_rois = load_calibration_module()

    result = calibrate_rois.calibrate(
        FIXTURE_DIR,
        engine_path=ENGINE_PATH,
        target="privacy-mask-rois",
    )
    calibrate_rois.ensure_rois_inside_crop(result.proposed_rois, result.crop)

    assert len(result.proposed_rois["chlorine"]) == 7
    assert len(result.proposed_rois["ph"]) == 7

    images = [path.read_bytes() for path in sorted(FIXTURE_DIR.glob("*.jpg"))]
    analyzed = analyze_burst(images, rois=result.proposed_rois)

    assert analyzed["chlorine"]["level"] == 4
    assert analyzed["chlorine"]["led_states"] == [
        False,
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert analyzed["ph"]["level"] == 4
    assert analyzed["ph"]["led_states"] == [
        False,
        False,
        False,
        True,
        False,
        False,
        False,
    ]
