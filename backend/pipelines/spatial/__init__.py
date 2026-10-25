"""Pure spatial helpers: geometry validation, projected areas, H3 covers and overlaps."""

from pipelines.spatial.geometry import (
    InvalidGeometryError,
    RepairedGeometry,
    area_km2,
    estimate_utm_crs,
    project_geometry,
    validate_boundary,
)
from pipelines.spatial.h3_cells import (
    cell_overlaps,
    cell_polygon,
    cell_regions,
    cover_cells,
    point_to_cell,
)

__all__ = [
    "InvalidGeometryError",
    "RepairedGeometry",
    "area_km2",
    "cell_overlaps",
    "cell_polygon",
    "cell_regions",
    "cover_cells",
    "estimate_utm_crs",
    "point_to_cell",
    "project_geometry",
    "validate_boundary",
]
