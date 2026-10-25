# ADR-004: H3 as the spatial aggregation unit

**Status:** Accepted

## Context
Comparing areas of different shapes and sizes needs a uniform unit. Map display needs cells that are cheap to render and query.

## Decision
Use H3 hexagonal cells at a configurable resolution, default 9 (about 0.1 km2 per cell). Cells are clipped to the service-area boundary for metric computation, with `overlap_ratio` stored and used to reduce confidence for sliver cells. Area-level metrics are computed on the whole boundary, not as a mean of cell values.

## Consequences
- Uniform comparison units and simple viewport queries.
- Resolution is a parameter recorded on each run. Changing it produces a new run.
- Edge cells at the boundary are noisier, which is handled through the confidence value rather than being hidden.

## Alternatives considered
- Square grids: distorted adjacency and no standard indexing.
- Census tracts: coverage differs by region and does not generalize to other places.
