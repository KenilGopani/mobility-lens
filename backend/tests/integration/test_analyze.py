import uuid
from typing import Any

import networkx as nx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.models import (
    AnalysisRun,
    AnalysisRunCell,
    AreaMetric,
    CellMetric,
    DataQualityFinding,
    H3Cell,
)
from app.repositories import service_areas
from app.repositories.inputs import AreaMetricInput, CellMetricInput
from cli.__main__ import app as cli_app
from cli.seed import seed_metric_definitions
from pipelines.analyze import (
    AnalysisContext,
    AreaNotFoundError,
    FindingInput,
    analyze_area,
)
from pipelines.metrics import METRIC_KEYS
from pipelines.osm import NetworkSnapshot, load_graph_fixture, snapshot_from_graph
from tests.unit.pipelines.conftest import FIXTURE, metre_box

pytestmark = pytest.mark.integration

SLUG = "fixture-town"


@pytest.fixture
def seeded(session: Session) -> str:
    seed_metric_definitions(session)
    boundary = metre_box(-50, -100, 450, 400)
    service_areas.create(
        session,
        name="Fixture Town",
        slug=SLUG,
        boundary_geojson={
            "type": "Polygon",
            "coordinates": [list(map(list, boundary.exterior.coords))],
        },
        source="test",
    )
    session.flush()
    return SLUG


def fixture_provider(polygon: Any, query: str) -> NetworkSnapshot:
    return snapshot_from_graph(load_graph_fixture(FIXTURE), query=query, polygon=polygon)


def _count(session: Session, model: Any, run_id: uuid.UUID) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(model).where(model.analysis_run_id == run_id)
        )
        or 0
    )


def test_end_to_end_on_fixture_graph(session: Session, seeded: str) -> None:
    summary = analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)

    run = session.get(AnalysisRun, summary.analysis_run_id)
    assert run is not None
    assert run.status == "succeeded"
    assert run.completed_at is not None
    assert run.error_message is None
    assert run.parameters["h3_resolution"] == 9
    assert run.parameters["network_type"] == "drive"
    assert run.parameters["utm_crs"].startswith("EPSG:")
    assert run.source_metadata["node_count"] == 26
    assert run.source_metadata["query"] == "Fixture Town"

    assert summary.cell_count > 0
    assert _count(session, AnalysisRunCell, run.id) == summary.cell_count
    assert _count(session, CellMetric, run.id) == summary.cell_count * len(METRIC_KEYS)
    assert _count(session, AreaMetric, run.id) == len(METRIC_KEYS)
    assert session.scalar(select(func.count()).select_from(H3Cell)) == summary.cell_count

    area = {m.metric_key: m for m in session.scalars(select(AreaMetric))}
    assert area["road_density"].raw_value == pytest.approx(4.1 / 0.25, rel=5e-3)
    assert area["intersection_density"].raw_value == pytest.approx(21 / 0.25, rel=5e-3)
    assert all(m.normalized_value is None for m in area.values())  # hook point, no-op default
    assert all(m.normalized_value is None for m in session.scalars(select(CellMetric)))
    # a sparse edge cell has unavailable (NULL, never 0) node-based metrics somewhere or all set
    assert all(m.raw_value is None or m.raw_value >= 0 for m in session.scalars(select(CellMetric)))


def test_rerun_creates_new_run(session: Session, seeded: str) -> None:
    a = analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)
    b = analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)
    assert a.analysis_run_id != b.analysis_run_id
    statuses = list(session.scalars(select(AnalysisRun.status)))
    assert statuses.count("succeeded") == 2
    # cells are shared across runs, not duplicated
    assert session.scalar(select(func.count()).select_from(H3Cell)) == a.cell_count
    assert _count(session, AreaMetric, a.analysis_run_id) == _count(
        session, AreaMetric, b.analysis_run_id
    )


def test_network_failure_marks_run_failed(session: Session, seeded: str) -> None:
    def boom(polygon: Any, query: str) -> NetworkSnapshot:
        raise RuntimeError("overpass unavailable")

    with pytest.raises(RuntimeError, match="overpass"):
        analyze_area(session, seeded, network_provider=boom)
    run = session.scalars(select(AnalysisRun)).one()
    assert run.status == "failed"
    assert run.completed_at is not None
    assert run.error_message is not None and "overpass unavailable" in run.error_message
    assert _count(session, AnalysisRunCell, run.id) == 0


def test_persistence_failure_rolls_back_all_rows(session: Session, seeded: str) -> None:
    def bad_normalizer(
        cells: list[CellMetricInput], areas: list[AreaMetricInput]
    ) -> tuple[list[CellMetricInput], list[AreaMetricInput]]:
        bad = AreaMetricInput("road_density", 1.0, normalized_value=5.0, confidence=1.0)  # CHECK
        return cells, [bad, *areas[1:]]

    with pytest.raises(Exception):  # noqa: B017  (IntegrityError wrapped by SQLAlchemy)
        analyze_area(session, seeded, network_provider=fixture_provider, normalizer=bad_normalizer)
    run = session.scalars(select(AnalysisRun)).one()
    assert run.status == "failed"
    assert run.error_message
    assert _count(session, AnalysisRunCell, run.id) == 0
    assert _count(session, CellMetric, run.id) == 0
    assert run.source_metadata.get("node_count") == 26  # provenance kept on failure


def test_hooks_are_applied(session: Session, seeded: str) -> None:
    def normalizer(
        cells: list[CellMetricInput], areas: list[AreaMetricInput]
    ) -> tuple[list[CellMetricInput], list[AreaMetricInput]]:
        return cells, [AreaMetricInput(a.metric_key, a.raw_value, 0.5, a.confidence) for a in areas]

    seen: list[AnalysisContext] = []

    def evaluator(ctx: AnalysisContext) -> list[FindingInput]:
        seen.append(ctx)
        return [FindingInput("DQ-003", "warning", "small area", 1.0, {"area_km2": ctx.area_km2})]

    summary = analyze_area(
        session,
        seeded,
        network_provider=fixture_provider,
        normalizer=normalizer,
        quality_evaluator=evaluator,
    )
    assert summary.findings == 1
    assert seen[0].node_count == 26
    areas = list(session.scalars(select(AreaMetric)))
    assert all(a.normalized_value == 0.5 for a in areas)
    finding = session.scalars(select(DataQualityFinding)).one()
    assert finding.rule_key == "DQ-003"


def test_unknown_area_creates_no_run(session: Session, seeded: str) -> None:
    with pytest.raises(AreaNotFoundError):
        analyze_area(session, "nope", network_provider=fixture_provider)
    assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 0


def test_cli_analyze_unknown_area_exit_code(engine: Any) -> None:
    result = CliRunner().invoke(cli_app, ["analyze-area", "definitely-not-seeded"])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_graph_type_sanity() -> None:
    assert isinstance(load_graph_fixture(FIXTURE), nx.MultiDiGraph)
