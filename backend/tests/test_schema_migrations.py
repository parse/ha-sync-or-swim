from db.migrations import migrate_shared_sensors_table
from db.models import Measurement, SharedSensor
from db.session import engine
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect

client = TestClient(app)


def test_shared_sensors_migration_updates_existing_schema():
    SharedSensor.__table__.drop(bind=engine)
    assert SharedSensor.__tablename__ not in inspect(engine).get_table_names()

    migrate_shared_sensors_table(engine)

    assert SharedSensor.__tablename__ in inspect(engine).get_table_names()

    disabled_response = client.post(
        "/api/installations/test-installation/disabled",
        headers={"Authorization": "Bearer test-token"},
    )
    assert disabled_response.status_code == 200

    sensor_response = client.post(
        "/api/installations/test-installation/sensors",
        headers={"Authorization": "Bearer test-token"},
        json=[
            {
                "key": "sensor.cellar_temperature",
                "label": "Cellar temperature",
                "value": "12.3",
                "unit": "C",
                "device_class": "temperature",
                "state_class": "measurement",
            }
        ],
    )
    assert sensor_response.status_code == 200

    latest_response = client.get(
        "/api/latest/test-installation",
        headers={"Authorization": "Bearer test-token"},
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["sensors"] == [
        {
            "key": "sensor.cellar_temperature",
            "label": "Cellar temperature",
            "preferred_alias": None,
            "value": "12.3",
            "unit": "C",
            "device_class": "temperature",
            "state_class": "measurement",
            "updated_at": sensor_response.json()[0]["updated_at"],
        }
    ]

    assert inspect(engine).has_table(Measurement.__tablename__)


def test_shared_sensors_migration_adds_preferred_alias_to_existing_table():
    SharedSensor.__table__.drop(bind=engine)
    metadata = MetaData()
    Table(
        SharedSensor.__tablename__,
        metadata,
        Column("id", String, primary_key=True),
        Column("installation_id", String, nullable=False),
        Column("key", String, nullable=False),
        Column("label", String, nullable=False),
        Column("value", String, nullable=False),
        Column("unit", String, nullable=True),
        Column("device_class", String, nullable=True),
        Column("state_class", String, nullable=True),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(bind=engine)
    assert "preferred_alias" not in {
        column["name"]
        for column in inspect(engine).get_columns(SharedSensor.__tablename__)
    }

    migrate_shared_sensors_table(engine)

    assert "preferred_alias" in {
        column["name"]
        for column in inspect(engine).get_columns(SharedSensor.__tablename__)
    }
