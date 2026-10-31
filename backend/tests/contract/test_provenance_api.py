import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AnalysisRun
from tests.contract.conftest import World

pytestmark = pytest.mark.integration


def test_public_provenance_omits_workstation_paths(
    client: TestClient, world: World, session: Session
):
    run = session.get(AnalysisRun, world.alpha_run)
    run.source_metadata = {
        "source": "overpass",
        "cache_key": "repeatable",
        "cache_dir": "/private/workstation/cache",
    }
    session.flush()
    base = f"/api/v1/service-areas/{world.ids['Alpha']}"
    for suffix in ["metrics", "quality"]:
        source = client.get(f"{base}/{suffix}").json()["source"]
        assert source == {"source": "overpass", "cache_key": "repeatable"}
    detail = client.get(f"/api/v1/analysis-runs/{run.id}").json()
    assert "cache_dir" not in detail["source_metadata"]
    assert run.source_metadata["cache_dir"] == "/private/workstation/cache"
