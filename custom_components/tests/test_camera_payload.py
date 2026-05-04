import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "sync_or_swim" / "camera_payload.py"
SPEC = importlib.util.spec_from_file_location("camera_payload", MODULE_PATH)
camera_payload = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(camera_payload)


def test_normalize_bytes_defaults_to_jpeg():
    payload = camera_payload.normalize_camera_payload(b"image-bytes")

    assert payload.content == b"image-bytes"
    assert payload.content_type == "image/jpeg"


@pytest.mark.parametrize(
    "capture",
    [
        bytearray(b"image-bytes"),
        memoryview(b"image-bytes"),
    ],
)
def test_normalize_bytes_like_values(capture):
    payload = camera_payload.normalize_camera_payload(capture)

    assert payload.content == b"image-bytes"
    assert isinstance(payload.content, bytes)
    assert payload.content_type == "image/jpeg"


def test_normalize_ha_image_preserves_content_type():
    image = SimpleNamespace(content=b"image-bytes", content_type="image/png")

    payload = camera_payload.normalize_camera_payload(image)

    assert payload.content == b"image-bytes"
    assert payload.content_type == "image/png"


def test_normalize_ha_image_defaults_missing_content_type_to_jpeg():
    image = SimpleNamespace(content=b"image-bytes")

    payload = camera_payload.normalize_camera_payload(image)

    assert payload.content == b"image-bytes"
    assert payload.content_type == "image/jpeg"


@pytest.mark.parametrize(
    "capture",
    [
        b"",
        SimpleNamespace(content=b""),
        object(),
    ],
)
def test_normalize_invalid_capture_raises_value_error(capture):
    with pytest.raises(ValueError):
        camera_payload.normalize_camera_payload(capture)
