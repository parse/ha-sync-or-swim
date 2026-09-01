from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

_LOCK_STRIPES = tuple(Lock() for _ in range(64))


@contextmanager
def sensor_request_lock(installation_id: str, idempotency_key: str) -> Iterator[None]:
    """Serialize retries carrying the same idempotency key in this process."""
    lock = _LOCK_STRIPES[hash((installation_id, idempotency_key)) % len(_LOCK_STRIPES)]
    with lock:
        yield
