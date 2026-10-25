"""Contract-test world: 5 areas with hand-chosen normalized metrics so scores are exact.

Baseline weights: intersection_density .25, road_density .25, avg_node_degree .20,
network_directness .15, metadata_completeness .15.

Area     normalized (id, rd, nd, nw, mc)      score            confidence  rank
Alpha    .8  .6  .5  .4  1.0                  66.0             0.9         2 (tie)
Delta    .6  .8  .5  .4  1.0                  66.0             0.9         2 (tie)
Beta     .4  .4  .4  .4  .4                   40.0             0.5         3
Gamma    1.  1.  1.  .5  None                 100*.775/.85     .85*.8=.68  1
Epsilon  (only a failed run)                   null             null        null
Alpha also has an OLDER succeeded run whose normalized values are all 0 (score 0.0).
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import tests.integration.conftest as _db
from app.db.session import get_session
from app.main import create_app
from app.repositories import analysis_runs, quality_findings
from app.repositories.inputs import AreaMetricInput, CellMetricInput, RunCellInput
from cli.seed import seed_metric_definitions, seed_scoring_model
from tests.integration.helpers import make_cell, square_geojson

# Reuse the integration DB fixtures (test-DB guard, migrations, rolled-back session).
engine = _db.engine
session = _db.session

KEYS = [
    "intersection_density",
    "road_density",
    "avg_node_degree",
    "network_directness",
    "metadata_completeness",
]
GAMMA_SCORE = 100 * 0.775 / 0.85


@dataclass
class World:
    ids: dict[str, uuid.UUID]
    alpha_old_run: uuid.UUID
    alpha_run: uuid.UUID
    beta_run: uuid.UUID
    epsilon_failed_run: uuid.UUID
    default_model: uuid.UUID


def _area(session: Session, name: str, x: float) -> uuid.UUID:
    from app.repositories import service_areas

    return service_areas.create(
        session,
        name=name,
        slug=name.lower(),
        boundary_geojson=square_geojson(x, 37.5, 0.1),
        source="test",
    ).id


def _persist(
    session: Session,
    area: uuid.UUID,
    norm: list[float | None],
    raws: list[float | None],
    conf: float,
    *,
    started: datetime,
    cells: list[RunCellInput] | None = None,
    cell_metrics: list[CellMetricInput] | None = None,
) -> uuid.UUID:
    run = analysis_runs.create_run(
        session,
        service_area_id=area,
        pipeline_version="test",
        parameters={"h3_resolution": 9},
        source_metadata={"osm": "fixture"},
        started_at=started,
    )
    analysis_runs.persist_results(
        session,
        run,
        cells=cells or [],
        cell_metrics=cell_metrics or [],
        area_metrics=[
            AreaMetricInput(k, r, n, None if n is None and r is None else conf)
            for k, n, r in zip(KEYS, norm, raws, strict=True)
        ],
    )
    return run.id


@pytest.fixture
def world(session: Session) -> World:
    seed_metric_definitions(session)
    seed_scoring_model(session)
    from app.repositories import scoring_models

    model = scoring_models.get_default(session)
    assert model is not None
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    ids = {n: _area(session, n, x) for n, x in [("Alpha", -122.3), ("Beta", -122.1)]}
    for i, n in enumerate(["Delta", "Gamma", "Epsilon"]):
        ids[n] = _area(session, n, -121.9 + 0.2 * i)

    old = _persist(session, ids["Alpha"], [0.0] * 5, [0.0] * 5, 0.9, started=t0)

    cells = [
        RunCellInput(make_cell("89a", -122.29, 37.51), 1.0),
        RunCellInput(make_cell("89b", -122.25, 37.51), 0.8),
        RunCellInput(make_cell("89c", -122.21, 37.55), 0.4),
    ]
    cm = [
        *[CellMetricInput("89a", k, 5.0, 0.5, 1.0) for k in KEYS],
        CellMetricInput("89b", "intersection_density", 9.0, 1.0, 0.9),
        CellMetricInput("89b", "road_density", None, None, None),
        *[CellMetricInput("89b", k, 9.0, 1.0, 0.9) for k in KEYS[2:]],
        CellMetricInput("89c", "intersection_density", 3.0, 0.2, 0.3),
    ]
    alpha = _persist(
        session,
        ids["Alpha"],
        [0.8, 0.6, 0.5, 0.4, 1.0],
        [10, 15, 10, 10, 10],
        0.9,
        started=t0 + timedelta(days=1),
        cells=cells,
        cell_metrics=cm,
    )
    _persist(
        session,
        ids["Delta"],
        [0.6, 0.8, 0.5, 0.4, 1.0],
        [10, 15, 10, 10, 10],
        0.9,
        started=t0 + timedelta(days=2),
    )
    beta = _persist(
        session,
        ids["Beta"],
        [0.4] * 5,
        [10, 14, 10, 10, 10],
        0.5,
        started=t0 + timedelta(days=2),
    )
    _persist(
        session,
        ids["Gamma"],
        [1.0, 1.0, 1.0, 0.5, None],
        [10, 25, 10, 10, None],
        0.8,
        started=t0 + timedelta(days=2),
    )
    failed = analysis_runs.create_run(
        session,
        service_area_id=ids["Epsilon"],
        pipeline_version="test",
        parameters={},
        started_at=t0,
    )
    analysis_runs.mark_failed(session, failed, "boom")

    for rule, sev, msg in [
        ("DQ-002", "warning", "low completeness"),
        ("DQ-003", "warning", "small area"),
        ("DQ-004", "critical", "few nodes"),
    ]:
        quality_findings.add(
            session,
            analysis_run_id=alpha,
            rule_key=rule,
            severity=sev,
            message=msg,
            affected_fraction=0.5 if rule == "DQ-002" else None,
        )
    return World(ids, old, alpha, beta, failed.id, model.id)


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
