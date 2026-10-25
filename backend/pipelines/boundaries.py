"""Fetch a service-area boundary from OSM (Nominatim) and write it as GeoJSON."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, Polygon, mapping

from pipelines.osm import CACHE_DIR, BoundaryResult, fetch_boundary
from pipelines.spatial import validate_boundary

BOUNDARY_DIR = Path(__file__).resolve().parent.parent / "data" / "boundaries"
SIMPLIFY_TOLERANCE_DEG = 1e-5  # ~1 m: removes redundant vertices, keeps the outline
COORD_PRECISION = 1e-6  # ~0.1 m


def build_feature(
    result: BoundaryResult, *, slug: str, tolerance: float = SIMPLIFY_TOLERANCE_DEG
) -> dict[str, Any]:
    """GeoJSON Feature (EPSG:4326 Polygon/MultiPolygon), validated and lightly simplified."""
    checked = validate_boundary(result.geometry)
    simplified = checked.geometry.simplify(tolerance, preserve_topology=True)
    snapped = shapely.set_precision(simplified, COORD_PRECISION)
    final = validate_boundary(snapped)
    geom: Polygon | MultiPolygon = final.geometry
    props = {
        "slug": slug,
        "query": result.query,
        "repaired": checked.repaired or final.repaired,
        "simplify_tolerance_deg": tolerance,
        **result.properties,
    }
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def write_boundary(
    slug: str,
    query: str,
    *,
    out_dir: Path = BOUNDARY_DIR,
    geocoder: Callable[..., gpd.GeoDataFrame] | None = None,
    cache_dir: Path = CACHE_DIR,
) -> Path:
    kwargs: dict[str, Any] = {"cache_dir": cache_dir}
    if geocoder is not None:
        kwargs["geocoder"] = geocoder
    result = fetch_boundary(query, **kwargs)
    feature = build_feature(result, slug=slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.geojson"
    path.write_text(json.dumps(feature, indent=1, sort_keys=True) + "\n")
    return path
