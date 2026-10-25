import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, AreaMetric, AreaScore, CellMetric, ScoringModel
from app.schemas.api import ComparisonResponse, PreviewResponse
from tests.contract.conftest import GAMMA_SCORE, World
from tests.contract.test_service_areas_api import assert_error

pytestmark = pytest.mark.integration

WEIGHTS = {
    "intersection_density": 0.2,
    "road_density": 0.2,
    "avg_node_degree": 0.2,
    "network_directness": 0.2,
    "metadata_completeness": 0.2,
}


def test_comparison_three_areas(client: TestClient, world: World) -> None:
    ids = [world.ids[n] for n in ("Beta", "Gamma", "Alpha")]
    r = client.post("/api/v1/comparisons", json={"service_area_ids": [str(i) for i in ids]})
    assert r.status_code == 200
    c = ComparisonResponse.model_validate(r.json())
    assert [a.name for a in c.areas] == ["Beta", "Gamma", "Alpha"]  # request order
    assert [a.rank for a in c.areas] == [3, 1, 2]
    assert [round(a.score or 0, 6) for a in c.areas] == [40.0, round(GAMMA_SCORE, 6), 66.0]
    assert c.scoring_model.name == "baseline"
    gamma = c.areas[1]
    assert "missing_metric:metadata_completeness" in gamma.warnings
    # DQ-006 over the compared set: Gamma road_density 25 vs peers 15, 14
    assert [(o.rule_key, o.metric) for o in gamma.peer_outliers] == [("DQ-006", "road_density")]
    assert "peer_outlier:road_density" in gamma.warnings
    assert c.areas[0].peer_outliers == [] and c.areas[2].peer_outliers == []
    assert c.areas[2].run is not None and c.areas[2].run.id == world.alpha_run
    assert c.areas[2].strengths[0].metric == "metadata_completeness"


def test_comparison_two_areas_has_no_dq006(client: TestClient, world: World) -> None:
    ids = [str(world.ids["Gamma"]), str(world.ids["Alpha"])]
    c = client.post("/api/v1/comparisons", json={"service_area_ids": ids}).json()
    assert all(a["peer_outliers"] == [] for a in c["areas"])
    assert [a["rank"] for a in c["areas"]] == [1, 2]


def test_comparison_area_without_run(client: TestClient, world: World) -> None:
    ids = [str(world.ids["Epsilon"]), str(world.ids["Alpha"])]
    c = client.post("/api/v1/comparisons", json={"service_area_ids": ids}).json()
    eps, alpha = c["areas"]
    assert eps["score"] is None and eps["confidence"] is None and eps["rank"] is None
    assert eps["warnings"] == ["no_successful_run"] and eps["run"] is None
    assert alpha["rank"] == 1


def test_comparison_ties_share_rank(client: TestClient, world: World) -> None:
    ids = [str(world.ids["Alpha"]), str(world.ids["Delta"])]
    c = client.post("/api/v1/comparisons", json={"service_area_ids": ids}).json()
    assert [a["rank"] for a in c["areas"]] == [1, 1]


def test_comparison_explicit_model(client: TestClient, world: World, session: Session) -> None:
    model = ScoringModel(
        name="equal",
        version="v1",
        weights=WEIGHTS,
        normalization_version="v1",
    )
    session.add(model)
    session.flush()
    ids = [str(world.ids["Beta"]), str(world.ids["Alpha"])]
    c = client.post(
        "/api/v1/comparisons", json={"service_area_ids": ids, "scoring_model_id": str(model.id)}
    ).json()
    assert c["scoring_model"]["name"] == "equal"
    assert c["areas"][1]["score"] == pytest.approx(66.0)  # (.8+.6+.5+.4+1)/5*100 = 66.0


@pytest.mark.parametrize(
    "ids",
    [1, 4, "dup", "none"],
)
def test_comparison_id_count_validation(client: TestClient, world: World, ids: object) -> None:
    pool = [str(i) for i in world.ids.values()]
    body: dict[str, object]
    if ids == "dup":
        body = {"service_area_ids": [pool[0], pool[0]]}
    elif ids == "none":
        body = {}
    else:
        assert isinstance(ids, int)
        body = {"service_area_ids": pool[:ids]}
    assert_error(client.post("/api/v1/comparisons", json=body), 422, "validation_error")


def test_comparison_unknown_refs(client: TestClient, world: World) -> None:
    ids = [str(world.ids["Alpha"]), str(uuid.uuid4())]
    assert_error(
        client.post("/api/v1/comparisons", json={"service_area_ids": ids}), 404, "not_found"
    )
    ids = [str(world.ids["Alpha"]), str(world.ids["Beta"])]
    r = client.post(
        "/api/v1/comparisons", json={"service_area_ids": ids, "scoring_model_id": str(uuid.uuid4())}
    )
    assert_error(r, 404, "not_found")
    r = client.post("/api/v1/comparisons", json={"service_area_ids": ["x", "y"]})
    assert_error(r, 422, "validation_error")


def test_preview_computes_custom_weights(client: TestClient, world: World) -> None:
    ids = [str(world.ids["Alpha"]), str(world.ids["Beta"])]
    r = client.post("/api/v1/scoring/preview", json={"service_area_ids": ids, "weights": WEIGHTS})
    assert r.status_code == 200
    p = PreviewResponse.model_validate(r.json())
    assert p.temporary is True
    assert p.scoring_model.id is None and p.scoring_model.weights == WEIGHTS
    assert p.areas[0].score == pytest.approx(66.0)
    assert p.areas[1].score == pytest.approx(40.0)
    assert [a.rank for a in p.areas] == [1, 2]


def test_preview_never_writes(client: TestClient, world: World, session: Session) -> None:
    tables = [AreaScore, AreaMetric, CellMetric, AnalysisRun, ScoringModel]

    def counts() -> list[int]:
        return [session.scalar(select(func.count()).select_from(t)) or 0 for t in tables]

    before = counts()
    ids = [str(world.ids["Alpha"]), str(world.ids["Gamma"])]
    assert (
        client.post(
            "/api/v1/scoring/preview", json={"service_area_ids": ids, "weights": WEIGHTS}
        ).status_code
        == 200
    )
    bad = {**WEIGHTS, "road_density": 0.9}
    assert (
        client.post(
            "/api/v1/scoring/preview", json={"service_area_ids": ids, "weights": bad}
        ).status_code
        == 422
    )
    assert counts() == before
    assert not session.new and not session.dirty


@pytest.mark.parametrize(
    "weights",
    [
        {**WEIGHTS, "road_density": 0.9},  # sum != 1
        {k: v for k, v in WEIGHTS.items() if k != "road_density"},  # missing key
        {**WEIGHTS, "bogus": 0.0},  # unknown key
        {**WEIGHTS, "road_density": -0.2, "avg_node_degree": 0.6},  # negative
        {},
    ],
)
def test_preview_invalid_weights(
    client: TestClient, world: World, weights: dict[str, float]
) -> None:
    r = client.post(
        "/api/v1/scoring/preview",
        json={"service_area_ids": [str(world.ids["Alpha"])], "weights": weights},
    )
    assert_error(r, 422, "validation_error")
    assert r.json()["error"]["details"]


def test_preview_invalid_weights_details(client: TestClient, world: World) -> None:
    r = client.post(
        "/api/v1/scoring/preview",
        json={
            "service_area_ids": [str(world.ids["Alpha"])],
            "weights": {k: v for k, v in WEIGHTS.items() if k != "road_density"} | {"bogus": 0.2},
        },
    )
    d = r.json()["error"]["details"][0]
    assert d["missing"] == ["road_density"] and d["unexpected"] == ["bogus"]
    assert d["loc"] == ["body", "weights"]


def test_preview_request_validation(client: TestClient, world: World) -> None:
    a = str(world.ids["Alpha"])
    for body in [
        {"service_area_ids": [], "weights": WEIGHTS},
        {"service_area_ids": [a, a], "weights": WEIGHTS},
        {"service_area_ids": [a], "weights": {"road_density": "x"}},
        {"service_area_ids": [a]},
    ]:
        assert_error(client.post("/api/v1/scoring/preview", json=body), 422, "validation_error")
    assert_error(
        client.post(
            "/api/v1/scoring/preview",
            json={"service_area_ids": [str(uuid.uuid4())], "weights": WEIGHTS},
        ),
        404,
        "not_found",
    )
