import uuid

import pytest
from fastapi.testclient import TestClient

from app.schemas.api import (
    AreaMetricsResponse,
    CellsResponse,
    QualityResponse,
    ServiceAreaDetail,
    ServiceAreaPage,
    ServiceAreaSummary,
)
from tests.contract.conftest import GAMMA_SCORE, World

pytestmark = pytest.mark.integration
BASE = "/api/v1/service-areas"


def assert_error(resp, status: int, code: str) -> None:  # type: ignore[no-untyped-def]
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


def test_list_order_scores_ranks(client: TestClient, world: World) -> None:
    r = client.get(BASE)
    assert r.status_code == 200
    page = ServiceAreaPage.model_validate(r.json())
    assert [i.name for i in page.items] == ["Alpha", "Beta", "Delta", "Epsilon", "Gamma"]
    assert page.total == 5
    by = {i.name: i for i in page.items}
    assert by["Alpha"].score == pytest.approx(66.0)
    assert by["Alpha"].confidence == pytest.approx(0.9)
    assert by["Gamma"].score == pytest.approx(GAMMA_SCORE)
    assert by["Gamma"].confidence == pytest.approx(0.68)
    assert by["Beta"].score == pytest.approx(40.0)
    # dense ranking, ties share a rank, unscored area unranked
    assert {n: i.rank for n, i in by.items()} == {
        "Gamma": 1,
        "Alpha": 2,
        "Delta": 2,
        "Beta": 3,
        "Epsilon": None,
    }
    assert by["Alpha"].analysis_run_id == world.alpha_run  # latest succeeded, not the old one
    assert by["Alpha"].last_run_at is not None


def test_list_includes_area_without_succeeded_run_with_nulls(
    client: TestClient, world: World
) -> None:
    items = {i["name"]: i for i in client.get(BASE).json()["items"]}
    eps = items["Epsilon"]
    assert eps["score"] is None and eps["confidence"] is None
    assert eps["rank"] is None and eps["last_run_at"] is None and eps["analysis_run_id"] is None


def test_list_pagination(client: TestClient, world: World) -> None:
    p1 = client.get(BASE, params={"limit": 2, "offset": 0}).json()
    p2 = client.get(BASE, params={"limit": 2, "offset": 2}).json()
    p3 = client.get(BASE, params={"limit": 2, "offset": 4}).json()
    assert [i["name"] for i in p1["items"]] == ["Alpha", "Beta"]
    assert [i["name"] for i in p2["items"]] == ["Delta", "Epsilon"]
    assert [i["name"] for i in p3["items"]] == ["Gamma"]
    assert p1["total"] == 5 and p1["limit"] == 2 and p2["offset"] == 2
    # rank is among ALL areas, not the page
    assert p3["items"][0]["rank"] == 1
    assert client.get(BASE, params={"offset": 99}).json()["items"] == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"limit": "x"}])
def test_list_pagination_validation(client: TestClient, params: dict[str, object]) -> None:
    assert_error(client.get(BASE, params=params), 422, "validation_error")


def test_list_is_deterministic(client: TestClient, world: World) -> None:
    assert client.get(BASE).json() == client.get(BASE).json()


def test_detail(client: TestClient, world: World) -> None:
    r = client.get(f"{BASE}/{world.ids['Alpha']}")
    assert r.status_code == 200
    d = ServiceAreaDetail.model_validate(r.json())
    assert d.name == "Alpha" and d.slug == "alpha"
    assert d.boundary["type"] == "MultiPolygon"
    assert d.bbox == pytest.approx([-122.3, 37.5, -122.2, 37.6])


def test_summary(client: TestClient, world: World) -> None:
    r = client.get(f"{BASE}/{world.ids['Alpha']}/summary")
    assert r.status_code == 200
    s = ServiceAreaSummary.model_validate(r.json())
    assert s.score == pytest.approx(66.0) and s.confidence == pytest.approx(0.9)
    assert s.rank == 2 and s.ranked_areas == 4
    assert s.scoring_model is not None and s.scoring_model.name == "baseline"
    # strengths = highest normalized, risks = lowest (disjoint)
    assert [h.metric for h in s.strengths] == ["metadata_completeness", "intersection_density"]
    assert [h.metric for h in s.risks] == ["network_directness", "avg_node_degree"]
    assert (s.finding_counts.info, s.finding_counts.warning, s.finding_counts.critical) == (0, 2, 1)
    assert s.run is not None and s.run.id == world.alpha_run
    contributions = sum(c.contribution or 0 for c in s.components)
    assert contributions == pytest.approx(66.0)
    assert s.warnings == []


def test_summary_with_missing_metric_warns_and_nulls_contribution(
    client: TestClient, world: World
) -> None:
    s = ServiceAreaSummary.model_validate(client.get(f"{BASE}/{world.ids['Gamma']}/summary").json())
    assert "missing_metric:metadata_completeness" in s.warnings
    comp = {c.metric: c for c in s.components}["metadata_completeness"]
    assert comp.normalized_value is None and comp.contribution is None
    assert s.score == pytest.approx(GAMMA_SCORE) and s.rank == 1


def test_summary_without_run(client: TestClient, world: World) -> None:
    s = client.get(f"{BASE}/{world.ids['Epsilon']}/summary").json()
    assert s["score"] is None and s["rank"] is None and s["run"] is None
    assert "no_successful_run" in s["warnings"]
    assert s["finding_counts"] == {"info": 0, "warning": 0, "critical": 0}


def test_metrics(client: TestClient, world: World) -> None:
    r = client.get(f"{BASE}/{world.ids['Alpha']}/metrics")
    assert r.status_code == 200
    m = AreaMetricsResponse.model_validate(r.json())
    assert m.run.id == world.alpha_run
    assert m.source == {"osm": "fixture"}
    assert m.analyzed_at is not None
    assert [x.key for x in m.metrics] == sorted(x.key for x in m.metrics)
    rd = {x.key: x for x in m.metrics}["road_density"]
    assert rd.raw_value == 15 and rd.normalized_value == pytest.approx(0.6)
    assert rd.unit == "km/km2" and rd.higher_is_better and rd.version == "v1"
    assert rd.display_name == "Road density"


def test_metrics_for_specific_run_and_zero_is_not_null(client: TestClient, world: World) -> None:
    r = client.get(
        f"{BASE}/{world.ids['Alpha']}/metrics", params={"analysis_run_id": str(world.alpha_old_run)}
    )
    assert r.status_code == 200
    assert all(m["normalized_value"] == 0.0 and m["raw_value"] == 0.0 for m in r.json()["metrics"])


def test_metrics_null_not_zero(client: TestClient, world: World) -> None:
    m = {x["key"]: x for x in client.get(f"{BASE}/{world.ids['Gamma']}/metrics").json()["metrics"]}
    mc = m["metadata_completeness"]
    assert mc["raw_value"] is None and mc["normalized_value"] is None
    assert mc["confidence"] is None


def test_metrics_run_must_belong_to_area(client: TestClient, world: World) -> None:
    r = client.get(
        f"{BASE}/{world.ids['Alpha']}/metrics", params={"analysis_run_id": str(world.beta_run)}
    )
    assert_error(r, 404, "not_found")
    r = client.get(
        f"{BASE}/{world.ids['Alpha']}/metrics", params={"analysis_run_id": str(uuid.uuid4())}
    )
    assert_error(r, 404, "not_found")
    r = client.get(f"{BASE}/{world.ids['Alpha']}/metrics", params={"analysis_run_id": "nope"})
    assert_error(r, 422, "validation_error")


@pytest.mark.parametrize("suffix", ["metrics", "quality", "cells"])
def test_missing_analysis_is_404(client: TestClient, world: World, suffix: str) -> None:
    assert_error(client.get(f"{BASE}/{world.ids['Epsilon']}/{suffix}"), 404, "not_found")


def test_quality(client: TestClient, world: World) -> None:
    r = client.get(f"{BASE}/{world.ids['Alpha']}/quality")
    assert r.status_code == 200
    q = QualityResponse.model_validate(r.json())
    assert [f.rule_key for f in q.findings] == ["DQ-002", "DQ-003", "DQ-004"]
    assert q.finding_counts.critical == 1 and q.finding_counts.warning == 2
    c = q.completeness
    assert c.cells_count == 3
    # 89c has confidence 0.3 (< 0.5)
    assert c.low_confidence_cells == 1 and c.low_confidence_share == pytest.approx(1 / 3)
    nulls = {m.metric: m for m in c.metrics}
    assert nulls["road_density"].null_cells == 2  # 89b null raw, 89c no row
    assert nulls["road_density"].null_share == pytest.approx(2 / 3)
    assert nulls["intersection_density"].null_cells == 0
    assert nulls["intersection_density"].null_share == 0.0  # 0.0, a real value
    assert q.source == {"osm": "fixture"}


def test_cells_feature_collection(client: TestClient, world: World) -> None:
    r = client.get(f"{BASE}/{world.ids['Alpha']}/cells", params={"metric": "intersection_density"})
    assert r.status_code == 200
    c = CellsResponse.model_validate(r.json())
    assert c.type == "FeatureCollection" and not c.truncated and c.limit == 2000
    assert [f.properties.h3_index for f in c.features] == ["89a", "89b", "89c"]
    p = {f.properties.h3_index: f.properties for f in c.features}
    assert p["89a"].raw_value == 5.0 and p["89a"].normalized_value == 0.5
    assert p["89c"].confidence == 0.3 and p["89c"].overlap_ratio == 0.4
    assert c.features[0].geometry["type"] == "Polygon"


def test_cells_missing_values_are_null_not_zero(client: TestClient, world: World) -> None:
    c = client.get(f"{BASE}/{world.ids['Alpha']}/cells", params={"metric": "road_density"}).json()
    p = {f["properties"]["h3_index"]: f["properties"] for f in c["features"]}
    for cell in ("89b", "89c"):  # null row / no row
        assert p[cell]["raw_value"] is None and p[cell]["normalized_value"] is None
        assert p[cell]["confidence"] is None


def test_cells_overall_score(client: TestClient, world: World) -> None:
    c = client.get(f"{BASE}/{world.ids['Alpha']}/cells").json()  # default metric
    assert c["metric"] == "overall_score"
    p = {f["properties"]["h3_index"]: f["properties"] for f in c["features"]}
    assert p["89a"]["score"] == pytest.approx(50.0)
    assert p["89b"]["score"] == pytest.approx(100.0)  # road_density missing, renormalized
    assert p["89c"]["score"] is None  # only 0.25 of weight available
    assert p["89c"]["raw_value"] is None


def test_cells_bbox_filter_and_limit(client: TestClient, world: World) -> None:
    url = f"{BASE}/{world.ids['Alpha']}/cells"
    r = client.get(url, params={"bbox": "-122.295,37.505,-122.28,37.52"})
    assert [f["properties"]["h3_index"] for f in r.json()["features"]] == ["89a"]
    r = client.get(url, params={"bbox": "-122.3,37.5,-122.2,37.6"})
    assert len(r.json()["features"]) == 3
    r = client.get(url, params={"bbox": "10,10,11,11"})
    assert r.json()["features"] == [] and r.json()["truncated"] is False
    r = client.get(url, params={"limit": 2}).json()
    assert [f["properties"]["h3_index"] for f in r["features"]] == ["89a", "89b"]
    assert r["truncated"] is True
    assert client.get(url, params={"limit": 3}).json()["truncated"] is False


@pytest.mark.parametrize(
    "params",
    [
        {"bbox": "1,2,3"},
        {"bbox": "a,b,c,d"},
        {"bbox": "5,5,1,1"},
        {"bbox": "-200,0,0,10"},
        {"bbox": "0,-91,10,10"},
        {"bbox": "nan,0,1,1"},
        {"limit": 5001},
        {"limit": 0},
        {"metric": "bogus"},
        {"metric": "road_density; drop table"},
    ],
)
def test_cells_validation(client: TestClient, world: World, params: dict[str, object]) -> None:
    assert_error(
        client.get(f"{BASE}/{world.ids['Alpha']}/cells", params=params), 422, "validation_error"
    )


def test_cells_for_old_run(client: TestClient, world: World) -> None:
    r = client.get(
        f"{BASE}/{world.ids['Alpha']}/cells", params={"analysis_run_id": str(world.alpha_old_run)}
    )
    assert r.status_code == 200 and r.json()["features"] == []


@pytest.mark.parametrize("suffix", ["", "/summary", "/metrics", "/quality", "/cells"])
def test_invalid_and_unknown_ids(client: TestClient, world: World, suffix: str) -> None:
    assert_error(client.get(f"{BASE}/not-a-uuid{suffix}"), 422, "validation_error")
    assert_error(client.get(f"{BASE}/{uuid.uuid4()}{suffix}"), 404, "not_found")
