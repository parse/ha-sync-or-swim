from typing import cast

from db.models import SharedSensor
from sqlalchemy import Table, inspect
from sqlalchemy.engine import Engine


def migrate_shared_sensors_table(engine: Engine) -> None:
    """Create the shared sensors table for deployments that predate it."""
    inspector = inspect(engine)
    if SharedSensor.__tablename__ in inspector.get_table_names():
        return

    table = cast(Table, SharedSensor.__table__)
    table.create(bind=engine, checkfirst=True)
