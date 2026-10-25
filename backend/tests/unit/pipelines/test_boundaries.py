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


def _census_zip(dest: Path) -> None:
    import shutil

    shp_dir = dest.parent / "shp"
    gdf = gpd.GeoDataFrame(
        {"NAME": ["Foster City", "Other"], "GEOID": ["0625338", "0600001"]},
        geometry=[box(0, 0, 1, 1), box(2, 2, 3, 3)],
        crs=4269,
    )
    gdf.to_file(shp_dir / "p.shp")
    shutil.make_archive(str(dest.with_suffix("")), "zip", shp_dir)


def test_census_boundary_selects_place_and_records_provenance(tmp_path: Path) -> None:
    calls: list[str] = []

    def downloader(url: str, dest: Path) -> None:
        calls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        (dest.parent / "shp").mkdir(exist_ok=True)
        _census_zip(dest)

    kw = {"out_dir": tmp_path / "out", "cache_dir": tmp_path / "cache", "downloader": downloader}
    path = write_boundary("fc", "foster city", source="census", **kw)  # type: ignore[arg-type]
    props = json.loads(path.read_text())["properties"]
    assert props["source"] == "census-cb-2023:0625338"
    assert props["land_clipped"] is True
    assert "GENZ2023/shp/cb_2023_06_place_500k.zip" in calls[0]
    write_boundary("fc", "Foster City", source="census", **kw)  # type: ignore[arg-type]
    assert len(calls) == 1  # cached zip reused


def test_census_unknown_place_is_error(tmp_path: Path) -> None:
    import pytest

    def downloader(url: str, dest: Path) -> None:
        (dest.parent / "shp").mkdir(parents=True, exist_ok=True)
        _census_zip(dest)

    with pytest.raises(ValueError, match="no place named"):
        write_boundary(
            "x", "Nowhere", out_dir=tmp_path, cache_dir=tmp_path / "c", source="census",
            downloader=downloader,
        )  # fmt: skip


def test_osm_source_is_recorded(tmp_path: Path) -> None:
    path = write_boundary(
        "demo", "Demo", out_dir=tmp_path, geocoder=lambda q: _gdf(box(0, 0, 1, 1)), source="osm"
    )
    assert json.loads(path.read_text())["properties"]["source"] == "osm-nominatim:42"


def test_cli_fetch_boundary_defaults_to_census() -> None:
    out = CliRunner().invoke(app, ["fetch-boundary", "--help"]).stdout
    assert "--source" in out and "census" in out


def test_census_ambiguous_name_prefers_city_or_geoid(tmp_path: Path) -> None:
    import shutil

    import pytest

    def downloader(url: str, dest: Path) -> None:
        shp = dest.parent / "shp"
        shp.mkdir(parents=True, exist_ok=True)
        gdf = gpd.GeoDataFrame(
            {"NAME": ["Twin", "Twin"], "GEOID": ["1", "2"], "LSAD": ["25", "57"]},
            geometry=[box(0, 0, 1, 1), box(5, 5, 6, 6)],
            crs=4269,
        )
        gdf.to_file(shp / "p.shp")
        shutil.make_archive(str(dest.with_suffix("")), "zip", shp)

    kw = {"cache_dir": tmp_path / "c", "downloader": downloader, "source": "census"}
    path = write_boundary("t", "Twin", out_dir=tmp_path, **kw)  # type: ignore[arg-type]
    assert json.loads(path.read_text())["properties"]["geoid"] == "1"
    path = write_boundary("t", "Twin", out_dir=tmp_path, geoid="2", **kw)  # type: ignore[arg-type]
    assert json.loads(path.read_text())["properties"]["geoid"] == "2"
    with pytest.raises(ValueError, match="no place"):
        write_boundary("t", "Twin", out_dir=tmp_path, geoid="9", **kw)  # type: ignore[arg-type]
