from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import make_engine


def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().database_url
    dbname = make_url(url).database or ""
    if not dbname.endswith("_test"):
        pytest.exit(f"refusing to run integration tests against non-test database {dbname!r}")
    command.downgrade(alembic_config(), "base")
    command.upgrade(alembic_config(), "head")
    eng = make_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Each test runs in an outer transaction that is rolled back; commits become savepoints."""
    conn = engine.connect()
    outer = conn.begin()
    sess = Session(conn, join_transaction_mode="create_savepoint")
    try:
        yield sess
    finally:
        sess.close()
        outer.rollback()
        conn.close()
