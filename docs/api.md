# API Draft (v1)

Base path: `/api/v1`. The implemented contract is committed as [openapi.json](openapi.json) (regenerate with `uv run python -m cli export-openapi` from `backend/`; a test fails on drift). This page documents intent and the refinements below. JSON only. All numeric metric fields are nullable (`null` = unavailable).

## Conventions

- IDs are UUIDs. Invalid UUID gives 422. Unknown resource gives 404.
- "Current run" = latest `succeeded` run for the area unless `analysis_run_id` is supplied.
- Lists are deterministically ordered (by `name`, or documented sort) and paginated with `limit` (default 50, max 200) and `offset`.
- Metric names and sort fields are validated against allow-lists.
- Error shape:

```json
{"error": {"code": "not_found", "message": "Service area not found", "details": null}}
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` (unversioned) | Liveness and DB connectivity |
| GET | `/service-areas` | List areas with current score and last run time |
| GET | `/service-areas/{id}` | Area detail and boundary (GeoJSON) |
| GET | `/service-areas/{id}/summary` | Score, confidence, rank, strengths/risks, warnings, last run |
| GET | `/service-areas/{id}/metrics` | Area metrics: raw, normalized, confidence, definition, source |
| GET | `/service-areas/{id}/quality` | Data-quality findings and completeness stats |
| GET | `/service-areas/{id}/cells` | H3 cells as GeoJSON for the map |
| POST | `/comparisons` | Side-by-side comparison of 2-3 areas |
| POST | `/scoring/preview` | What-if scoring, not persisted |
| GET | `/analysis-runs` | List runs (filter by `service_area_id`, `status`) |
| GET | `/analysis-runs/{id}` | Run detail and source metadata |
| GET | `/scoring-models` | Available models (default flagged) |

### `GET /service-areas/{id}/cells`

Query: `metric` (allow-list; includes `overall_score`), `analysis_run_id` (optional), `bbox=minLon,minLat,maxLon,maxLat` (optional), `limit` (default 2000, max 5000).

Returns a GeoJSON FeatureCollection. Each feature: `h3_index`, `raw_value`, `normalized_value`, `confidence`, `overlap_ratio`. Response includes `truncated: true` when `limit` clips the result. A missing metric value is `null`, not `0`.

### `POST /comparisons`

```json
{"service_area_ids": ["...", "..."], "scoring_model_id": "..."}
```

2-3 distinct ids required (otherwise 422). `scoring_model_id` optional (default model). Response: per area score, confidence, components, rank, strengths, risks, warnings (including DQ-006 computed over the compared set), and `run` metadata.

### `POST /scoring/preview`

```json
{"service_area_ids": ["..."], "weights": {"intersection_density": 0.25, "road_density": 0.25,
  "avg_node_degree": 0.20, "network_directness": 0.15, "metadata_completeness": 0.15}}
```

Invalid weights (missing key, unknown key, negative, sum != 1) return 422 with per-field details. Response matches the comparison shape and includes `"temporary": true`. Nothing is written.

## Out of scope for MVP

Triggering analysis via API, authentication, write endpoints for areas.

## Implemented refinements (Phase 5)

- **Lists** return `{items, total, limit, offset}` (`/service-areas`, `/analysis-runs`); `/scoring-models` returns `{items}`. `/analysis-runs` is newest first.
- **Scores are computed at read time** from the run's stored area metrics via `app.scoring` with the default model (or the requested/preview weights), not read from `area_scores`. `rank` is a dense rank (score desc; scores equal to 6 decimals tie; null = unranked) among *all* areas for list/summary, and among the compared set for comparison/preview.
- **No successful run**: list/summary/comparison include the area with null score and `no_successful_run`; `/metrics`, `/quality`, `/cells` return 404. A supplied `analysis_run_id` must belong to the area (else 404); it is also accepted by `/quality`.
- **Components**: `contribution` is null (not 0) for a missing metric; `effective_weight` is the renormalized weight.
- **Cells**: `metric` defaults to `overall_score` and is validated against metric definitions plus `overall_score` (422). Feature properties are `h3_index, raw_value, normalized_value, confidence, overlap_ratio, score`; `score` (0-100, null if insufficient data) is set only for `overall_score`, whose raw/normalized values are null. `bbox` must be `minLon,minLat,maxLon,maxLat` with min < max inside lon/lat bounds (422). Top level: `metric, analysis_run_id, limit, truncated`.
- **Quality**: `completeness` = `cells_count`, per-metric `null_cells`/`null_share` (cell has no non-null raw value), `low_confidence_cells/share` (cell with any metric confidence < `low_confidence_threshold` = 0.5), plus `source` (run.source_metadata) and `analyzed_at`.
- **Comparison/preview**: DQ-006 appears as `peer_outliers` and a `peer_outlier:<metric>` warning (only with >= 3 areas that have data; computed on raw values). Preview accepts 1-3 distinct areas; `scoring_model.id` is null; response has `"temporary": true`. Invalid weights return 422 with `details[0] = {loc, msg, type, missing, unexpected}`.
- **Errors**: `not_found` (404, also unknown routes), `validation_error` (422, including remapped FastAPI validation errors, `details` = list of `{loc,msg,type}`), `method_not_allowed` (405), `payload_too_large` (413, bodies > 64 KB), `internal` (500, no internals leaked).

## Synthetic operational analytics (Phase 8)

- `GET /service-areas/{id}/simulations?limit=50&offset=0` lists scenarios newest-first, with explicit `synthetic: true` on the response and each run.
- `GET /service-areas/{id}/operations?simulation_run_id=<optional UUID>` returns the requested scenario for this area, or its newest scenario. No scenario/incorrect ownership returns 404. The response is always `synthetic: true` and includes an explicit disclaimer.
- Metrics: route count, completion fraction, intervention fraction (routes with at least one intervention), mean completed-trip duration, issue counts by severity/status and mean resolution hours over resolved issues. Null means no denominator, never zero-filled. Daily UTC series include route/completion/intervention counts and completed-trip duration.
- Generation is CLI-only: `python -m cli simulate-area <slug> --seed 42 --routes 500`. Identical source run, seed, count and generator version reuse the existing scenario. Synthetic metrics never enter geographic scores.

## Reliability diagnostics

`GET /ready` returns 200 when the database is reachable and 503 otherwise. API responses include generated `X-Request-ID` and `Server-Timing` headers. Public metric, quality and analysis-run provenance omits local cache directory paths while preserving source IDs, cache keys, query parameters and timestamps.
