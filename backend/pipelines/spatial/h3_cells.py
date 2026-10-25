"""H3 cell cover and boundary overlap (overlap is measured in a projected CRS)."""

import geopandas as gpd
import h3
from pyproj import CRS
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from pipelines.spatial.geometry import WGS84, estimate_utm_crs


def point_to_cell(lat: float, lng: float, resolution: int) -> str:
    return str(h3.latlng_to_cell(lat, lng, resolution))


def cell_polygon(h3_index: str) -> Polygon:
    """Cell boundary as a lon/lat (x=lng, y=lat) polygon."""
    ring = [(lng, lat) for lat, lng in h3.cell_to_boundary(h3_index)]
    return Polygon(ring)


def cover_cells(geom: BaseGeometry, resolution: int) -> list[str]:
    """Every cell at `resolution` that intersects the (EPSG:4326) polygon, sorted.

    h3.geo_to_cells returns cells whose *centre* lies inside; boundary cells whose centre is
    just outside would be missed, so the one-ring neighbours are added and kept only if they
    actually intersect the polygon.
    """
    seeds = set(h3.geo_to_cells(geom, resolution))
    candidates = set(seeds)
    for c in seeds:
        candidates.update(h3.grid_ring(c, 1))
    prepared = prep(geom)
    return sorted(c for c in candidates if c in seeds or prepared.intersects(cell_polygon(c)))


def cell_regions(
    boundary: BaseGeometry, cells: list[str], crs: CRS | None = None
) -> dict[str, tuple[BaseGeometry, float]]:
    """Per cell: (cell clipped to the boundary, in the projected CRS; overlap ratio in [0, 1])."""
    if not cells:
        return {}
    target = crs or estimate_utm_crs(boundary)
    boundary_p = gpd.GeoSeries([boundary], crs=WGS84).to_crs(target).iloc[0]
    polys = gpd.GeoSeries([cell_polygon(c) for c in cells], crs=WGS84).to_crs(target)
    clipped = polys.intersection(boundary_p)
    ratio = (clipped.area / polys.area).clip(0.0, 1.0)
    return {c: (g, float(r)) for c, g, r in zip(cells, clipped, ratio, strict=True)}


def cell_overlaps(
    boundary: BaseGeometry, cells: list[str], crs: CRS | None = None
) -> dict[str, float]:
    """Share of each cell's area lying inside the boundary, in [0, 1], via a projected CRS."""
    return {c: r for c, (_, r) in cell_regions(boundary, cells, crs).items()}
