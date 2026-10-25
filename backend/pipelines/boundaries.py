"""Fetch a service-area boundary (Census land-clipped by default, or OSM) and write GeoJSON."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, Polygon, mapping

from pipelines.census import Downloader, fetch_census_boundary
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
    cache_dir: Path | None = None,
    source: str = "osm",
    downloader: Downloader | None = None,
    state_fips: str = "06",
    geoid: str | None = None,
) -> Path:
    if source == "census":
        census_kwargs: dict[str, Any] = {"state_fips": state_fips, "geoid": geoid}
        if cache_dir is not None:
            census_kwargs["cache_dir"] = cache_dir
        if downloader is not None:
            census_kwargs["downloader"] = downloader
        result = fetch_census_boundary(query, **census_kwargs)
    elif source == "osm":
        kwargs: dict[str, Any] = {"cache_dir": cache_dir or CACHE_DIR}
        if geocoder is not None:
            kwargs["geocoder"] = geocoder
        osm = fetch_boundary(query, **kwargs)
        osm_id = osm.properties.get("osm_id")
        tag = f"osm-nominatim:{osm_id}" if osm_id else "osm-nominatim"
        result = BoundaryResult(osm.geometry, osm.query, {**osm.properties, "source": tag})
    else:
        raise ValueError(f"unknown boundary source {source!r} (expected 'census' or 'osm')")
    feature = build_feature(result, slug=slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.geojson"
    path.write_text(json.dumps(feature, indent=1, sort_keys=True) + "\n")
    return path
