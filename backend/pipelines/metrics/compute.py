"""Raw metric computation, exactly as defined in docs/scoring-model.md.

Conventions
-----------
* The network is the OSMnx drive graph viewed as undirected (reciprocal edges collapse), so each
  physical street counts once.
* A *region* is a projected (metre) polygon: an H3 cell clipped to the boundary, or the whole
  boundary. Nodes are "inside" when they intersect the region; an edge belongs to the region
  when part of it lies inside, and contributes its clipped share `f` of its `length`.
* Unavailable is None, never 0. `road_density` is 0.0 for a region with no roads (a genuine
  zero); the other metrics are None when there is nothing to average.
"""

from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import CRS
from shapely.geometry.base import BaseGeometry

METRIC_KEYS: tuple[str, ...] = (
    "intersection_density",
    "road_density",
    "avg_node_degree",
    "network_directness",
    "metadata_completeness",
)
NODE_BASED_METRICS: frozenset[str] = frozenset({"intersection_density", "avg_node_degree"})
METADATA_TAGS: tuple[str, ...] = ("maxspeed", "lanes", "name")

MIN_OVERLAP_FOR_FULL_CONFIDENCE = 0.5
NODES_FOR_FULL_CELL_CONFIDENCE = 10
NODES_FOR_FULL_AREA_CONFIDENCE = 100  # matches the DQ-004 default threshold
INTERSECTION_MIN_STREET_COUNT = 3


@dataclass(frozen=True)
class PreparedNetwork:
    """Projected undirected network ready for region queries."""

    crs: CRS
    nodes: gpd.GeoDataFrame  # street_count, geometry
    edges: gpd.GeoDataFrame  # length, straight, geom_length, has_<tag>..., geometry


@dataclass(frozen=True)
class RegionMetrics:
    raw: dict[str, float | None]
    confidence: dict[str, float | None]
    node_count: int
    edge_count: int
    area_km2: float
    details: dict[str, Any] = field(default_factory=dict)


def _has_value(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, list | tuple | set):
        return len(v) > 0
    if isinstance(v, str):
        return v.strip() != ""
    return not bool(pd.isna(v))


def prepare_network(graph: nx.MultiDiGraph, crs: CRS) -> PreparedNetwork:
    """Undirected, projected node/edge frames with precomputed per-edge quantities."""
    if graph.number_of_nodes() == 0:
        empty_nodes = gpd.GeoDataFrame({"street_count": []}, geometry=[], crs=crs)
        cols: dict[str, list[Any]] = {
            "length": [],
            "straight": [],
            "geom_length": [],
            **{f"has_{t}": [] for t in METADATA_TAGS},
        }
        return PreparedNetwork(crs, empty_nodes, gpd.GeoDataFrame(cols, geometry=[], crs=crs))

    if any("street_count" not in d for _, d in graph.nodes(data=True)):
        counts = ox.stats.count_streets_per_node(graph)
        nx.set_node_attributes(graph := graph.copy(), counts, "street_count")

    undirected = ox.convert.to_undirected(graph)
    nodes, edges = ox.graph_to_gdfs(undirected)
    nodes = nodes.to_crs(crs)[["street_count", "geometry"]].copy()
    edges = edges.to_crs(crs)

    u = edges.index.get_level_values("u")
    v = edges.index.get_level_values("v")
    px = nodes.geometry.x.reindex(u).to_numpy(), nodes.geometry.y.reindex(u).to_numpy()
    qx = nodes.geometry.x.reindex(v).to_numpy(), nodes.geometry.y.reindex(v).to_numpy()
    straight = np.hypot(px[0] - qx[0], px[1] - qx[1])
    length = edges["length"].astype(float).to_numpy()
    out = gpd.GeoDataFrame(
        {
            "length": length,
            # straight-line distance can't exceed path length; guards UTM scale-factor noise
            "straight": np.minimum(straight, length),
            "geom_length": edges.geometry.length.to_numpy(),
            "is_loop": (u == v),
        },
        geometry=edges.geometry.to_numpy(),
        crs=crs,
    )
    for tag in METADATA_TAGS:
        col = edges[tag] if tag in edges.columns else pd.Series(None, index=edges.index)
        out[f"has_{tag}"] = col.map(_has_value).to_numpy()
    return PreparedNetwork(crs, nodes, out)


def _edge_shares(net: PreparedNetwork, region: BaseGeometry) -> pd.DataFrame:
    """Edges touching the region with the clipped share f in (0, 1] of each."""
    edges = net.edges
    if len(edges) == 0:
        return edges.iloc[0:0].assign(share=pd.Series(dtype=float))
    idx = edges.sindex.query(region, predicate="intersects")
    cand = edges.iloc[np.sort(idx)]
    if len(cand) == 0:
        return cand.assign(share=pd.Series(dtype=float))
    inside = cand.geometry.intersection(region).length.to_numpy()
    full = cand["geom_length"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(full > 0, inside / full, 0.0)
    cand = cand.assign(share=np.clip(share, 0.0, 1.0))
    return cand[cand["share"] > 0]


def _compute_raw(
    net: PreparedNetwork, region: BaseGeometry
) -> tuple[dict[str, float | None], int, int, float]:
    area = float(region.area) / 1_000_000.0
    if len(net.nodes):
        nidx = net.nodes.sindex.query(region, predicate="intersects")
        nodes_in = net.nodes.iloc[np.sort(nidx)]
    else:
        nodes_in = net.nodes
    edges_in = _edge_shares(net, region)
    node_count, edge_count = len(nodes_in), len(edges_in)

    raw: dict[str, float | None] = dict.fromkeys(METRIC_KEYS)
    if node_count and area > 0:
        sc = nodes_in["street_count"].astype(float)
        raw["intersection_density"] = float((sc >= INTERSECTION_MIN_STREET_COUNT).sum() / area)
    if node_count:
        raw["avg_node_degree"] = float(nodes_in["street_count"].astype(float).mean())
    if area > 0:
        clipped_km = float((edges_in["length"] * edges_in["share"]).sum()) / 1000.0
        raw["road_density"] = clipped_km / area
    if edge_count:
        usable = edges_in[~edges_in["is_loop"] & (edges_in["length"] > 0)]
        path = float((usable["length"] * usable["share"]).sum())
        straight = float((usable["straight"] * usable["share"]).sum())
        if path > 0:
            raw["network_directness"] = straight / path
        raw["metadata_completeness"] = float(
            np.mean([edges_in[f"has_{t}"].mean() for t in METADATA_TAGS])
        )
    return raw, node_count, edge_count, area


def cell_confidence(overlap_ratio: float, node_count: int, *, node_based: bool) -> float:
    """min(1, overlap/0.5), times min(1, node_count/10) for node-based metrics."""
    c = min(1.0, max(0.0, overlap_ratio) / MIN_OVERLAP_FOR_FULL_CONFIDENCE)
    if node_based:
        c *= min(1.0, node_count / NODES_FOR_FULL_CELL_CONFIDENCE)
    return c


def area_confidence(node_count: int) -> float:
    """Whole-area sample-size confidence: min(1, nodes / 100) (the DQ-004 threshold)."""
    return min(1.0, node_count / NODES_FOR_FULL_AREA_CONFIDENCE)


def compute_cell_metrics(
    net: PreparedNetwork, region: BaseGeometry, *, overlap_ratio: float
) -> RegionMetrics:
    """Metrics for one H3 cell already clipped to the boundary (projected polygon)."""
    raw, nodes, edges, area = _compute_raw(net, region)
    conf: dict[str, float | None] = {
        k: None
        if raw[k] is None
        else cell_confidence(overlap_ratio, nodes, node_based=k in NODE_BASED_METRICS)
        for k in METRIC_KEYS
    }
    return RegionMetrics(
        raw, conf, nodes, edges, area, {"overlap_ratio": overlap_ratio, "area_km2": area}
    )


def compute_area_metrics(net: PreparedNetwork, boundary: BaseGeometry) -> RegionMetrics:
    """Metrics for the whole boundary (projected polygon), computed directly, not from cells."""
    raw, nodes, edges, area = _compute_raw(net, boundary)
    conf: dict[str, float | None] = {
        k: None if raw[k] is None else area_confidence(nodes) for k in METRIC_KEYS
    }
    return RegionMetrics(raw, conf, nodes, edges, area, {"area_km2": area})
