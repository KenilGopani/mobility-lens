"""Boundary validation/repair and projected (metric) measurements."""

from dataclasses import dataclass

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity, make_valid

WGS84 = CRS.from_epsg(4326)


class InvalidGeometryError(ValueError):
    """The geometry cannot be used as an analysis boundary."""


@dataclass(frozen=True)
class RepairedGeometry:
    geometry: Polygon | MultiPolygon
    repaired: bool
    reason: str | None = None  # shapely's validity explanation when repaired


def _polygonal_parts(geom: BaseGeometry) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [] if geom.is_empty else [geom]
    if isinstance(geom, MultiPolygon):
        return [p for p in geom.geoms if not p.is_empty]
    if hasattr(geom, "geoms"):  # GeometryCollection from make_valid
        parts: list[Polygon] = []
        for g in geom.geoms:
            parts.extend(_polygonal_parts(g))
        return parts
    return []


def validate_boundary(geom: BaseGeometry) -> RepairedGeometry:
    """Return a valid (Multi)Polygon; invalid input is repaired with make_valid and flagged.

    Empty or non-polygonal input, or input whose repair leaves no area, is rejected.
    """
    if geom is None or geom.is_empty:
        raise InvalidGeometryError("boundary geometry is empty")
    if not isinstance(geom, Polygon | MultiPolygon):
        raise InvalidGeometryError(
            f"boundary must be Polygon or MultiPolygon, got {geom.geom_type}"
        )
    if geom.is_valid:
        return RepairedGeometry(geom, repaired=False)
    reason = explain_validity(geom)
    parts = [p for p in _polygonal_parts(make_valid(geom)) if p.area > 0]
    if not parts:
        raise InvalidGeometryError(f"boundary has no area after repair ({reason})")
    fixed: Polygon | MultiPolygon = parts[0] if len(parts) == 1 else MultiPolygon(parts)
    return RepairedGeometry(fixed, repaired=True, reason=reason)


def estimate_utm_crs(geom: BaseGeometry) -> CRS:
    """Local UTM CRS for a geometry given in EPSG:4326."""
    crs: CRS = gpd.GeoSeries([geom], crs=WGS84).estimate_utm_crs()
    return crs


def project_geometry(geom: BaseGeometry, crs: CRS, source_crs: CRS = WGS84) -> BaseGeometry:
    projected: BaseGeometry = gpd.GeoSeries([geom], crs=source_crs).to_crs(crs).iloc[0]
    return projected


def area_km2(geom: BaseGeometry, crs: CRS | None = None) -> float:
    """Area in km2 of an EPSG:4326 geometry, measured in `crs` (default: its local UTM)."""
    target = crs or estimate_utm_crs(geom)
    return float(project_geometry(geom, target).area) / 1_000_000.0
