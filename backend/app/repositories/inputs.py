"""Plain input records handed to repositories (no ORM, no shapely)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class H3CellInput:
    h3_index: str
    resolution: int
    boundary_wkt: str  # POLYGON, EPSG:4326
    centroid_wkt: str  # POINT, EPSG:4326


@dataclass(frozen=True)
class RunCellInput:
    cell: H3CellInput
    overlap_ratio: float


@dataclass(frozen=True)
class CellMetricInput:
    h3_index: str
    metric_key: str
    raw_value: float | None = None
    normalized_value: float | None = None
    confidence: float | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AreaMetricInput:
    metric_key: str
    raw_value: float | None = None
    normalized_value: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in EPSG:4326 (lon/lat)."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
