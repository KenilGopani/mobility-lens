# ADR-003: Batch pipeline separated from the HTTP API

**Status:** Accepted

## Context
OSM download and graph analysis for a city can take minutes and gigabytes of memory (San Jose is the largest case). An HTTP request must not block on this.

## Decision
Run analysis through a Typer CLI that writes results to PostGIS. The API is read-only over stored results. Raw OSM responses are cached on disk. Every execution creates an `analysis_runs` row with a status.

## Consequences
- API latency is independent of pipeline cost.
- Runs are reproducible and auditable. Failed runs remain visible.
- No trigger endpoint or worker queue in the MVP. If a requirement appears later, add a background worker as a separate decision.
