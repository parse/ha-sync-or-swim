import os
from collections.abc import Iterator
from time import perf_counter
from typing import Any

from fastapi import Request
from request_timing import elapsed_ms, log_timing
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# If it's postgresql://, change to postgresql+psycopg2:// if needed,
# though psycopg2 is often the default.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine_kwargs: dict[str, Any] = {}
if DATABASE_URL == "sqlite+pysqlite:///:memory:":
    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(request: Request) -> Iterator[Session]:
    started = perf_counter()
    db = SessionLocal()
    try:
        db.connection()
        log_timing(
            "database_acquisition",
            installation_id=request.path_params.get("installation_id", "unknown"),
            duration_ms=elapsed_ms(started),
            pool_status=engine.pool.status(),
        )
        yield db
    finally:
        db.close()
