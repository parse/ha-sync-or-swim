from db.models import Base, SharedSensor
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

# Shared sensor writes use dialect-specific atomic upserts.
SUPPORTED_DIALECTS = {"postgresql", "sqlite"}


def migrate_schema(engine: Engine) -> None:
    """Create missing tables and add columns that predate the current models."""
    if engine.dialect.name not in SUPPORTED_DIALECTS:
        raise RuntimeError(
            f"Unsupported database dialect {engine.dialect.name!r}; "
            "use PostgreSQL or SQLite"
        )

    Base.metadata.create_all(bind=engine, checkfirst=True)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns(SharedSensor.__tablename__)
    }
    if "preferred_alias" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE shared_sensors ADD COLUMN preferred_alias VARCHAR"
            )
