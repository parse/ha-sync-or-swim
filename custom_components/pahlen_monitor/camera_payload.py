from dataclasses import dataclass
from typing import Any

DEFAULT_CONTENT_TYPE = "image/jpeg"


@dataclass(frozen=True)
class CameraPayload:
    content: bytes
    content_type: str


def normalize_camera_payload(capture: Any) -> CameraPayload:
    """Normalize Home Assistant camera captures into uploadable bytes."""
    content_type = DEFAULT_CONTENT_TYPE

    if isinstance(capture, bytes):
        content = capture
    elif isinstance(capture, bytearray | memoryview):
        content = bytes(capture)
    elif hasattr(capture, "content"):
        raw_content = capture.content
        if isinstance(raw_content, bytes):
            content = raw_content
        elif isinstance(raw_content, bytearray | memoryview):
            content = bytes(raw_content)
        else:
            raise ValueError("Camera image content is not bytes-like.")

        raw_content_type = getattr(capture, "content_type", None)
        if raw_content_type:
            content_type = raw_content_type
    else:
        raise ValueError("Camera image capture is not bytes-like.")

    if not content:
        raise ValueError("Camera image content is empty.")

    return CameraPayload(content=content, content_type=content_type)
