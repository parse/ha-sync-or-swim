import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PACKAGE_PATH = Path(__file__).resolve().parents[1] / "sync_or_swim"


def sample_measurement():
    return {
        "installation_id": "pool-1",
        "captured_at": "2026-04-28T18:16:36Z",
        "pushed_at": "2026-04-28T18:16:37Z",
        "raw_response": None,
        "dosing_problem": {
            "state": "Warning",
            "reason": "ph_warning",
            "stale": False,
            "chlorine_status": "ok",
            "ph_status": "warning",
        },
        "pool": {
            "chlorine": {
                "status": "ok",
                "summary": "Chlorine is OK",
                "action_required": False,
                "recommended_action": "",
            },
            "ph": {
                "status": "warning",
                "diagnosis": "Standby mode",
                "pattern_detected": "LED 5 blinking",
                "blinking_leds": ["LED 5"],
                "solid_leds": [],
                "summary": "pH unit in standby",
                "action_required": False,
                "recommended_action": "Check pump",
            },
        },
        "sensors": [],
    }


class FakeFormData:
    def __init__(self):
        self.fields = []

    def add_field(self, *args, **kwargs):
        self.fields.append((args, kwargs))


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status = status
        self._payload = payload if payload is not None else sample_measurement()
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class FakeSession:
    calls = []
    responses = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.responses.pop(0)


def load_api_client():
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientSession = FakeSession
    aiohttp.FormData = FakeFormData
    sys.modules["aiohttp"] = aiohttp

    package = types.ModuleType("custom_components.sync_or_swim")
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules["custom_components.sync_or_swim"] = package
    for module_name in (
        "api_client",
        "camera_payload",
        "contract_validation",
        "generated_api_types",
    ):
        sys.modules.pop(f"custom_components.sync_or_swim.{module_name}", None)
    FakeSession.calls = []
    FakeSession.responses = []
    return importlib.import_module("custom_components.sync_or_swim.api_client")


@pytest.mark.asyncio
async def test_get_latest_uses_auth_headers_and_validates_response():
    api_client = load_api_client()
    FakeSession.responses = [FakeResponse(payload=sample_measurement())]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    data = await client.get_latest("pool-1")

    assert data["installation_id"] == "pool-1"
    assert data["dosing_problem"]["reason"] == "ph_warning"
    assert data["pool"]["chlorine"]["blinking_leds"] == []
    assert FakeSession.calls == [
        (
            "get",
            "https://backend.example/api/latest/pool-1",
            {
                "headers": {"Authorization": "Bearer secret"},
                "params": None,
                "timeout": 10,
            },
        )
    ]


@pytest.mark.asyncio
async def test_get_latest_sends_staleness_threshold():
    api_client = load_api_client()
    FakeSession.responses = [FakeResponse(payload=sample_measurement())]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    await client.get_latest("pool-1", 90)

    assert FakeSession.calls == [
        (
            "get",
            "https://backend.example/api/latest/pool-1",
            {
                "headers": {"Authorization": "Bearer secret"},
                "params": {"staleness_threshold_minutes": 90},
                "timeout": 10,
            },
        )
    ]


@pytest.mark.asyncio
async def test_get_latest_defaults_missing_dosing_problem_stale_to_false():
    api_client = load_api_client()
    payload = sample_measurement()
    payload["dosing_problem"].pop("stale")
    FakeSession.responses = [FakeResponse(payload=payload)]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    data = await client.get_latest("pool-1")

    assert data["dosing_problem"]["stale"] is False


@pytest.mark.asyncio
async def test_get_latest_defaults_missing_dosing_problem_reason_to_none():
    api_client = load_api_client()
    payload = sample_measurement()
    payload["dosing_problem"].pop("reason")
    FakeSession.responses = [FakeResponse(payload=payload)]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    data = await client.get_latest("pool-1")

    assert data["dosing_problem"]["reason"] is None


@pytest.mark.asyncio
async def test_get_latest_rejects_invalid_dosing_problem_reason():
    api_client = load_api_client()
    payload = sample_measurement()
    payload["dosing_problem"]["reason"] = "bad_reason"
    FakeSession.responses = [FakeResponse(payload=payload)]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    with pytest.raises(ValueError, match="dosing_problem.reason"):
        await client.get_latest("pool-1")


@pytest.mark.asyncio
async def test_get_latest_rejects_invalid_dosing_problem_stale_type():
    api_client = load_api_client()
    payload = sample_measurement()
    payload["dosing_problem"]["stale"] = "false"
    FakeSession.responses = [FakeResponse(payload=payload)]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example/", "secret", FakeSession()
    )

    with pytest.raises(ValueError, match="dosing_problem.stale"):
        await client.get_latest("pool-1")


@pytest.mark.asyncio
async def test_get_latest_raises_not_found_for_404():
    api_client = load_api_client()
    FakeSession.responses = [FakeResponse(status=404)]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example", None, FakeSession()
    )

    with pytest.raises(api_client.SyncOrSwimApiNotFound):
        await client.get_latest("pool-1")


@pytest.mark.asyncio
async def test_non_200_response_includes_status_and_body():
    api_client = load_api_client()
    FakeSession.responses = [FakeResponse(status=500, text="boom")]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example", None, FakeSession()
    )

    with pytest.raises(api_client.SyncOrSwimApiError, match="500 boom"):
        await client.store_disabled_state("pool-1")

    assert FakeSession.calls == [
        (
            "post",
            "https://backend.example/api/installations/pool-1/disabled",
            {"headers": {}, "timeout": 10},
        )
    ]


@pytest.mark.asyncio
async def test_analyze_burst_uploads_multipart_images():
    api_client = load_api_client()
    FakeSession.responses = [FakeResponse(payload=sample_measurement())]
    client = api_client.SyncOrSwimApiClient(
        "https://backend.example", "secret", FakeSession()
    )
    image = SimpleNamespace(content=b"image-bytes", content_type="image/jpeg")

    await client.analyze_burst("pool-1", [image])

    method, url, kwargs = FakeSession.calls[0]
    assert method == "post"
    assert url == "https://backend.example/api/analyze/pool-1/burst"
    assert kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert kwargs["timeout"] == 60
    assert kwargs["data"].fields == [
        (
            ("files", b"image-bytes"),
            {"filename": "frame_0.jpg", "content_type": "image/jpeg"},
        )
    ]
