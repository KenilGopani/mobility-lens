"""Regenerate drive_grid.graphml: `uv run python tests/fixtures/osm/make_fixture.py`.

Layout (metres east/north of ORIGIN; 1 unit = 100 m): a 5x5 grid (nodes 100..124, id = 100 +
row*5 + col), plus dead-end node 200 at (200, -50) attached to node 102 (row 0, col 2).

* every grid edge is 100 m long except (row1,col1)-(row1,col2), whose `length` is 150 m
  (circuity 1.5); the stub edge is 50 m
* top-row (row 4) horizontal edges are one-way, all others two-way (undirected view collapses)
* highway=residential (stub: service)
* name: all horizontal edges + vertical edges in cols 0, 2, 4 (32 of 41 physical edges)
* maxspeed: horizontal edges in rows 0-2 (12 of 41)
* lanes: vertical edges in col 2 + horizontal edges in row 2 (8 of 41)
* street_count: corners 2, other edge nodes 3 (node 102: 4), interior 4, stub 1
"""

import math
from pathlib import Path

import networkx as nx
import osmnx as ox

ORIGIN_LON, ORIGIN_LAT = -122.27, 37.55
M_LAT = 1 / 111_320.0
M_LON = 1 / (111_320.0 * math.cos(math.radians(ORIGIN_LAT)))


def node_id(row: int, col: int) -> int:
    return 100 + row * 5 + col


def build() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph(crs="EPSG:4326")
    for r in range(5):
        for c in range(5):
            g.add_node(
                node_id(r, c), x=ORIGIN_LON + c * 100 * M_LON, y=ORIGIN_LAT + r * 100 * M_LAT
            )
    g.add_node(200, x=ORIGIN_LON + 200 * M_LON, y=ORIGIN_LAT - 50 * M_LAT)

    def add(u: int, v: int, length: float, horizontal: bool, r: int, c: int, oneway: bool) -> None:
        attrs: dict[str, object] = {
            "osmid": u * 1000 + v,
            "highway": "residential",
            "length": length,
            "oneway": oneway,
        }
        if horizontal:
            attrs["name"] = f"Row {r} Street"
            if r <= 2:
                attrs["maxspeed"] = "25 mph"
            if r == 2:
                attrs["lanes"] = "2"
        else:
            if c in (0, 2, 4):
                attrs["name"] = f"Col {c} Avenue"
            if c == 2:
                attrs["lanes"] = "2"
        g.add_edge(u, v, 0, **attrs)
        if not oneway:
            g.add_edge(v, u, 0, **attrs)

    for r in range(5):
        for c in range(5):
            if c < 4:
                length = 150.0 if (r, c) == (1, 1) else 100.0
                add(node_id(r, c), node_id(r, c + 1), length, True, r, c, oneway=(r == 4))
            if r < 4:
                add(node_id(r, c), node_id(r + 1, c), 100.0, False, r, c, oneway=False)
    g.add_edge(102, 200, 0, osmid=999, highway="service", length=50.0, oneway=False)
    g.add_edge(200, 102, 0, osmid=999, highway="service", length=50.0, oneway=False)

    for n in g.nodes:
        g.nodes[n]["street_count"] = len(set(g.successors(n)) | set(g.predecessors(n)))
    return g


if __name__ == "__main__":
    out = Path(__file__).parent / "drive_grid.graphml"
    ox.save_graphml(build(), out)
    print(f"wrote {out}")
