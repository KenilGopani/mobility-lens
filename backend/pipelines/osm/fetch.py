"""Boundary geocoding and drive-network download through osmnx, with an on-disk HTTP cache.

osmnx caches every Overpass/Nominatim response under `.cache/osm` (git-ignored), so a repeated
run with the same query does not re-download. The two `fetch_*` functions take the osmnx
callables as parameters so tests can inject fixtures and never touch the network.
"""

import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / ".cache" / "osm"
NETWORK_TYPE = "drive"
FETCH_ATTEMPTS = 4
RETRY_BASE_SECONDS = 20.0


@dataclass(frozen=True)
class BoundaryResult:
    geometry: Polygon | MultiPolygon
    query: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class NetworkSnapshot:
    graph: nx.MultiDiGraph
    source_metadata: dict[str, Any]


def configure_osmnx_cache(cache_dir: Path = CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(cache_dir)
    ox.settings.log_console = False
    if endpoint := os.environ.get("OVERPASS_URL"):  # e.g. a mirror when the default is at capacity
        ox.settings.overpass_url = endpoint
    return cache_dir


def fetch_boundary(
    query: str,
    *,
    geocoder: Callable[..., gpd.GeoDataFrame] = ox.geocode_to_gdf,
    cache_dir: Path = CACHE_DIR,
) -> BoundaryResult:
    """Geocode `query` to its OSM polygon boundary (EPSG:4326)."""
    configure_osmnx_cache(cache_dir)
    gdf = geocoder(query)
    polys = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if polys.empty:
        raise ValueError(f"geocoding {query!r} returned no Polygon/MultiPolygon boundary")
    row = polys.iloc[0]
    props = {
        k: (None if row.get(k) is None else str(row.get(k)))
        for k in ("osm_type", "osm_id", "display_name", "name", "class", "type")
        if k in polys.columns
    }
    geom: Polygon | MultiPolygon = row.geometry
    return BoundaryResult(geometry=geom, query=query, properties=props)


def snapshot_from_graph(
    graph: nx.MultiDiGraph,
    *,
    query: str,
    polygon: BaseGeometry,
    cache_dir: Path | None = CACHE_DIR,
    fetched_at: datetime | None = None,
    origin: str = "overpass",
) -> NetworkSnapshot:
    """Wrap a graph with the provenance recorded in analysis_runs.source_metadata."""
    cache_key = hashlib.sha256(
        f"{NETWORK_TYPE}|{ox.__version__}|{polygon.wkt}".encode()
    ).hexdigest()[:16]
    metadata: dict[str, Any] = {
        "source": origin,
        "query": query,
        "network_type": NETWORK_TYPE,
        "simplify": True,
        "osmnx_version": ox.__version__,
        "fetched_at": (fetched_at or datetime.now(UTC)).isoformat(),
        "cache_key": cache_key,
        "cache_dir": None if cache_dir is None else str(cache_dir),
        "polygon_bounds": [round(b, 6) for b in polygon.bounds],
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    return NetworkSnapshot(graph, metadata)


def fetch_drive_network(
    polygon: BaseGeometry,
    *,
    query: str,
    graph_factory: Callable[..., nx.MultiDiGraph] = ox.graph_from_polygon,
    cache_dir: Path = CACHE_DIR,
    attempts: int = FETCH_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> NetworkSnapshot:
    """Download the simplified drivable network inside `polygon` (EPSG:4326).

    The public Overpass servers are often at capacity, so failures are retried with exponential
    backoff. Responses that succeeded are served from the osmnx cache on later calls.
    """
    configure_osmnx_cache(cache_dir)
    for attempt in range(1, attempts + 1):
        try:
            graph = graph_factory(polygon, network_type=NETWORK_TYPE, simplify=True)
            break
        except Exception:
            if attempt == attempts:
                raise
            sleep(RETRY_BASE_SECONDS * 2 ** (attempt - 1))
    return snapshot_from_graph(graph, query=query, polygon=polygon, cache_dir=cache_dir)


def load_graph_fixture(path: Path) -> nx.MultiDiGraph:
    graph: nx.MultiDiGraph = ox.load_graphml(path)
    return graph
