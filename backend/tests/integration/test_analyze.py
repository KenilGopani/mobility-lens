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
    AreaScore,
    CellMetric,
    DataQualityFinding,
    H3Cell,
)
from app.repositories import service_areas
from app.repositories.inputs import AreaMetricInput, CellMetricInput
from cli.__main__ import app as cli_app
from cli.seed import seed_metric_definitions, seed_scoring_model
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
    seed_scoring_model(session)
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
    # a sparse edge cell has unavailable (NULL, never 0) node-based metrics somewhere or all set
    assert all(m.raw_value is None or m.raw_value >= 0 for m in session.scalars(select(CellMetric)))


def test_normalized_values_in_unit_range_or_none(session: Session, seeded: str) -> None:
    analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)
    metrics = [*session.scalars(select(CellMetric)), *session.scalars(select(AreaMetric))]
    assert metrics
    for m in metrics:
        if m.raw_value is None:
            assert m.normalized_value is None  # None stays None, never 0
        else:
            assert m.normalized_value is not None and 0.0 <= m.normalized_value <= 1.0
    cells = list(session.scalars(select(CellMetric)))
    assert all("clipped" in (m.metadata_ or {}) for m in cells)
    area = {m.metric_key: m for m in session.scalars(select(AreaMetric))}
    assert area["road_density"].normalized_value == pytest.approx(
        min(1.0, area["road_density"].raw_value / 25.0)  # type: ignore[operator]
    )


def test_none_raw_metric_stays_none() -> None:
    from pipelines.hooks import make_db_normalizer

    class FakeDef:
        ref_min, ref_max, higher_is_better = 0.0, 10.0, True

    class FakeSession:
        def scalars(self, stmt: Any) -> list[Any]:
            return []

    # direct unit check of None handling through the real normalizer with stubbed definitions
    import pipelines.hooks as hooks

    original = hooks.metric_definitions.get_all
    hooks.metric_definitions.get_all = lambda s: {"road_density": FakeDef()}  # type: ignore[assignment,misc]
    try:
        norm = make_db_normalizer(FakeSession())  # type: ignore[arg-type]
        cells, areas = norm(
            [CellMetricInput("h", "road_density", None, None, 0.5, {"a": 1})],
            [AreaMetricInput("road_density", 0.0, None, 1.0)],
        )
    finally:
        hooks.metric_definitions.get_all = original  # type: ignore[assignment]
    assert cells[0].normalized_value is None and cells[0].metadata == {"a": 1, "clipped": False}
    assert areas[0].normalized_value == 0.0  # a real 0 is kept as 0


def test_missing_metric_definition_is_an_error_and_fails_run(session: Session, seeded: str) -> None:
    from sqlalchemy import delete

    from app.models import MetricDefinition
    from pipelines.hooks import MissingMetricDefinitionError

    session.execute(delete(MetricDefinition).where(MetricDefinition.key == "road_density"))
    with pytest.raises(MissingMetricDefinitionError):
        analyze_area(session, seeded, network_provider=fixture_provider)
    run = session.scalars(select(AnalysisRun)).one()
    assert run.status == "failed"
    assert _count(session, AreaScore, run.id) == 0


def test_real_quality_findings_and_config_recorded(session: Session, seeded: str) -> None:
    summary = analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)
    run = session.get(AnalysisRun, summary.analysis_run_id)
    assert run is not None
    keys = {f.rule_key for f in session.scalars(select(DataQualityFinding))}
    assert "DQ-004" in keys  # fixture graph has 26 nodes (< 100)
    assert "DQ-003" in keys  # fixture area is far below 2 km2
    assert summary.findings == len(keys)
    cfg = run.parameters["quality_config"]
    assert cfg["min_nodes"] == 100 and cfg["min_area_km2"] == 2.0


def test_area_score_persisted_and_consistent(session: Session, seeded: str) -> None:
    summary = analyze_area(session, seeded, network_provider=fixture_provider, h3_resolution=9)
    row = session.scalars(select(AreaScore)).one()
    assert row.analysis_run_id == summary.analysis_run_id
    assert row.score is not None and 0 <= row.score <= 100
    assert summary.score == pytest.approx(row.score)
    assert summary.score_confidence == pytest.approx(row.confidence)
    comps = row.component_breakdown["components"]
    assert {c["metric"] for c in comps} == set(METRIC_KEYS)
    assert sum(c["contribution"] for c in comps) == pytest.approx(row.score)
    assert row.component_breakdown["warnings"] == []


def test_failure_leaves_no_area_scores(session: Session, seeded: str) -> None:
    def bad_evaluator(ctx: AnalysisContext) -> list[FindingInput]:
        raise RuntimeError("quality exploded")

    with pytest.raises(RuntimeError):
        analyze_area(
            session, seeded, network_provider=fixture_provider, quality_evaluator=bad_evaluator
        )
    assert session.scalar(select(func.count()).select_from(AreaScore)) == 0


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
    assert summary.score is not None
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
