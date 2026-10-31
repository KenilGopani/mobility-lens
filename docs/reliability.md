# Reliability and performance

## Request visibility

API responses include a generated `X-Request-ID` and `Server-Timing: app;dur=…`. Structured `http_request` events contain the request ID, route template, method, status and total duration. Query strings, bodies and credentials are not logged by this middleware. Reverse-proxy/server access logs should follow the same policy if deployed.

`GET /health` is liveness plus database status. `GET /ready` returns HTTP 503 when the database cannot be reached; use it for dependency readiness checks.

## Batch failure and interruption recovery

1. Inspect `GET /api/v1/analysis-runs?status=failed` and run logs. A failed stage rolls back its data transaction; its run record retains the error and captured provenance.
2. Retry one area with `python -m cli analyze-area <slug>`, or resume an unchanged batch with `python -m cli analyze-all --resume`. Each attempted retry creates a new analysis run. A failed/unfinished run never displaces the most recent successful run in API reads.
3. After a hard process crash, inspect old `running` rows using `python -m cli recover-stale-runs --older-than-hours 24`. This is a preview by default.
4. Only after confirming that no worker is still using those runs, repeat with `--apply`. Locked rows are skipped. This marks only old running attempts failed; successful/recent runs remain unchanged. Then resume the batch.

`--resume` is recovery, not a freshness check. Omit it after changing boundaries, reference definitions, scoring settings or source snapshots. OSM downloads already use bounded exponential retry (4 attempts, 20/40/80-second waits) and disk response caching; ordinary tests inject fixture providers and never hit public services.

## Measured baseline

Run the real API, then from `backend/`:

```bash
uv run python -m cli benchmark-api ../docs/performance.json --samples 10
```

The report includes local HTTP latency and a parameterized `EXPLAIN (ANALYZE, BUFFERS)` plan for a San Jose viewport. Warm samples include HTTP/serialization/database work, not remote public-data fetching. These are local portfolio-scale measurements, not production SLAs.

Existing indexes include geometry GiST indexes, run/cell and metric composite primary keys, and service-area run lookup indexes. The captured plan and measured targets justify retaining these indexes without speculative additional indexes or application caches. A larger or concurrent deployment should be profiled again before changing them.

The frontend limits viewport requests to 2,000 cells and flags truncation. Query keys isolate area, metric and bounding box; request cancellation prevents stale responses from replacing the selected view. Plotly and MapLibre/its worker are separate lazy chunks. Their vendor sizes exceed Vite's advisory, while the initial application remains separate.
