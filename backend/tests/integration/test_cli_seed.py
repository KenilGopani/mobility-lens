from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from typer.testing import CliRunner

from cli.__main__ import app

pytestmark = pytest.mark.integration


def test_seed_service_areas_missing_files_exit_nonzero(engine: Engine, tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["seed-service-areas", "--boundary-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "MISSING boundary file" in result.output
    assert "Phase 3" in result.output


def test_seed_metric_and_model_commands_twice(engine: Engine) -> None:
    runner = CliRunner()
    try:
        for _ in range(2):
            assert runner.invoke(app, ["seed-metric-definitions"]).exit_code == 0
            assert runner.invoke(app, ["seed-scoring-model"]).exit_code == 0
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM metric_definitions")).scalar_one() == 5
            assert conn.execute(text("SELECT count(*) FROM scoring_models")).scalar_one() == 1
    finally:
        with engine.begin() as conn:  # these commands commit for real; clean up
            conn.execute(text("DELETE FROM scoring_models"))
            conn.execute(text("DELETE FROM metric_definitions"))
