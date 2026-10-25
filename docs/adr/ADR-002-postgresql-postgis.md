# ADR-002: PostgreSQL + PostGIS

**Status:** Accepted

## Context
The data is relational (areas, runs, metrics, scores) and spatial (boundaries, H3 polygons, bbox viewport queries). Integrity constraints and provenance matter.

## Decision
Use PostgreSQL 16 with PostGIS. Geometries are stored as EPSG:4326. Use Docker Compose locally and a dedicated test database for integration tests.

## Consequences
- Spatial predicates and GiST indexes are available for viewport queries.
- Constraints (CHECK, FK, composite keys) enforce data rules in the database.
- Requires Docker locally.

## Alternatives considered
- SQLite/SpatiaLite: weaker concurrency and tooling, and does not match a production-style stack.
- GeoParquet files only: no relational integrity or query layer for the API.
