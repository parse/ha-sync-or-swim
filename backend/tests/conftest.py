import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["PUSH_TOKEN"] = "test-token"
os.environ["WEB_UI_TOKEN"] = "web-test-token"

from db.models import Base
from db.session import engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = BACKEND_ROOT / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def get_fixture_dir(folder: str) -> Path:
    fixture_dir = FIXTURES_ROOT / folder
    if not fixture_dir.is_dir():
        pytest.fail(f"Fixture directory not found: {fixture_dir}")
    return fixture_dir


def get_fixture_image_paths(folder: str) -> list[Path]:
    image_paths = sorted(get_fixture_dir(folder).glob("*.jpg"))
    if not image_paths:
        pytest.fail(f"No images found in {get_fixture_dir(folder)}")
    return image_paths


def load_fixture_images(folder: str) -> list[bytes]:
    return [path.read_bytes() for path in get_fixture_image_paths(folder)]


@pytest.fixture
def fixture_image_loader() -> Callable[[str], list[bytes]]:
    return load_fixture_images


@pytest.fixture
def fixture_image_paths() -> Callable[[str], list[Path]]:
    return get_fixture_image_paths


@pytest.fixture
def multipart_files_builder() -> Iterator[
    Callable[[str], list[tuple[str, tuple[str, object, str]]]]
]:
    stacks: list[ExitStack] = []

    def build(folder: str) -> list[tuple[str, tuple[str, object, str]]]:
        stack = ExitStack()
        stacks.append(stack)
        return [
            ("files", (path.name, stack.enter_context(path.open("rb")), "image/jpeg"))
            for path in get_fixture_image_paths(folder)
        ]

    yield build

    for stack in stacks:
        stack.close()
