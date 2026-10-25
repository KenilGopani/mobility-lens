from pathlib import Path

import networkx as nx
import osmnx as ox
import pytest
from shapely.geometry import Polygon, box

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "osm" / "drive_grid.graphml"

# fixture geometry: grid origin and metre -> degree conversion (see make_fixture.py)
LON0, LAT0 = -122.27, 37.55
M_LAT = 1 / 111_320.0
M_LON = 1.0 / 88_237.4  # 111320 * cos(37.55 deg), rounded; only used to place test boxes


def metre_box(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """Box in EPSG:4326 given metres east/north of the fixture grid origin."""
    return box(LON0 + x0 * M_LON, LAT0 + y0 * M_LAT, LON0 + x1 * M_LON, LAT0 + y1 * M_LAT)


@pytest.fixture(scope="session")
def fixture_graph() -> nx.MultiDiGraph:
    return ox.load_graphml(FIXTURE)
