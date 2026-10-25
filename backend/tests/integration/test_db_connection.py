import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine

pytestmark = pytest.mark.integration


def test_postgis_available() -> None:
    # Deliberately no skip: if the DB is unreachable this must fail (CI provides PostGIS).
    engine = make_engine(get_settings().database_url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT postgis_version()")).scalar_one()
    assert version
