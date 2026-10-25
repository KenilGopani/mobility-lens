import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, box
from typer.testing import CliRunner

from cli.__main__ import app
from pipelines.boundaries import write_boundary


def _gdf(geom: Polygon) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"osm_id": [42], "osm_type": ["relation"]}, geometry=[geom], crs=4326)


def test_write_boundary_produces_seedable_geojson(tmp_path: Path) -> None:
    # redundant collinear vertex is removed by the light simplification
    geom = Polygon([(0, 0), (0.5, 0.0000001), (1, 0), (1, 1), (0, 1)])
    path = write_boundary("demo", "Demo", out_dir=tmp_path, geocoder=lambda q: _gdf(geom))
    assert path == tmp_path / "demo.geojson"
    doc = json.loads(path.read_text())
    assert doc["type"] == "Feature"
    assert doc["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert doc["properties"]["slug"] == "demo"
    assert doc["properties"]["osm_id"] == "42"
    assert len(doc["geometry"]["coordinates"][0]) == 5  # 4 corners, closed


def test_write_boundary_repairs_and_flags_invalid(tmp_path: Path) -> None:
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    path = write_boundary("bow", "Bow", out_dir=tmp_path, geocoder=lambda q: _gdf(bowtie))
    assert json.loads(path.read_text())["properties"]["repaired"] is True


def test_boundary_file_is_read_by_seed(tmp_path: Path) -> None:
    from cli.seed import _read_geometry

    path = write_boundary("ok", "Ok", out_dir=tmp_path, geocoder=lambda q: _gdf(box(0, 0, 1, 1)))
    assert _read_geometry(path)["type"] == "Polygon"


def test_new_commands_registered() -> None:
    out = CliRunner().invoke(app, ["--help"]).stdout
    assert "analyze-area" in out
    assert "fetch-boundary" in out
