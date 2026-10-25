import math

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box

from pipelines.spatial import (
    InvalidGeometryError,
    area_km2,
    cell_overlaps,
    cell_polygon,
    cover_cells,
    estimate_utm_crs,
    point_to_cell,
    validate_boundary,
)

# ~2 km x ~2 km around Foster City
FC = box(-122.28, 37.55, -122.26, 37.57)


def test_point_converts_to_expected_h3_index() -> None:
    # San Francisco City Hall area; canonical H3 docs example at resolution 9.
    assert point_to_cell(37.7749, -122.4194, 9) == "89283082803ffff"


def test_cover_is_non_empty_and_contains_interior_point() -> None:
    cells = cover_cells(FC, 9)
    assert len(cells) > 0
    assert point_to_cell(37.56, -122.27, 9) in cells


def test_cover_includes_boundary_cells_whose_center_is_outside() -> None:
    cells = set(cover_cells(FC, 9))
    # every cell that overlaps the polygon must be present
    centered = {c for c in cells if FC.contains(cell_polygon(c).centroid)}
    assert len(cells) > len(centered)


def test_cell_polygon_is_valid_hexagon_in_lonlat() -> None:
    poly = cell_polygon("89283082803ffff")
    assert poly.is_valid
    assert len(poly.exterior.coords) == 7  # 6 vertices, closed
    x, y = poly.centroid.x, poly.centroid.y
    assert -122.5 < x < -122.3
    assert 37.7 < y < 37.8


def test_overlap_in_unit_interval_and_one_for_interior_cells() -> None:
    cells = cover_cells(FC, 9)
    overlaps = cell_overlaps(FC, cells)
    assert set(overlaps) == set(cells)
    assert all(0.0 < v <= 1.0 for v in overlaps.values())
    assert any(math.isclose(v, 1.0, abs_tol=1e-9) for v in overlaps.values())
    assert any(v < 1.0 for v in overlaps.values())
    for c, v in overlaps.items():
        if FC.contains(cell_polygon(c)):
            assert v == pytest.approx(1.0, abs=1e-9)


def test_overlap_zero_for_disjoint_cell() -> None:
    far = point_to_cell(37.7749, -122.4194, 9)
    assert cell_overlaps(FC, [far])[far] == 0.0


def test_overlaps_sum_matches_boundary_area() -> None:
    cells = cover_cells(FC, 9)
    overlaps = cell_overlaps(FC, cells)
    crs = estimate_utm_crs(FC)
    total_cell_area = sum(v * area_km2(cell_polygon(c), crs) for c, v in overlaps.items())
    assert total_cell_area == pytest.approx(area_km2(FC, crs), rel=1e-3)


def test_utm_crs_is_zone_10n_for_bay_area() -> None:
    crs = estimate_utm_crs(FC)
    assert crs.to_epsg() in (32610, 26910)
    assert crs.axis_info[0].unit_name == "metre"


def test_area_known_square() -> None:
    # 0.01 deg lat ~ 1.1132 km; 0.01 deg lon at 37.5 N ~ 0.8832 km => ~0.9833 km2
    sq = box(-122.0, 37.5, -121.99, 37.51)
    expected = 0.01 * 111.2 * (0.01 * 111.32 * math.cos(math.radians(37.505)))
    assert area_km2(sq) == pytest.approx(expected, rel=0.01)


def test_valid_polygon_passes_unrepaired() -> None:
    r = validate_boundary(FC)
    assert r.repaired is False
    assert r.geometry.equals(FC)


def test_bowtie_is_repaired_and_flagged() -> None:
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid
    r = validate_boundary(bowtie)
    assert r.repaired is True
    assert r.geometry.is_valid
    assert isinstance(r.geometry, Polygon | MultiPolygon)
    assert r.geometry.area > 0


def test_repair_discards_non_polygonal_parts() -> None:
    # collapsed ring (zero area) + nothing else -> rejected
    degenerate = Polygon([(0, 0), (1, 1), (2, 2), (0, 0)])
    with pytest.raises(InvalidGeometryError):
        validate_boundary(degenerate)


@pytest.mark.parametrize(
    "geom",
    [
        Polygon(),
        Point(0, 0),
        LineString([(0, 0), (1, 1)]),
        GeometryCollection(),
    ],
)
def test_empty_or_non_polygon_rejected(geom: object) -> None:
    with pytest.raises(InvalidGeometryError):
        validate_boundary(geom)  # type: ignore[arg-type]
