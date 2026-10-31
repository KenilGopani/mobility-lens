import pytest
from alembic import command
from sqlalchemy import Engine, inspect, text

from app.models import Base
from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.integration

EXPECTED = set(Base.metadata.tables)


def test_all_tables_exist(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= EXPECTED
    assert len(EXPECTED) == 13


def test_no_tiger_or_topology_schemas(engine: Engine) -> None:
    with engine.connect() as conn:
        schemas = set(
            conn.execute(text("SELECT schema_name FROM information_schema.schemata")).scalars()
        )
    assert not schemas & {"tiger", "tiger_data", "topology"}


def test_gist_indexes_exist(engine: Engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN "
                "('ix_service_areas_boundary', 'ix_h3_cells_boundary')"
            )
        ).all()
    assert len(rows) == 2
    assert all("gist" in r.indexdef.lower() for r in rows)


def test_upgrade_downgrade_upgrade_cycle(engine: Engine) -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    assert not set(inspect(engine).get_table_names()) & EXPECTED
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) >= EXPECTED


def test_models_match_migration(engine: Engine) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from geoalchemy2 import alembic_helpers

    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"include_object": alembic_helpers.include_object}
        )
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
