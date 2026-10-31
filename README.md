# MobilityLens

A geospatial decision-support platform for comparing mobility service areas using public road-network data, transparent weighted scores and visible data-quality limitations.

**Status:** Phase 6 frontend implemented. The backend exposes analysis/read APIs; the frontend includes Executive Overview, Interactive Map, Area Comparison, Data Quality and What-if Analysis. See [logs.md](logs.md) for feature commits, verification and handoff notes. Live PostGIS acceptance remains to be rerun locally.

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

Database integration/contract tests require a dedicated database whose name ends with `_test`. Tests reset its schema; never point them at your analysis database. See [logs.md](logs.md) for the current validation scope and remaining acceptance work.

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

```text
Census boundaries + OpenStreetMap road networks
        ↓
Typer batch pipeline → PostgreSQL + PostGIS
                              ↓
                         FastAPI v1
                              ↓
              React + MapLibre + Plotly
```

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

Real analysis uses OpenStreetMap contributors (ODbL) and US Census land-clipped boundaries. Browser test fixtures are synthetic and explicitly labeled. Synthetic operational analytics are deferred to Phase 8. MobilityLens uses no proprietary fleet data and is not an autonomous-driving system.
