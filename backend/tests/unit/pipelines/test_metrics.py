import networkx as nx
import pytest

from pipelines.metrics import (
    METRIC_KEYS,
    area_confidence,
    cell_confidence,
    compute_area_metrics,
    compute_cell_metrics,
    prepare_network,
)
from pipelines.spatial import area_km2, estimate_utm_crs, project_geometry
from tests.unit.pipelines.conftest import metre_box

# Hand-computed expectations are derived from the fixture layout in
# tests/fixtures/osm/make_fixture.py. Grid spacing is 100 m; UTM scale (~0.9997) and the
# degree-per-metre rounding in the test boxes justify the ~0.5% tolerances.
REL = 5e-3


@pytest.fixture(scope="module")
def net(fixture_graph: nx.MultiDiGraph):  # type: ignore[no-untyped-def]
    boundary = metre_box(-100, -150, 500, 500)
    return prepare_network(fixture_graph, estimate_utm_crs(boundary))


def _cell(net, region_ll, overlap=1.0):  # type: ignore[no-untyped-def]
    region = project_geometry(region_ll, net.crs)
    return compute_cell_metrics(net, region, overlap_ratio=overlap)


def test_prepare_network_counts(net) -> None:  # type: ignore[no-untyped-def]
    assert len(net.nodes) == 26
    assert len(net.edges) == 41  # 82-ish directed edges collapse to 41 physical streets
    assert net.crs.axis_info[0].unit_name == "metre"


def test_whole_area_metrics(net) -> None:  # type: ignore[no-untyped-def]
    boundary = metre_box(-50, -100, 450, 400)  # 500 m x 500 m = 0.25 km2 containing everything
    m = compute_area_metrics(net, project_geometry(boundary, net.crs))
    assert area_km2(boundary) == pytest.approx(0.25, rel=REL)
    assert m.node_count == 26
    assert m.edge_count == 41
    # 21 nodes with street_count >= 3 over 0.25 km2
    assert m.raw["intersection_density"] == pytest.approx(21 / 0.25, rel=REL)
    # 39*100 + 150 + 50 = 4100 m over 0.25 km2
    assert m.raw["road_density"] == pytest.approx(4.1 / 0.25, rel=REL)
    # sum(street_count) = 82 over 26 nodes
    assert m.raw["avg_node_degree"] == pytest.approx(82 / 26, rel=1e-9)
    # straight 4050 m / length 4100 m
    assert m.raw["network_directness"] == pytest.approx(4050 / 4100, rel=REL)
    # mean(32/41, 12/41, 8/41)
    assert m.raw["metadata_completeness"] == pytest.approx(52 / 123, rel=1e-9)
    assert set(m.raw) == set(METRIC_KEYS)


def test_cell_with_clipped_edges(net) -> None:  # type: ignore[no-untyped-def]
    # x in [-50, 250], y in [-100, 250]: 9 grid nodes + stub, edges clipped at x=250 and y=250
    m = _cell(net, metre_box(-50, -100, 250, 250))
    assert m.node_count == 10
    assert m.edge_count == 19
    assert m.raw["intersection_density"] == pytest.approx(8 / 0.105, rel=REL)
    assert m.raw["road_density"] == pytest.approx(1.6 / 0.105, rel=REL)
    assert m.raw["avg_node_degree"] == pytest.approx(32 / 10, rel=1e-9)
    assert m.raw["network_directness"] == pytest.approx(1550 / 1600, rel=REL)
    assert m.raw["metadata_completeness"] == pytest.approx(30 / 57, rel=1e-9)
    assert all(c == 1.0 for c in m.confidence.values())


def test_cell_without_nodes_has_none_not_zero(net) -> None:  # type: ignore[no-untyped-def]
    # no node inside (x in 110..190), but two roads (rows 0 and 1) pass through it
    m = _cell(net, metre_box(110, -10, 190, 110))
    assert m.node_count == 0
    assert m.edge_count == 2
    assert m.raw["road_density"] is not None
    assert m.raw["intersection_density"] is None
    assert m.raw["avg_node_degree"] is None
    assert m.confidence["intersection_density"] is None


def test_cell_without_roads(net) -> None:  # type: ignore[no-untyped-def]
    m = _cell(net, metre_box(-1000, -1000, -900, -900))
    assert m.edge_count == 0
    assert m.raw["road_density"] == 0.0  # a genuine zero: area with no roads
    assert m.raw["network_directness"] is None
    assert m.raw["metadata_completeness"] is None
    assert m.raw["intersection_density"] is None
    assert m.confidence["road_density"] is not None


def test_directness_ignores_self_loops(fixture_graph: nx.MultiDiGraph) -> None:
    g = fixture_graph.copy()
    g.add_edge(100, 100, 0, length=30.0, highway="residential")
    boundary = metre_box(-50, -100, 450, 400)
    n = prepare_network(g, estimate_utm_crs(boundary))
    m = compute_area_metrics(n, project_geometry(boundary, n.crs))
    assert m.raw["network_directness"] == pytest.approx(4050 / 4100, rel=REL)


def test_missing_street_count_is_computed(fixture_graph: nx.MultiDiGraph) -> None:
    g = fixture_graph.copy()
    for _, data in g.nodes(data=True):
        data.pop("street_count", None)
    boundary = metre_box(-50, -100, 450, 400)
    n = prepare_network(g, estimate_utm_crs(boundary))
    m = compute_area_metrics(n, project_geometry(boundary, n.crs))
    assert m.raw["avg_node_degree"] == pytest.approx(82 / 26, rel=1e-9)


def test_empty_graph_gives_none_except_zero_road_density() -> None:
    g = nx.MultiDiGraph(crs="EPSG:4326")
    boundary = metre_box(0, 0, 500, 500)
    n = prepare_network(g, estimate_utm_crs(boundary))
    m = compute_area_metrics(n, project_geometry(boundary, n.crs))
    assert m.raw["road_density"] == 0.0
    assert m.raw["intersection_density"] is None
    assert m.node_count == 0


def test_cell_confidence_rules() -> None:
    assert cell_confidence(1.0, 10, node_based=True) == 1.0
    assert cell_confidence(0.25, 5, node_based=True) == pytest.approx(0.25)
    assert cell_confidence(0.25, 5, node_based=False) == pytest.approx(0.5)
    assert cell_confidence(0.9, 0, node_based=True) == 0.0
    assert cell_confidence(0.5, 100, node_based=False) == 1.0


def test_area_confidence_scales_with_node_count() -> None:
    assert area_confidence(0) == 0.0
    assert area_confidence(50) == pytest.approx(0.5)
    assert area_confidence(5000) == 1.0
