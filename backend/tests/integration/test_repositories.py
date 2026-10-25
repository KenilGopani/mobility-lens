from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AnalysisRunCell, CellMetric
from app.repositories import (
    analysis_runs,
    metrics,
    quality_findings,
    scoring_models,
    service_areas,
)
from app.repositories.inputs import (
    AreaMetricInput,
    BBox,
    CellMetricInput,
    RunCellInput,
)
from tests.integration.helpers import make_area, make_cell, make_metric, square_geojson

pytestmark = pytest.mark.integration


def test_service_areas_listed_by_name(session: Session) -> None:
    for slug, name in [("z", "Zeta"), ("a", "Alpha"), ("m", "Mid")]:
        service_areas.create(
            session, name=name, slug=slug, boundary_geojson=square_geojson(0, 0), source="t"
        )
    assert [a.name for a in service_areas.list_all(session)] == ["Alpha", "Mid", "Zeta"]
    found = service_areas.get_by_slug(session, "m")
    assert found is not None
    assert service_areas.get(session, found.id) is found
    assert service_areas.get_by_slug(session, "nope") is None


def test_upsert_service_area(session: Session) -> None:
    a, created = service_areas.upsert_by_slug(
        session, name="A", slug="a", boundary_geojson=square_geojson(0, 0), source="s1"
    )
    assert created
    b, created2 = service_areas.upsert_by_slug(
        session, name="A2", slug="a", boundary_geojson=square_geojson(1, 1), source="s2"
    )
    assert not created2
    assert b.id == a.id
    assert (b.name, b.source) == ("A2", "s2")
    assert session.scalar(select(func.count()).select_from(type(a))) == 1


def test_latest_succeeded_run(session: Session) -> None:
    area = make_area(session)
    other = make_area(session, "other", x=-100)
    assert analysis_runs.latest_succeeded_for_area(session, area.id) is None

    base = datetime(2026, 1, 1, tzinfo=UTC)

    def run(status_ok: bool, day: int, a: object = area) -> object:
        r = analysis_runs.create_run(
            session,
            service_area_id=a.id,  # type: ignore[attr-defined]
            pipeline_version="t",
            parameters={},
            started_at=base + timedelta(days=day),
        )
        if status_ok:
            analysis_runs.persist_results(session, r, cells=[], cell_metrics=[], area_metrics=[])
            r.completed_at = base + timedelta(days=day, hours=1)
        else:
            analysis_runs.mark_failed(session, r, "boom")
        return r

    old = run(True, 1)
    newest_ok = run(True, 3)
    run(False, 5)  # newer but failed
    run(True, 9, other)  # other area
    session.flush()
    latest = analysis_runs.latest_succeeded_for_area(session, area.id)
    assert latest is not None
    assert latest.id == newest_ok.id  # type: ignore[attr-defined]
    assert latest.id != old.id  # type: ignore[attr-defined]


def test_running_run_is_not_latest_succeeded(session: Session) -> None:
    area = make_area(session)
    analysis_runs.create_run(session, service_area_id=area.id, pipeline_version="t", parameters={})
    assert analysis_runs.latest_succeeded_for_area(session, area.id) is None


def test_persist_run_success_and_metrics(session: Session) -> None:
    area = make_area(session)
    make_metric(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    analysis_runs.persist_results(
        session,
        run,
        cells=[RunCellInput(make_cell("c1", -122.29, 37.51), 0.9)],
        cell_metrics=[
            CellMetricInput("c1", "road_density", 0.0, 0.0, 0.8, {"clipped": False}),
        ],
        area_metrics=[AreaMetricInput("road_density", None, None, 0.1)],
    )
    assert run.status == "succeeded"
    assert run.completed_at is not None
    cm = metrics.list_cell_metrics(session, run.id)
    assert [(m.raw_value, m.metadata_) for m in cm] == [(0.0, {"clipped": False})]
    am = metrics.list_area_metrics(session, run.id)
    assert am[0].raw_value is None


def test_persist_is_atomic_on_failure(session: Session) -> None:
    area = make_area(session)
    make_metric(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    with pytest.raises(IntegrityError):
        analysis_runs.persist_results(
            session,
            run,
            cells=[RunCellInput(make_cell("c1", -122.29, 37.51), 1.0)],
            cell_metrics=[CellMetricInput("c1", "road_density", 1.0, 9.0, 0.5)],  # bad
            area_metrics=[],
        )
    assert session.scalar(select(func.count()).select_from(AnalysisRunCell)) == 0
    assert session.scalar(select(func.count()).select_from(CellMetric)) == 0
    session.refresh(run)
    assert run.status == "running"
    analysis_runs.mark_failed(session, run, "bad value")
    assert run.status == "failed"
    assert run.error_message == "bad value"


def _two_runs(session: Session) -> tuple[object, object]:
    make_metric(session)
    area = make_area(session)
    runs = []
    for i, raw in enumerate([1.0, 2.0]):
        r = analysis_runs.create_run(
            session, service_area_id=area.id, pipeline_version="t", parameters={}
        )
        analysis_runs.persist_results(
            session,
            r,
            cells=[
                RunCellInput(make_cell("shared", -122.29, 37.51), 1.0),
                RunCellInput(make_cell(f"only{i}", -122.25 + i * 0.01, 37.55), 1.0),
            ],
            cell_metrics=[CellMetricInput("shared", "road_density", raw, 0.5, 1.0)],
            area_metrics=[AreaMetricInput("road_density", raw, 0.5, 1.0)],
        )
        runs.append(r)
    return runs[0], runs[1]


def test_metrics_only_for_requested_run(session: Session) -> None:
    r0, r1 = _two_runs(session)
    c0 = metrics.list_cell_metrics(session, r0.id)  # type: ignore[attr-defined]
    c1 = metrics.list_cell_metrics(session, r1.id)  # type: ignore[attr-defined]
    assert [m.raw_value for m in c0] == [1.0]
    assert [m.raw_value for m in c1] == [2.0]
    assert all(m.analysis_run_id == r0.id for m in c0)  # type: ignore[attr-defined]
    assert [m.raw_value for m in metrics.list_area_metrics(session, r0.id)] == [1.0]  # type: ignore[attr-defined]
    assert metrics.list_cell_metrics(session, r0.id, "nonexistent") == []  # type: ignore[attr-defined]


def test_bbox_returns_only_runs_cells(session: Session) -> None:
    r0, r1 = _two_runs(session)
    everything = BBox(-123, 37, -122, 38)
    ids0 = [c.h3_index for c in metrics.cells_in_bbox(session, r0.id, everything)]  # type: ignore[attr-defined]
    ids1 = [c.h3_index for c in metrics.cells_in_bbox(session, r1.id, everything)]  # type: ignore[attr-defined]
    assert ids0 == ["only0", "shared"]
    assert ids1 == ["only1", "shared"]
    # tight bbox around "shared" only (cell spans -122.29..-122.28, 37.51..37.52)
    tight = BBox(-122.285, 37.515, -122.284, 37.516)
    assert [c.h3_index for c in metrics.cells_in_bbox(session, r0.id, tight)] == ["shared"]  # type: ignore[attr-defined]
    far = BBox(10, 10, 11, 11)
    assert metrics.cells_in_bbox(session, r0.id, far) == []  # type: ignore[attr-defined]


def test_default_scoring_model_lookup(session: Session) -> None:
    assert scoring_models.get_default(session) is None
    first = scoring_models.create(
        session,
        name="a",
        version="v1",
        weights={"x": 1.0},
        normalization_version="v1",
        is_default=True,
    )
    assert scoring_models.get_default(session) is first
    second = scoring_models.create(
        session, name="b", version="v1", weights={"x": 1.0}, normalization_version="v1"
    )
    scoring_models.set_default(session, second)
    session.expire_all()
    assert scoring_models.get_default(session) is second
    assert not first.is_default
    assert [m.name for m in scoring_models.list_all(session)] == ["a", "b"]


def test_quality_findings_for_run(session: Session) -> None:
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    other = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    quality_findings.add(
        session, analysis_run_id=run.id, rule_key="DQ-004", severity="critical", message="few"
    )
    quality_findings.add(
        session,
        analysis_run_id=run.id,
        rule_key="DQ-002",
        severity="warning",
        message="meta",
        affected_fraction=0.0,
        metadata={"threshold": 0.5},
    )
    quality_findings.add(
        session, analysis_run_id=other.id, rule_key="DQ-001", severity="info", message="x"
    )
    found = quality_findings.list_for_run(session, run.id)
    assert [f.rule_key for f in found] == ["DQ-002", "DQ-004"]
    assert found[0].affected_fraction == 0.0
