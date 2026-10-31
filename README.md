# MobilityLens

A geospatial decision-support platform for comparing mobility service areas using public road-network data, transparent weighted scores and visible data-quality limitations.

**Status:** Phases 0–10 of the defined portfolio roadmap are implemented and locally validated. Geographic analysis uses real persisted OSM/Census snapshots; operational analytics is explicitly synthetic. See [logs.md](logs.md) for module commits and phase evidence.

![Executive overview using real public-data snapshots](docs/screenshots/overview.png)

[Recorded demo](docs/demo.webm) · [Map screenshot](docs/screenshots/map.png) · [Synthetic operations screenshot](docs/screenshots/operations.png) · [Decision walkthrough](docs/decision-walkthrough.md) · [Sample API responses](docs/sample-responses/)

## Problem and audience

A mobility program manager or operations analyst needs to decide where a service should expand next, explain the ranking, challenge assumptions and see where evidence is weak. MobilityLens makes those inputs inspectable instead of offering an unexplained recommendation. It is a local portfolio/internal-tool example, not a validated forecast of fleet performance.

## Decision workflow

1. Compare candidate service areas: Foster City, Mountain View and San Jose.
2. Inspect their H3 cells, metrics and low-confidence regions on the MapLibre map.
3. Review score contributions, missing data, strengths, risks and source provenance.
4. Adjust temporary weights to challenge the default ranking. All scoring stays in the backend.

The five MVP metrics are intersection density, road density, average node degree, network directness and road metadata completeness. Fixed reference ranges and weights are documented assumptions. Unavailable data remains unavailable; it is never silently replaced with zero. Confidence is a reliability signal, not a probability.

## Local setup

Requires Python 3.12, uv, Node.js 22+ and Docker with Compose. Run commands from the repository root unless a different directory is shown.

Start PostGIS (host port 5433):

```bash
docker compose up -d db
```

Prepare the backend:

```bash
cd backend
cp ../.env.example .env
uv sync --frozen
uv run alembic upgrade head
uv run python -m cli seed-service-areas
uv run python -m cli seed-metric-definitions
uv run python -m cli seed-scoring-model
```

Generate real analysis results, then serve the API. Network fetching can take time; OSM responses are cached:

```bash
uv run python -m cli analyze-area foster-city
uv run python -m cli analyze-area mountain-view
uv run python -m cli analyze-area san-jose
uv run uvicorn app.main:app --reload
```

In another terminal, prepare the frontend:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Open the printed `http://localhost:5173` URL. The default API is `http://localhost:8000`. Backend CORS allows `http://localhost:5173`; if using another host or port, set `CORS_ORIGINS` in `backend/.env` accordingly. Frontend configuration uses `VITE_API_BASE_URL` and `VITE_MAP_STYLE_URL`. The public demo basemap requires no access token and has external network dependencies.

No API request starts an OSM download or writes what-if assumptions. Analysis runs are created only through the CLI.

### Batch analysis and synthetic scenarios

From `backend/`:

```bash
uv run python -m cli analyze-all
# Resume only an unchanged, interrupted batch:
uv run python -m cli analyze-all --resume
# Optional, clearly synthetic operational examples:
uv run python -m cli simulate-area foster-city --seed 42 --routes 500
uv run python -m cli simulate-area mountain-view --seed 43 --routes 500
uv run python -m cli simulate-area san-jose --seed 44 --routes 500
```

The Operations page shows simulated completion/intervention rates, completed-trip duration, daily trends, issue severity/status and resolution time. Each scenario records its seed, generator version and pinned geographic run; repeating the same inputs reuses it. Synthetic data never enters geographic scores.

## Validation

From `frontend/`:

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

From `backend/`:

```bash
uv run ruff check .
uv run mypy app cli pipelines
uv run pytest tests/unit --no-cov
```

Database integration/contract tests require a dedicated database whose name ends with `_test`. Tests reset its schema; never point them at your analysis database:

```bash
# From backend/, using the dedicated local test database:
DATABASE_URL=postgresql+psycopg://mobility:mobility@localhost:5433/mobility_lens_test uv run pytest
```

The final local validation passed 250 backend tests, 16 frontend unit tests and 6 browser tests. Browser tests also pass in CI's isolated fixture mode. Remote CI has not been triggered by this local implementation.

### Browser acceptance and demo capture

For the real-data tests, start the API with the test origin allowlisted:

```bash
# From backend/ (stop another API process on port 8000 first):
CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5175"]' uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then from `frontend/`:

```bash
npx playwright install chromium
npm run test:e2e
npm run demo:record
```

Playwright starts its own frontend on port 5175. The capture command writes screenshots and a short WebM walkthrough to `docs/`. Without a real API, use `E2E_FIXTURE=1 npm run test:e2e`; this starts an isolated, explicitly labeled fixture API on port 8011. Fixture mode is also wired into CI. Normal tests skip the opt-in recording test.

### Reliability and performance

Readiness is available at `/ready`, with generated request IDs and timing headers on API responses. From `backend/`:

```bash
uv run python -m cli benchmark-api ../docs/performance.json --samples 10
uv run python -m cli calibration-report ../docs/calibration.md
uv run python -m cli recover-stale-runs --older-than-hours 24
```

Stale-run recovery previews by default. Use `--apply` only after confirming the owning worker stopped. Details and measured query plans are in [reliability.md](docs/reliability.md). Recorded warm local p95s: summary 5 ms, comparison 4 ms, viewport 55 ms. Useful overview render during demo capture was 738 ms. These are local measurements, not production SLAs. npm audit reports zero vulnerabilities with the committed dependency override.

## Isolated browser QA without PostGIS

A test-only API fixture is available to verify UI workflows without downloading public data. Every metric and geometry it serves is synthetic test data. It uses the backend's pure scoring engine and cannot write analysis results.

```bash
# Terminal 1, repository root:
backend/.venv/bin/python frontend/tests/browser_fixture.py

# Terminal 2, frontend directory (macOS/Linux shell):
VITE_API_BASE_URL=http://127.0.0.1:8011 npm run dev -- --host 127.0.0.1
```

Visit the preview URL. Fixture model/provenance/warnings identify the test data. Stop both processes after testing; run the frontend normally to return to the real API on port 8000. The fixture has no role in the production build.

## Architecture and design

```mermaid
flowchart LR
    Census[Census land boundaries] --> Pipeline[CLI geospatial pipeline]
    OSM[OpenStreetMap networks] --> Pipeline
    Pipeline --> DB[(PostgreSQL + PostGIS)]
    DB --> API[FastAPI read API]
    API --> UI[React + MapLibre + Plotly]
    Generator[Seeded synthetic generator] --> Sim[CLI simulate-area]
    DB --> Sim
    Sim --> Synthetic[(Synthetic scenario tables)]
    Synthetic --> API
```

**Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL/PostGIS, GeoPandas, Shapely, OSMnx, H3, React/TypeScript, TanStack Query, MapLibre, Plotly, Vitest and Playwright. The [standalone diagram source](docs/architecture.mmd) can be reused independently.

| Document                                       | Purpose                                                              |
| ---------------------------------------------- | -------------------------------------------------------------------- |
| [logs.md](logs.md)                             | Completed modules, validation and next work                          |
| [PLAN.md](PLAN.md)                             | Original phased roadmap                                              |
| [docs/architecture.md](docs/architecture.md)   | Components and data flow                                             |
| [docs/data-model.md](docs/data-model.md)       | Domain entities and spatial schema                                   |
| [docs/scoring-model.md](docs/scoring-model.md) | Metrics, normalization, weights and confidence                       |
| [docs/api.md](docs/api.md)                     | Implemented REST behavior                                            |
| [docs/adr/](docs/adr/)                         | Architecture decisions; MapLibre supersedes the original Mapbox plan |

## Data disclaimer

Real analysis uses OpenStreetMap contributors (ODbL) and US Census land-clipped boundaries. Browser test fixtures are synthetic and explicitly labeled. Synthetic operational analytics are opt-in and always labeled in the database, API and UI. MobilityLens uses no proprietary fleet data and is not an autonomous-driving system.

## Engineering tradeoffs and limits

- Heavy ingestion runs offline; HTTP reads stay responsive. There is one pure scoring implementation for persisted and temporary scores.
- Fixed normalization ranges avoid forcing extreme 0/1 values from a three-city peer set. Weights/ranges are documented assumptions; see [calibration.md](docs/calibration.md).
- Missing values remain null; confidence reflects available weight and metric reliability. Current area confidence uses sample size and does not prove completeness or safety.
- Viewport filtering, payload bounds and existing spatial indexes meet the measured scale. No additional cache, distributed processing, worker queue or speculative indexes were introduced.
- MapLibre and Plotly are lazy vendor chunks; they exceed Vite's size advisory. Public basemap/fonts require external network access. Ordinary database/unit/CI browser data sources remain deterministic and offline.
- The captured geographic snapshots are from 2026-10-25, not newly downloaded on the screenshot date. Synthetic outcomes are illustrative, not observed fleet results. No authentication or public deployment is included in the local MVP.

## Future work

The defined phases are delivered. Further work is optional: validate assumptions against real service outcomes if such evidence becomes available, refresh public snapshots, expand POI/accessibility analysis, profile larger/concurrent workloads and add authentication/rate limits before a public deployment. The PLAN's future-enhancement ideas are not requirements for this portfolio release.
