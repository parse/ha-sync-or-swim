import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest
from schemas.models import validate_installation_id

CONST_PATH = Path(__file__).resolve().parents[1] / "sync_or_swim" / "const.py"


def load_const_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_or_swim_const", CONST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CONST_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLATION_ID_PATTERN = load_const_module().INSTALLATION_ID_PATTERN


@pytest.mark.parametrize(
    "installation_id",
    [
        "pool",
        "pool-1",
        "pool-house-2026",
        "a" * 64,
    ],
)
def test_installation_id_contract_accepts_same_examples(installation_id: str) -> None:
    assert validate_installation_id(installation_id) == installation_id
    assert re.fullmatch(INSTALLATION_ID_PATTERN, installation_id)


@pytest.mark.parametrize(
    "installation_id",
    [
        "",
        "Pool",
        "pool_1",
        "pool.1",
        "a" * 65,
    ],
)
def test_installation_id_contract_rejects_same_examples(installation_id: str) -> None:
    with pytest.raises(ValueError):
        validate_installation_id(installation_id)
    assert not re.fullmatch(INSTALLATION_ID_PATTERN, installation_id)
