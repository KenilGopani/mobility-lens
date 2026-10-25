# ADR-004: H3 as the spatial aggregation unit

**Status:** Accepted

## Context
Comparing areas of different shapes and sizes needs a uniform unit. Map display needs cells that are cheap to render and query.

## Decision
Use H3 hexagonal cells at a configurable resolution, default 9 (about 0.1 km2 per cell). Cells are clipped to the service-area boundary for metric computation, with `overlap_ratio` stored and used to reduce confidence for sliver cells. Area-level metrics are computed on the whole boundary, not as a mean of cell values.

## Amendment: land-clipped Census boundaries
The service-area boundary that H3 cells cover is a US Census cartographic boundary (`cb_2023_<state>_place_500k`, clipped to the shoreline), not an OSM/Nominatim polygon. The OSM polygon for Foster City includes San Francisco Bay (49.76 km2 against roughly 11 km2 of land), which diluted densities and produced hundreds of mostly-water cells. This supersedes the earlier assumption that boundaries are fetched from OSM. `fetch-boundary --source census` is the default; `--source osm` remains available. Provenance is stored in `service_areas.source` (e.g. `census-cb-2023:0625338`). Census files are downloaded once and cached in the git-ignored `.cache/boundaries/`. The limitation is US-only coverage; other countries would need an equivalent land-clipped source.

## Consequences
- Uniform comparison units and simple viewport queries.
- Resolution is a parameter recorded on each run. Changing it produces a new run.
- Edge cells at the boundary are noisier, which is handled through the confidence value rather than being hidden.

## Alternatives considered
- Square grids: distorted adjacency and no standard indexing.
- Census tracts: coverage differs by region and does not generalize to other places.
