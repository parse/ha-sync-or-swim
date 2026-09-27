from db.models import Base, SharedSensor
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def migrate_schema(engine: Engine) -> None:
    """Create missing tables and add columns that predate the current models."""
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
