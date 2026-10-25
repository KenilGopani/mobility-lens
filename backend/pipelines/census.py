"""Land-clipped place boundaries from the US Census cartographic boundary files.

Nominatim/OSM municipal polygons often include adjacent water (Foster City's includes San
Francisco Bay), which dilutes every per-km2 metric. The Census cartographic boundary files
(`cb_<vintage>_<state>_place_500k`) are clipped to the shoreline, so they describe land area.
The zip is downloaded once and cached under the repo-root `.cache/boundaries/` (git-ignored).
"""

import urllib.request
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon

from pipelines.osm import BoundaryResult
from pipelines.osm.fetch import REPO_ROOT

CACHE_DIR = REPO_ROOT / ".cache" / "boundaries"
VINTAGE = 2023
BASE_URL = "https://www2.census.gov/geo/tiger/GENZ{vintage}/shp/{name}.zip"

Downloader = Callable[[str, Path], None]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:
        fh.write(resp.read())
    tmp.replace(dest)


def fetch_census_boundary(
    name: str,
    *,
    state_fips: str = "06",
    geoid: str | None = None,
    vintage: int = VINTAGE,
    cache_dir: Path = CACHE_DIR,
    downloader: Downloader = download,
) -> BoundaryResult:
    """Select the place called `name` from the state's Census place file (EPSG:4326)."""
    stem = f"cb_{vintage}_{state_fips}_place_500k"
    zip_path = cache_dir / f"{stem}.zip"
    if not zip_path.is_file():
        downloader(BASE_URL.format(vintage=vintage, name=stem), zip_path)
    gdf = gpd.read_file(f"zip://{zip_path}")
    matches = gdf[gdf["NAME"].str.casefold() == name.casefold()]
    if geoid is not None:
        matches = matches[matches["GEOID"] == geoid]
    elif len(matches) > 1 and "LSAD" in matches.columns:
        # prefer the incorporated city (LSAD 25) over same-named census-designated places
        cities = matches[matches["LSAD"] == "25"]
        matches = cities if len(cities) == 1 else matches
    if matches.empty:
        raise ValueError(f"no place named {name!r} in {stem}")
    if len(matches) > 1:
        geoids = ", ".join(sorted(matches["GEOID"]))
        raise ValueError(f"place name {name!r} is ambiguous in {stem}: {geoids}")
    row = matches.iloc[0]
    row_gdf = gpd.GeoDataFrame(geometry=[row.geometry], crs=gdf.crs).to_crs(4326)
    geom: Polygon | MultiPolygon = row_gdf.geometry.iloc[0]
    place_geoid = str(row["GEOID"])
    props = {
        "source": f"census-cb-{vintage}:{place_geoid}",
        "geoid": place_geoid,
        "name": str(row["NAME"]),
        "census_file": f"{stem}.zip",
        "land_clipped": True,
    }
    return BoundaryResult(geometry=geom, query=name, properties=props)
