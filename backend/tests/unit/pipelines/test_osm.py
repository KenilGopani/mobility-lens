from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pytest
from shapely.geometry import MultiPolygon, Point, box

from pipelines.osm import (
    CACHE_DIR,
    fetch_boundary,
    fetch_drive_network,
    load_graph_fixture,
    snapshot_from_graph,
)
from tests.unit.pipelines.conftest import FIXTURE, metre_box


def test_cache_dir_is_repo_root_dot_cache_osm_and_git_ignored() -> None:
    assert CACHE_DIR.parts[-2:] == (".cache", "osm")
    root = CACHE_DIR.parents[1]
    assert "\n.cache/" in (root / ".gitignore").read_text()


def test_fixture_loads() -> None:
    g = load_graph_fixture(FIXTURE)
    assert g.number_of_nodes() == 26
    assert all("street_count" in d for _, d in g.nodes(data=True))


def test_fetch_drive_network_uses_injected_factory(
    fixture_graph: nx.MultiDiGraph, tmp_path: Path
) -> None:
    calls: list[dict[str, Any]] = []

    def factory(polygon: Any, **kwargs: Any) -> nx.MultiDiGraph:
        calls.append({"polygon": polygon, **kwargs})
        return fixture_graph

    poly = metre_box(-50, -100, 450, 400)
    snap = fetch_drive_network(
        poly, query="Fixture Town", graph_factory=factory, cache_dir=tmp_path
    )
    assert calls == [{"polygon": poly, "network_type": "drive", "simplify": True}]
    md = snap.source_metadata
    assert md["query"] == "Fixture Town"
    assert md["osmnx_version"] == ox.__version__
    assert md["node_count"] == fixture_graph.number_of_nodes()
    assert md["edge_count"] == fixture_graph.number_of_edges()
    assert md["network_type"] == "drive"
    assert md["fetched_at"]
    assert md["cache_dir"] == str(tmp_path)
    assert ox.settings.cache_folder == str(tmp_path)
    assert ox.settings.use_cache is True


def test_fetch_drive_network_retries_then_succeeds(
    fixture_graph: nx.MultiDiGraph, tmp_path: Path
) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def flaky(polygon: Any, **kwargs: Any) -> nx.MultiDiGraph:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("502")
        return fixture_graph

    snap = fetch_drive_network(
        box(0, 0, 1, 1), query="q", graph_factory=flaky, cache_dir=tmp_path, sleep=sleeps.append
    )
    assert len(attempts) == 3
    assert sleeps == [20.0, 40.0]
    assert snap.source_metadata["node_count"] == 26


def test_fetch_drive_network_gives_up(tmp_path: Path) -> None:
    def always(polygon: Any, **kwargs: Any) -> nx.MultiDiGraph:
        raise RuntimeError("502")

    with pytest.raises(RuntimeError, match="502"):
        fetch_drive_network(
            box(0, 0, 1, 1),
            query="q",
            graph_factory=always,
            cache_dir=tmp_path,
            attempts=2,
            sleep=lambda s: None,
        )


def test_cache_key_is_deterministic_per_polygon(fixture_graph: nx.MultiDiGraph) -> None:
    a = snapshot_from_graph(fixture_graph, query="q", polygon=box(0, 0, 1, 1)).source_metadata
    b = snapshot_from_graph(fixture_graph, query="q", polygon=box(0, 0, 1, 1)).source_metadata
    c = snapshot_from_graph(fixture_graph, query="q", polygon=box(0, 0, 2, 1)).source_metadata
    assert a["cache_key"] == b["cache_key"] != c["cache_key"]


def test_fetch_boundary_picks_polygon_row(tmp_path: Path) -> None:
    gdf = gpd.GeoDataFrame(
        {"osm_id": [1, 2], "osm_type": ["node", "relation"], "display_name": ["pt", "area"]},
        geometry=[Point(0, 0), box(0, 0, 1, 1)],
        crs=4326,
    )
    res = fetch_boundary("Somewhere", geocoder=lambda q: gdf, cache_dir=tmp_path)
    assert res.geometry.equals(box(0, 0, 1, 1))
    assert res.properties["osm_id"] == "2"
    assert res.query == "Somewhere"


def test_fetch_boundary_rejects_point_only(tmp_path: Path) -> None:
    gdf = gpd.GeoDataFrame({"osm_id": [1]}, geometry=[Point(0, 0)], crs=4326)
    with pytest.raises(ValueError, match="no Polygon"):
        fetch_boundary("Nowhere", geocoder=lambda q: gdf, cache_dir=tmp_path)


@pytest.mark.live_data
def test_live_foster_city_boundary() -> None:
    res = fetch_boundary("Foster City, California, USA")
    assert isinstance(res.geometry, MultiPolygon) or res.geometry.area > 0
