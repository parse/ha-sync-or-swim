import pytest
from db.session import normalize_database_url
from sqlalchemy import create_engine


@pytest.mark.parametrize(
    "url",
    [
        "postgres://user:secret@db.internal:5432/pool",
        "postgresql://user:secret@db.internal:5432/pool",
        "postgresql+psycopg2://user:secret@db.internal:5432/pool",
    ],
)
def test_postgres_urls_use_installed_psycopg2_driver(url):
    normalized = normalize_database_url(url)

    assert normalized == "postgresql+psycopg2://user:secret@db.internal:5432/pool"
    # Creating the engine imports the driver without connecting.
    assert create_engine(normalized).dialect.driver == "psycopg2"


def test_non_postgres_urls_are_unchanged():
    url = "sqlite+pysqlite:///:memory:"

    assert normalize_database_url(url) == url
