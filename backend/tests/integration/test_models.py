import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AnalysisRunCell,
    AreaMetric,
    AreaScore,
    CellMetric,
    DataQualityFinding,
    H3Cell,
    ScoringModel,
)
from app.repositories import analysis_runs, scoring_models
from app.repositories.inputs import (
    AreaMetricInput,
    CellMetricInput,
    H3CellInput,
    RunCellInput,
)
from tests.integration.helpers import make_area, make_cell, make_metric, square_geojson

pytestmark = pytest.mark.integration


def _persist_one(session: Session) -> tuple[uuid.UUID, str]:
    area = make_area(session)
    make_metric(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    cell = make_cell("89283082803ffff", -122.29, 37.51)
    analysis_runs.persist_results(
        session,
        run,
        cells=[RunCellInput(cell, 1.0)],
        cell_metrics=[],
        area_metrics=[],
    )
    return run.id, cell.h3_index


def test_geometry_round_trip_srid_4326(session: Session) -> None:
    area = make_area(session)
    session.refresh(area)
    cell = make_cell("89283082803ffff", -122.29, 37.51)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    analysis_runs.persist_results(
        session, run, cells=[RunCellInput(cell, 0.5)], cell_metrics=[], area_metrics=[]
    )
    row = session.execute(
        text(
            "SELECT ST_GeometryType(boundary), ST_SRID(boundary), ST_AsText(boundary) "
            "FROM service_areas WHERE id = :i"
        ),
        {"i": area.id},
    ).one()
    assert row[0] == "ST_MultiPolygon"  # POLYGON input promoted to MULTIPOLYGON
    assert row[1] == 4326
    assert row[2].startswith("MULTIPOLYGON(((-122.3 37.5")

    cell_row = session.execute(
        text(
            "SELECT ST_GeometryType(boundary), ST_SRID(boundary), ST_GeometryType(centroid), "
            "ST_SRID(centroid), ST_X(centroid), ST_Y(centroid) FROM h3_cells WHERE h3_index = :h"
        ),
        {"h": cell.h3_index},
    ).one()
    assert cell_row[:4] == ("ST_Polygon", 4326, "ST_Point", 4326)
    assert (cell_row[4], cell_row[5]) == (pytest.approx(-122.285), pytest.approx(37.515))


def test_geometry_type_is_enforced(session: Session) -> None:
    bad = H3CellInput("x1", 9, "POINT(0 0)", "POINT(0 0)")
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    with pytest.raises(Exception):  # noqa: B017 - DB type error (sqlalchemy wraps it)
        analysis_runs.persist_results(
            session, run, cells=[RunCellInput(bad, 1.0)], cell_metrics=[], area_metrics=[]
        )


@pytest.mark.parametrize("ratio", [-0.01, 1.01])
def test_overlap_ratio_check(session: Session, ratio: float) -> None:
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    with pytest.raises(IntegrityError):
        analysis_runs.persist_results(
            session,
            run,
            cells=[RunCellInput(make_cell("a1", -122.29, 37.51), ratio)],
            cell_metrics=[],
            area_metrics=[],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("normalized_value", 1.5), ("normalized_value", -0.1), ("confidence", 2.0)],
)
def test_cell_metric_range_checks(session: Session, field: str, value: float) -> None:
    area = make_area(session)
    make_metric(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    with pytest.raises(IntegrityError):
        analysis_runs.persist_results(
            session,
            run,
            cells=[RunCellInput(make_cell("a1", -122.29, 37.51), 1.0)],
            cell_metrics=[CellMetricInput("a1", "road_density", **{field: value})],
            area_metrics=[],
        )


def test_area_metric_range_check(session: Session) -> None:
    area = make_area(session)
    make_metric(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    with pytest.raises(IntegrityError):
        analysis_runs.persist_results(
            session,
            run,
            cells=[],
            cell_metrics=[],
            area_metrics=[AreaMetricInput("road_density", normalized_value=3.0)],
        )


def test_null_and_zero_are_preserved(session: Session) -> None:
    run_id, h3 = _persist_one(session)
    run = analysis_runs.get(session, run_id)
    assert run is not None
    session.add_all(
        [
            CellMetric(
                analysis_run_id=run_id,
                h3_index=h3,
                metric_key="road_density",
                raw_value=0.0,
                normalized_value=0.0,
                confidence=0.0,
            ),
            AreaMetric(
                analysis_run_id=run_id,
                metric_key="road_density",
                raw_value=None,
                normalized_value=None,
                confidence=None,
            ),
        ]
    )
    session.flush()
    session.expire_all()
    cm = session.get(CellMetric, (run_id, h3, "road_density"))
    am = session.get(AreaMetric, (run_id, "road_density"))
    assert cm is not None
    assert (cm.raw_value, cm.normalized_value, cm.confidence) == (0.0, 0.0, 0.0)
    assert am is not None
    assert (am.raw_value, am.normalized_value, am.confidence) == (None, None, None)


def test_cell_metric_requires_cell_in_run_composite_fk(session: Session) -> None:
    run_id, _ = _persist_one(session)
    other_area = make_area(session, "other", x=-121.0)
    other_run = analysis_runs.create_run(
        session, service_area_id=other_area.id, pipeline_version="t", parameters={}
    )
    # h3 cell exists globally, but is not part of other_run
    session.add(
        CellMetric(
            analysis_run_id=other_run.id,
            h3_index="89283082803ffff",
            metric_key="road_density",
            raw_value=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    assert run_id


def test_analysis_run_status_check(session: Session) -> None:
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    run.status = "weird"
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("severity", ["fatal", ""])
def test_finding_severity_check(session: Session, severity: str) -> None:
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    session.add(
        DataQualityFinding(
            analysis_run_id=run.id, rule_key="DQ-001", severity=severity, message="m"
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_area_score_allows_null_score_but_bounds_range(session: Session) -> None:
    area = make_area(session)
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={}
    )
    model = scoring_models.create(
        session, name="m", version="v1", weights={"a": 1.0}, normalization_version="v1"
    )
    session.add(
        AreaScore(
            analysis_run_id=run.id,
            scoring_model_id=model.id,
            score=None,
            confidence=0.0,
            component_breakdown={},
            calculated_at=func.now(),
        )
    )
    session.flush()
    session.expire_all()
    stored = session.get(AreaScore, (run.id, model.id))
    assert stored is not None
    assert stored.score is None

    stored.score = 101.0
    with pytest.raises(IntegrityError):
        session.flush()


def test_single_default_scoring_model_enforced(session: Session) -> None:
    scoring_models.create(
        session, name="a", version="v1", weights={"x": 1.0}, normalization_version="v1"
    )
    scoring_models.create(
        session,
        name="b",
        version="v1",
        weights={"x": 1.0},
        normalization_version="v1",
        is_default=True,
    )
    session.add(
        ScoringModel(
            name="c", version="v1", weights={"x": 1.0}, normalization_version="v1", is_default=True
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_scoring_model_name_version_unique(session: Session) -> None:
    scoring_models.create(
        session, name="a", version="v1", weights={"x": 1.0}, normalization_version="v1"
    )
    with pytest.raises(IntegrityError):
        scoring_models.create(
            session, name="a", version="v1", weights={"x": 1.0}, normalization_version="v1"
        )


def test_service_area_slug_unique(session: Session) -> None:
    make_area(session, "dup")
    with pytest.raises(IntegrityError):
        make_area(session, "dup")


def test_h3_cells_shared_across_runs(session: Session) -> None:
    area = make_area(session)
    cell = make_cell("shared1", -122.29, 37.51)
    for _ in range(2):
        run = analysis_runs.create_run(
            session, service_area_id=area.id, pipeline_version="t", parameters={}
        )
        analysis_runs.persist_results(
            session, run, cells=[RunCellInput(cell, 1.0)], cell_metrics=[], area_metrics=[]
        )
    assert session.scalar(select(func.count()).select_from(H3Cell)) == 1
    assert session.scalar(select(func.count()).select_from(AnalysisRunCell)) == 2


def test_square_helper_is_polygon() -> None:
    assert square_geojson(0, 0)["type"] == "Polygon"
