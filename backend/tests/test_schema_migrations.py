from db.migrations import migrate_shared_sensors_table
from db.models import Measurement, SharedSensor
from db.session import engine
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import inspect

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
            "value": "12.3",
            "unit": "C",
            "device_class": "temperature",
            "state_class": "measurement",
            "updated_at": sensor_response.json()[0]["updated_at"],
        }
    ]

    assert inspect(engine).has_table(Measurement.__tablename__)
