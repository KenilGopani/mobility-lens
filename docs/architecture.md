# Architecture

## Business decision

Rank candidate mobility service areas and explain the ranking: evidence, assumptions, risks, and data reliability.

## Components

```text
Public data (OSM via OSMnx)
        |
        v
Batch CLI pipeline (Typer)  --writes-->  PostgreSQL + PostGIS
                                              |
                                              v
                                   FastAPI read API (/api/v1)
                                              |
                                              v
                      React + TypeScript + MapLibre GL + Plotly
```

| Component | Responsibility | Must not |
|---|---|---|
| `backend/pipelines` | Download/cache OSM, build graphs, H3 cells, compute raw metrics | Be called from an HTTP request |
| `backend/app/scoring` | Pure functions: normalization, weighted score, confidence | Touch the DB or network |
| `backend/app/quality` | Pure data-quality rule functions returning findings | Touch the DB |
| `backend/app/repositories` | All SQL / ORM access | Contain business rules |
| `backend/app/services` | Orchestrate repositories + pure logic for API use cases | Parse HTTP |
| `backend/app/api/v1` | Validation, serialization, error mapping | Contain SQL or scoring math |
| `backend/cli` | Typer commands: seed, analyze-area, analyze-all | Duplicate pipeline logic |
| `frontend` | Presentation, client state, what-if interaction | Re-implement scoring on the server's behalf (see below) |

## Pipeline stages (per service area)

1. Create `analysis_runs` row (`running`).
2. Load boundary; validate/repair geometry; project to a local UTM CRS (`GeoDataFrame.estimate_utm_crs`).
3. Fetch drivable network via OSMnx; cache the raw response on disk (`.cache/osm/`, git-ignored). Record snapshot metadata (query, cache key, fetch time, node/edge counts).
4. Generate H3 cells (default resolution 9) covering the boundary; compute `overlap_ratio` per cell.
5. Compute raw metrics per cell and for the whole area.
6. Normalize against the versioned reference ranges in `metric_definitions`.
7. Evaluate data-quality rules; store findings.
8. Compute and store the default-model `area_scores`.
9. Mark run `succeeded` (or `failed` with `error_message`). All persistence for steps 4–8 happens in one transaction.

Every stage emits a structured log event with `analysis_run_id`, `service_area_id`, stage, duration, record counts.

## What-if scoring

Scoring is a pure function over stored *normalized* metric values. The server exposes it via `POST /scoring/preview` (compute, never persist). The frontend calls this endpoint on slider change (debounced) rather than duplicating the formula, so there is one implementation of the score. Area-level normalized values are small (3 areas x 5 metrics), so the round trip is cheap.

## "Current" run

For each service area, the current run is the most recent run with `status = 'succeeded'`. Endpoints accept an optional `analysis_run_id` to inspect older runs.

## Cross-cutting rules

- **Missing is not zero.** Nullable values end to end (DB `NULL`, JSON `null`, UI "Unavailable").
- **Provenance.** Each result carries metric version, source metadata, and run timestamp.
- **Determinism.** Same inputs and same cached OSM snapshot produce identical outputs.
- **No live network in CI.** Tests use committed fixtures in `backend/tests/fixtures/osm/`; live tests are marked `live_data` and excluded by default.
- **Config via environment.** `DATABASE_URL`, `LOG_LEVEL`, `H3_RESOLUTION`, `CORS_ORIGINS`; optional `MAP_STYLE_URL` for the frontend. No secrets are required for the MVP.

## Basemap

MapLibre GL JS is used instead of Mapbox GL JS because no Mapbox token is available (ADR-007). The basemap style URL is configuration, so a Mapbox style can be swapped in later. The H3 and boundary layers are independent of the basemap.

## Deployment (local only for MVP)

Docker Compose runs PostGIS. Backend and frontend run natively (uvicorn, Vite).

## Out of scope for MVP

Authentication, background workers, pipeline-trigger API, ML, Spark, synthetic data (Phase 8).

## Operational scenarios and diagnostics

The CLI-only `simulate-area` command uses the pure seeded generator and writes the three synthetic tables atomically. Operations reads aggregate a selected scenario pinned to a successful geographic analysis. A separate Operations page labels every view synthetic; it does not participate in geographic rankings.

Request telemetry records route templates, generated request IDs, status and timing. Readiness and operator-controlled interrupted-run recovery are documented in [reliability.md](reliability.md). Local benchmark evidence is in [performance.json](performance.json); the fixed-range review is in [calibration.md](calibration.md).
