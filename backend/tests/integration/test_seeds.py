import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MetricDefinition, ScoringModel, ServiceArea
from app.repositories import scoring_models
from app.schemas import MetricDefinitionRead, ScoringModelRead
from cli import seed
from tests.integration.helpers import square_geojson

pytestmark = pytest.mark.integration


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_metric_definitions_idempotent(session: Session) -> None:
    first = seed.seed_metric_definitions(session)
    second = seed.seed_metric_definitions(session)
    assert len(first.created) == 5
    assert second.created == [] and len(second.updated) == 5
    assert _count(session, MetricDefinition) == 5
    for row in session.scalars(select(MetricDefinition)):
        read = MetricDefinitionRead.model_validate(row)
        assert read.version == "v1"
        assert read.normalization_method == "minmax_fixed"
    avg = session.get(MetricDefinition, "avg_node_degree")
    assert avg is not None
    assert (avg.ref_min, avg.ref_max) == (2.0, 3.5)


def test_seed_scoring_model_idempotent(session: Session) -> None:
    seed.seed_scoring_model(session)
    again = seed.seed_scoring_model(session)
    assert again.created == []
    assert _count(session, ScoringModel) == 1
    default = scoring_models.get_default(session)
    assert default is not None
    read = ScoringModelRead.model_validate(default)
    assert read.weights == seed.BASELINE_WEIGHTS
    assert set(read.weights) == {m["key"] for m in seed.METRIC_DEFINITIONS}


def test_seed_scoring_model_restores_default(session: Session) -> None:
    seed.seed_scoring_model(session)
    other = scoring_models.create(
        session, name="x", version="v1", weights={"a": 1.0}, normalization_version="v1"
    )
    scoring_models.set_default(session, other)
    seed.seed_scoring_model(session)
    session.expire_all()
    default = scoring_models.get_default(session)
    assert default is not None
    assert default.name == "baseline"


def test_seed_service_areas_reports_missing_and_is_idempotent(
    session: Session, tmp_path: Path
) -> None:
    (tmp_path / "foster-city.geojson").write_text(json.dumps(square_geojson(-122.3, 37.5)))
    feature = {"type": "Feature", "properties": {}, "geometry": square_geojson(-121.9, 37.3)}
    (tmp_path / "san-jose.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature]})
    )
    first = seed.seed_service_areas(session, tmp_path)
    assert sorted(first.created) == ["foster-city", "san-jose"]
    assert first.missing == ["mountain-view"]
    second = seed.seed_service_areas(session, tmp_path)
    assert second.created == [] and sorted(second.updated) == ["foster-city", "san-jose"]
    assert _count(session, ServiceArea) == 2


def test_seed_service_areas_rejects_non_polygon(session: Session, tmp_path: Path) -> None:
    (tmp_path / "foster-city.geojson").write_text(
        json.dumps({"type": "Point", "coordinates": [0, 0]})
    )
    with pytest.raises(ValueError, match="Polygon"):
        seed.seed_service_areas(session, tmp_path)


def test_seed_service_areas_rejects_multi_feature(session: Session, tmp_path: Path) -> None:
    doc = {"type": "FeatureCollection", "features": []}
    (tmp_path / "foster-city.geojson").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="exactly one"):
        seed.seed_service_areas(session, tmp_path)


def test_seed_service_areas_records_geojson_source(session: Session, tmp_path: Path) -> None:
    feature = {
        "type": "Feature",
        "properties": {"source": "census-cb-2023:0625338"},
        "geometry": square_geojson(-122.3, 37.5),
    }
    (tmp_path / "foster-city.geojson").write_text(json.dumps(feature))
    (tmp_path / "san-jose.geojson").write_text(json.dumps(square_geojson(-121.9, 37.3)))
    seed.seed_service_areas(session, tmp_path)
    rows = {a.slug: a.source for a in session.scalars(select(ServiceArea))}
    assert rows["foster-city"] == "census-cb-2023:0625338"
    assert rows["san-jose"] == "file:data/boundaries/san-jose.geojson"
