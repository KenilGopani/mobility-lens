# MobilityLens — Development Plan

> **Project goal:** Build a production-style internal decision-support platform that helps mobility/program teams compare candidate service areas using public geospatial data, transparent scoring, data-quality signals, and clearly labeled synthetic operational data.

**Recommended GitHub repository:** `mobility-lens`

**One-line description:**  
A full-stack geospatial decision-intelligence platform for comparing mobility service areas using road-network, accessibility, operational, and data-quality metrics.

---

## 1. Product Principle

This project should demonstrate the exact engineering pattern expected from an internal tooling / analytics developer:

> **Start from a business decision → define reliable data inputs → model the domain → build repeatable pipelines → expose stable APIs → build a usable decision interface → test assumptions and data quality.**

This is **not** an autonomous-driving system and should never imply access to proprietary fleet data.

Use only:

- Public geospatial data, primarily OpenStreetMap.
- Clearly labeled synthetic operational/simulation data.
- Deterministic, explainable scoring logic.
- Reproducible data pipelines.

---

## 2. Primary User and Core Decision

### Primary user
A Technical Program Manager, operations analyst, or engineering leader deciding where a mobility service should expand next.

### Core question
> Which candidate service area is the strongest expansion option, and what evidence, assumptions, risks, and data-quality limitations support that recommendation?

### Initial candidate areas
Start small:

1. Foster City
2. San Jose
3. Mountain View

Add more only after the MVP is stable.

---

## 3. MVP Scope

The first usable release should allow a user to:

1. View candidate service areas.
2. Inspect an interactive map.
3. Analyze road-network metrics by H3 cell.
4. Compare candidate areas side-by-side.
5. View an explainable overall score.
6. Adjust scoring weights for what-if analysis.
7. See data-quality/confidence indicators.
8. Understand where each metric came from.
9. See the last successful analysis run.

Do **not** add synthetic fleet/issue data until the geospatial MVP is stable.

---

## 4. Engineering Principles

### 4.1 Architecture before implementation
Before writing feature code:

1. Define the business question.
2. Define domain entities.
3. Define database schema.
4. Define data contracts.
5. Define API contracts.
6. Define scoring rules.
7. Define test strategy.
8. Only then implement.

### 4.2 Prefer simple, explainable systems
Do not introduce ML merely to make the project sound more advanced.

The scoring model should initially be a deterministic weighted model with clearly documented normalization and assumptions.

### 4.3 Separate pipeline work from request/response APIs
OSM downloads and geospatial computation can be slow.

The first architecture should therefore use:

```text
Public Data
    |
    v
Batch / CLI Analysis Pipeline
    |
    v
PostgreSQL + PostGIS
    |
    v
FastAPI Read API
    |
    v
React + TypeScript + Mapbox
```

Do **not** make an HTTP request wait while OSMnx downloads and analyzes an entire city.

### 4.4 Every result should be explainable
For every score, preserve:

- raw metric value
- normalized value
- weight
- contribution to overall score
- data source
- analysis timestamp
- confidence / quality signal

### 4.5 Do not hide incomplete data
A missing value should not silently become zero.

The system should distinguish:

- `value = 0`
- `value is unavailable`
- `value exists but confidence is low`

---

# 5. Proposed Tech Stack

## Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL 16
- PostGIS
- GeoPandas
- Shapely
- OSMnx
- H3
- Pandas
- NumPy
- Typer for data/analysis CLI commands

## Frontend

- React
- TypeScript
- Vite
- TanStack Query
- Mapbox GL JS for geospatial visualization
- Plotly.js via `react-plotly.js` for analytical charts and comparisons
- React Router
- CSS/Tailwind only if needed; avoid UI-framework bloat early

## Frontend framework rationale

The JD allows either a traditional frontend stack such as React/TypeScript **or** a Python UI framework such as Streamlit, Dash, or Flask-based rendering.

This project intentionally uses **React + TypeScript** rather than Streamlit/Dash because:

- the product is meant to resemble a production-style internal web application
- Mapbox integration and rich geospatial interactions are easier to control in React
- the UI requires reusable components, client-side state, map layers, comparison views, and what-if controls
- it demonstrates stronger end-to-end web engineering

Do **not** add Streamlit merely to match a keyword. It would duplicate the frontend without adding meaningful product value.

Visualization responsibilities:

```text
Mapbox GL JS
    -> maps
    -> H3 cells
    -> service-area boundaries
    -> spatial heatmaps
    -> hover/click interactions

Plotly.js
    -> metric comparisons
    -> score breakdowns
    -> data-quality charts
    -> operational trends
    -> simulation analytics
```

## Testing

### Python
- pytest
- pytest-asyncio
- pytest-cov
- factory/helper fixtures
- integration tests against PostGIS

### Frontend
- Vitest
- React Testing Library
- Playwright for critical end-to-end flows

## Quality

### Python
- Ruff
- MyPy
- Black only if desired; otherwise use Ruff formatting consistently

### TypeScript
- ESLint
- Prettier
- TypeScript strict mode

## Dev infrastructure

- Docker Compose for PostgreSQL + PostGIS
- Local Python virtual environment
- Local Node/Vite frontend
- GitHub Actions for CI

The application itself can run entirely on a MacBook.

---

# 6. Repository Structure

```text
mobility-lens/
|
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   |-- v1/
|   |   |
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- repositories/
|   |   |-- services/
|   |   |-- scoring/
|   |   |-- quality/
|   |   |-- main.py
|   |
|   |-- pipelines/
|   |   |-- osm/
|   |   |-- spatial/
|   |   |-- metrics/
|   |   |-- synthetic/
|   |
|   |-- cli/
|   |-- migrations/
|   |-- tests/
|   |   |-- unit/
|   |   |-- integration/
|   |   |-- contract/
|   |
|   |-- pyproject.toml
|
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- features/
|   |   |   |-- map/
|   |   |   |-- comparison/
|   |   |   |-- quality/
|   |   |   |-- scoring/
|   |   |
|   |   |-- pages/
|   |   |-- types/
|   |   |-- hooks/
|   |
|   |-- tests/
|   |-- package.json
|
|-- docs/
|   |-- architecture.md
|   |-- data-model.md
|   |-- scoring-model.md
|   |-- api.md
|   |-- adr/
|
|-- scripts/
|-- .github/
|   |-- workflows/
|
|-- docker-compose.yml
|-- .env.example
|-- README.md
|-- PLAN.md
```

---

# 7. Domain Model

Start by modeling the domain before creating tables.

## Core entities

### ServiceArea
A candidate geographic area being evaluated.

Important fields:

- id
- name
- slug
- geometry/boundary
- source
- created_at
- updated_at

### AnalysisRun
Represents one repeatable execution of the geospatial pipeline.

Important fields:

- id
- service_area_id
- pipeline_version
- parameters
- status
- started_at
- completed_at
- error_message
- source_snapshot metadata

### H3Cell
A spatial analysis unit.

Important fields:

- h3_index
- resolution
- geometry
- centroid

### MetricDefinition
Describes a metric.

Examples:

- intersection_density
- road_density
- avg_node_degree
- metadata_completeness
- poi_accessibility

Fields:

- key
- display_name
- description
- unit
- higher_is_better
- normalization_method
- version

### CellMetric
Stores raw and normalized metric values for an H3 cell.

Fields:

- analysis_run_id
- h3_index
- metric_key
- raw_value
- normalized_value
- confidence
- metadata

### AreaMetric
Aggregated area-level metrics.

Fields:

- analysis_run_id
- metric_key
- raw_value
- normalized_value
- confidence

### ScoringModel
Defines scoring assumptions.

Fields:

- id
- name
- version
- weights
- normalization_version
- created_at

### AreaScore
Stores one score calculation.

Fields:

- analysis_run_id
- scoring_model_id
- score
- confidence
- component_breakdown
- calculated_at

### DataQualityFinding
Explicit data-quality issue.

Fields:

- id
- analysis_run_id
- rule_key
- severity
- message
- affected_fraction
- metadata

---

# 8. Initial Database Schema

Use PostgreSQL + PostGIS.

A first-pass relational schema:

```text
service_areas
-------------
id UUID PK
name VARCHAR
slug VARCHAR UNIQUE
boundary GEOMETRY(MULTIPOLYGON, 4326)
source VARCHAR
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ


analysis_runs
-------------
id UUID PK
service_area_id UUID FK
pipeline_version VARCHAR
parameters JSONB
status VARCHAR
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ NULL
error_message TEXT NULL
source_metadata JSONB


h3_cells
---------
h3_index VARCHAR PK
resolution INTEGER
boundary GEOMETRY(POLYGON, 4326)
centroid GEOMETRY(POINT, 4326)


analysis_run_cells
------------------
analysis_run_id UUID FK
h3_index VARCHAR FK
overlap_ratio DOUBLE PRECISION
PRIMARY KEY (analysis_run_id, h3_index)


metric_definitions
------------------
key VARCHAR PK
display_name VARCHAR
description TEXT
unit VARCHAR
higher_is_better BOOLEAN
normalization_method VARCHAR
version VARCHAR


cell_metrics
------------
analysis_run_id UUID FK
h3_index VARCHAR FK
metric_key VARCHAR FK
raw_value DOUBLE PRECISION NULL
normalized_value DOUBLE PRECISION NULL
confidence DOUBLE PRECISION NULL
metadata JSONB
PRIMARY KEY (analysis_run_id, h3_index, metric_key)


area_metrics
------------
analysis_run_id UUID FK
metric_key VARCHAR FK
raw_value DOUBLE PRECISION NULL
normalized_value DOUBLE PRECISION NULL
confidence DOUBLE PRECISION NULL
PRIMARY KEY (analysis_run_id, metric_key)


scoring_models
--------------
id UUID PK
name VARCHAR
version VARCHAR
weights JSONB
normalization_version VARCHAR
created_at TIMESTAMPTZ


area_scores
-----------
analysis_run_id UUID FK
scoring_model_id UUID FK
score DOUBLE PRECISION
confidence DOUBLE PRECISION
component_breakdown JSONB
calculated_at TIMESTAMPTZ
PRIMARY KEY (analysis_run_id, scoring_model_id)


data_quality_findings
---------------------
id UUID PK
analysis_run_id UUID FK
rule_key VARCHAR
severity VARCHAR
message TEXT
affected_fraction DOUBLE PRECISION NULL
metadata JSONB
```

Do not add more tables until a real requirement exists.

---

# 9. Metric Strategy

## MVP metrics

Start with metrics that can be calculated reliably from OSM road-network data.

### 1. Intersection density
Intersections per square kilometer.

### 2. Road density
Total drivable road length per square kilometer.

### 3. Average node degree
Simple road-network connectivity indicator.

### 4. Circuity / directness
How indirect road paths are relative to straight-line distance.

### 5. Road metadata completeness
Percentage of selected road records with relevant metadata.

Important:

> Call this **metadata completeness**, not true geographic coverage unless a defensible ground-truth comparison exists.

### Later metric
POI accessibility.

Do not block the MVP on this.

---

# 10. Scoring Model

Use a transparent weighted score.

Example initial weights:

```text
intersection_density       25%
road_density               25%
avg_node_degree            20%
network_directness         15%
metadata_completeness      15%
```

These are assumptions, not objective truth.

Document them in:

`docs/scoring-model.md`

## Requirements

The scoring function must:

1. Accept normalized metric inputs.
2. Reject missing required weights.
3. Ensure weights sum to 1.0 within tolerance.
4. Handle unavailable metric values explicitly.
5. Return:
   - final score
   - confidence
   - contribution by metric
   - warnings

Example response:

```json
{
  "score": 84.7,
  "confidence": 0.91,
  "components": [
    {
      "metric": "road_density",
      "normalized_value": 0.88,
      "weight": 0.25,
      "contribution": 22.0
    }
  ],
  "warnings": []
}
```

---

# 11. Data-Quality Rules

The project should distinguish itself by making reliability visible.

Initial rules:

### DQ-001
Missing required metric.

### DQ-002
Road metadata completeness below configured threshold.

### DQ-003
Analysis area too small for stable comparison.

### DQ-004
Too few road-network nodes.

### DQ-005
OSM retrieval returned an unexpectedly small dataset.

### DQ-006
Metric is an outlier compared with peer candidate areas.

Every rule should have:

- severity
- machine-readable code
- human-readable explanation
- affected proportion if applicable

---

# 12. API Design

Version APIs from the beginning.

Base:

```text
/api/v1
```

## Health

```http
GET /health
```

## Service areas

```http
GET /api/v1/service-areas
GET /api/v1/service-areas/{service_area_id}
GET /api/v1/service-areas/{service_area_id}/summary
GET /api/v1/service-areas/{service_area_id}/metrics
GET /api/v1/service-areas/{service_area_id}/quality
```

## Map cells

```http
GET /api/v1/service-areas/{service_area_id}/cells
```

Query parameters:

```text
metric
analysis_run_id
bbox
limit
```

Do not return an entire large H3 dataset when the map only needs the current viewport.

## Comparison

```http
POST /api/v1/comparisons
```

Request:

```json
{
  "service_area_ids": ["...", "..."],
  "scoring_model_id": "..."
}
```

## What-if scoring

```http
POST /api/v1/scoring/preview
```

Request:

```json
{
  "service_area_ids": ["...", "..."],
  "weights": {
    "intersection_density": 0.25,
    "road_density": 0.25,
    "avg_node_degree": 0.20,
    "network_directness": 0.15,
    "metadata_completeness": 0.15
  }
}
```

This endpoint should calculate but **not persist** temporary what-if weights.

## Analysis runs

Initially keep pipeline execution in CLI.

Read-only API:

```http
GET /api/v1/analysis-runs
GET /api/v1/analysis-runs/{analysis_run_id}
```

Only add an API endpoint for triggering analysis later if a real requirement exists.

---

# 13. CLI Design

Use Typer.

Example:

```bash
python -m backend.cli analyze-area foster-city
python -m backend.cli analyze-area san-jose
python -m backend.cli analyze-all
python -m backend.cli seed-service-areas
python -m backend.cli seed-scoring-model
```

A pipeline run should be idempotent where practical and always create an `analysis_runs` record.

---

# 14. Frontend UX

## Page 1 — Executive Overview

Show:

- recommended area
- ranking
- top metrics
- confidence
- main warnings
- last analysis timestamp

## Page 2 — Interactive Map

Show:

- service area boundary
- H3 cells
- metric selector
- hover tooltip
- detail panel
- confidence/quality overlay

Suggested metric selector:

```text
Overall score
Intersection density
Road density
Connectivity
Network directness
Metadata completeness
```

Use Plotly for non-map analytical visualizations such as:

- ranked service-area score bars
- metric comparison charts
- score contribution breakdowns
- confidence/completeness charts
- operational trends introduced in later phases

Keep geospatial layers in Mapbox rather than duplicating them in Plotly.

## Page 3 — Area Comparison

Allow selecting 2–3 areas.

Show:

- side-by-side metrics
- score breakdown
- confidence
- top strengths
- top risks

## Page 4 — Data Quality

Show:

- quality findings
- missing values
- completeness statistics
- source information
- analysis timestamp

## Page 5 — What-if Analysis

Sliders for scoring weights.

Requirements:

- percentages always total 100%
- rankings update immediately
- UI clearly indicates temporary assumptions
- default model can be restored with one click

---

# 15. Testing Strategy

Use **TDD selectively**, not dogmatically.

TDD is especially valuable for:

- scoring logic
- normalization
- data-quality rules
- geospatial helper functions
- API validation
- repository behavior

UI layout can be implemented first and tested around observable behavior.

## Test pyramid

```text
             E2E
            /   \
       Integration
       /         \
      Unit Tests
```

The majority should be unit tests.

---

# 16. Required Unit Tests

## Scoring

Before implementing scoring, write tests for:

1. valid weights produce expected score
2. weights not summing to 1 are rejected
3. missing metric is handled explicitly
4. zero is not treated as missing
5. low-confidence component reduces output confidence
6. component contributions sum to final score
7. score remains within valid range

## Normalization

Test:

1. known minimum
2. known maximum
3. midpoint
4. inverted metric where lower is better
5. constant-value dataset
6. null input
7. outlier clipping behavior if implemented

## H3 / geospatial helpers

Test:

1. point converts to expected H3 index
2. polygon produces non-empty H3 cell set
3. boundary-cell overlap calculation is valid
4. invalid geometry is rejected or repaired explicitly
5. CRS transformations preserve expected units

## Data-quality rules

One test per rule code.

---

# 17. Integration Tests

Use a dedicated PostGIS test database.

Test:

- Alembic migrations apply cleanly.
- Service areas can be persisted and read.
- PostGIS geometry types round-trip correctly.
- Analysis run + metrics persist transactionally.
- Repository queries return only the requested analysis run.
- API reads actual test database data.
- Bounding-box cell queries work.

Do not depend on live OpenStreetMap for normal integration tests.

Use small committed fixtures.

---

# 18. Contract / API Tests

FastAPI tests should validate:

- status code
- response schema
- error schema
- pagination behavior
- invalid IDs
- missing analysis
- invalid scoring weights
- deterministic ordering

Generate OpenAPI automatically from FastAPI and treat it as the contract.

---

# 19. Frontend Tests

## Component tests

Test:

- metric selector changes visible metric
- confidence badge renders expected state
- comparison table displays API data
- Plotly comparison chart renders the expected metric series
- Plotly charts receive normalized/validated data rather than raw untrusted payloads
- missing values display `Unavailable`, not `0`
- what-if weights update both displayed scores and Plotly comparison views

## End-to-end tests

Playwright critical flows:

### E2E-001
Open app → see service-area rankings.

### E2E-002
Select San Jose → map loads cells.

### E2E-003
Change metric → map legend and values update.

### E2E-004
Compare two service areas.

### E2E-005
Modify scoring weights → ranking changes.

### E2E-006
Open data quality → warning is visible.

---

# 20. External Data Testing Rule

Do not make CI depend on OpenStreetMap availability.

Pipeline tests should use:

```text
tests/fixtures/osm/
```

with tiny deterministic datasets.

Live-data tests may exist separately and must be explicitly invoked.

Example:

```bash
pytest -m live_data
```

Never run them by default in CI.

---

# 21. Development Phases

---

## Phase 0 — Discovery and Design

### Goal
Remove ambiguity before coding.

### Deliverables

- `README.md` initial problem statement
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/scoring-model.md`
- Architecture Decision Records

Create ADRs for at least:

```text
ADR-001: FastAPI backend
ADR-002: PostgreSQL + PostGIS
ADR-003: batch pipeline separated from HTTP API
ADR-004: H3 as spatial aggregation unit
ADR-005: transparent weighted scoring instead of ML
ADR-006: synthetic data labeling policy
```

### Exit criteria

Do not move to Phase 1 until:

- product question is clear
- schema is reviewed
- API draft exists
- scoring assumptions are documented
- MVP boundaries are explicit

---

## Phase 1 — Repository Foundation

### Goal
Create a clean engineering foundation.

### Tasks

- initialize repository
- create backend/frontend directories
- configure Python project
- configure TypeScript/Vite project
- Docker Compose for PostGIS
- Alembic
- linting
- formatting
- test runners
- `.env.example`
- pre-commit hooks if useful
- GitHub Actions

### Required CI

Backend:

```text
lint
type-check
unit tests
integration tests
coverage
```

Frontend:

```text
lint
type-check
unit tests
build
```

### Exit criteria

A clean clone can:

1. start PostGIS
2. run migrations
3. run backend tests
4. run frontend tests
5. build frontend
6. pass CI

---

## Phase 2 — Core Domain + Database

### Goal
Implement schema without geospatial complexity first.

### TDD focus

Write repository and domain tests before implementations where practical.

### Tasks

- SQLAlchemy models
- Alembic migration
- Pydantic schemas
- repositories
- service-area seed command
- scoring model seed command

### Exit criteria

Data model persists correctly and all repository tests pass.

---

## Phase 3 — Geospatial Ingestion Pipeline

### Goal
Load one candidate area end-to-end.

Start with **Foster City only**.

### Tasks

1. define service-area boundary
2. fetch OSM road network using OSMnx
3. transform graph data into GeoDataFrames
4. validate CRS
5. calculate area
6. generate H3 cells
7. calculate overlap
8. persist analysis run
9. persist raw metrics
10. record quality findings

### Important rule

Cache raw OSM response/artifacts locally so development does not repeatedly hit public services.

### Exit criteria

One CLI command produces a reproducible analysis for Foster City.

---

## Phase 4 — Metric + Scoring Engine

### Goal
Make results explainable and comparable.

### TDD-first module

Write scoring and normalization tests before implementation.

### Tasks

- raw metric computation
- normalization
- area aggregation
- data-quality confidence
- scoring engine
- component breakdown
- score persistence

### Exit criteria

Given deterministic fixture data, expected scores are reproducible exactly.

---

## Phase 5 — Read API

### Goal
Expose stable data contracts to the frontend.

### Tasks

Implement:

- service-area endpoints
- summary
- metric data
- cells
- quality findings
- comparison
- scoring preview
- analysis-run metadata

### Exit criteria

All OpenAPI/contract tests pass and frontend can use generated/example responses.

---

## Phase 6 — Frontend MVP

### Goal
Deliver the actual decision workflow.

### Order

1. API client
2. executive overview
3. service-area selector
4. Mapbox map
5. H3 layer
6. metric selector
7. Plotly metric/score visualizations
8. comparison
9. data quality
10. what-if scoring

### Exit criteria

A user can answer:

> Which area ranks highest, why, and how reliable is that recommendation?

without reading raw database rows.

---

## Phase 7 — Add Candidate Areas

### Goal
Validate that the design generalizes.

Add:

- San Jose
- Mountain View

Run same pipeline.

Do not write city-specific branching logic unless absolutely necessary.

### Exit criteria

All candidate areas are processed by the same pipeline and are comparable.

---

## Phase 8 — Synthetic Operational Analytics

Only begin this after the geospatial product is stable.

### Goal
Demonstrate PMO-style multi-source analytics.

Clearly label all generated records as synthetic.

### New entities

```text
simulation_runs
route_events
operational_issues
```

Possible synthetic fields:

```text
simulation_run_id
service_area_id
route_id
started_at
completed_at
distance_km
duration_minutes
completed
intervention_count
```

Issues:

```text
issue_id
service_area_id
category
severity
status
created_at
resolved_at
```

### Metrics

- simulated route completion rate
- simulated intervention rate
- simulated mean trip duration
- issue count by severity
- mean issue resolution time

Never present synthetic metrics as real-world Zoox data.

---

## Phase 9 — Reliability / Performance

### Tasks

- query profiling
- database indexes
- spatial indexes
- pagination
- map viewport filtering
- caching if demonstrated necessary
- error logging
- structured logs
- pipeline retry strategy
- failed-run recovery
- performance benchmark notes

### Database indexes to evaluate

- GiST on geometry columns
- service_area_id + analysis_run_id
- metric lookup composite indexes

Do not add indexes blindly; verify query plans.

---

## Phase 10 — Portfolio / Interview Polish

### Deliverables

README should include:

1. problem
2. screenshots
3. architecture diagram
4. data flow
5. stack
6. metrics
7. scoring assumptions
8. data-quality design
9. synthetic-data disclaimer
10. local setup
11. tests
12. engineering tradeoffs
13. future work

Add:

- short demo GIF/video
- screenshots
- sample API responses
- architecture diagram
- decision explanation example

---

# 22. Git and Commit Practices

## Author identity

All commits must be authored by the repository owner.

Before Claude Code makes any commit:

```bash
git config user.name "Kenil Gopani"
git config user.email "<your-github-email>"
```

Verify:

```bash
git config user.name
git config user.email
```

### Claude Code rule

Claude Code may:

- edit files
- run tests
- propose commit messages
- stage files only when explicitly requested
- create a commit only when explicitly requested

Claude Code must **not**:

- use itself as commit author
- add `Co-authored-by: Claude`
- add bot attribution
- create commits silently
- rewrite existing user commits without explicit instruction

---

# 23. Commit Style

Use Conventional Commits.

Examples:

```text
chore: initialize backend and frontend workspaces

docs: define service area domain model

feat(db): add service area and analysis run schema

test(scoring): define weighted score behavior

feat(scoring): implement weighted scoring engine

feat(pipeline): ingest OSM road network for service area

feat(api): expose service area summary endpoint

feat(map): render H3 metric layer

fix(quality): distinguish missing values from zero

test(api): add comparison endpoint contract tests

perf(db): add spatial index for H3 viewport queries
```

## Commit rules

One commit should represent one coherent idea.

Avoid:

```text
update stuff
fix things
changes
more work
final
```

### Commit gate

Before every feature commit:

```text
lint passes
type-check passes
relevant tests pass
```

Before a phase-completion commit:

```text
all tests pass
frontend build passes
migration state is clean
documentation is updated
```

---

# 24. Claude Code Working Protocol

At the start of each phase, Claude Code should:

1. Read `PLAN.md`.
2. Read relevant ADRs.
3. Inspect existing code.
4. State the exact phase objective.
5. List files expected to change.
6. Identify tests to create/update.
7. Implement the smallest vertical slice.
8. Run tests.
9. Run lint/type-check.
10. Summarize what changed.
11. Propose a commit message.
12. Wait for explicit commit approval unless the user instructed otherwise.

Do not allow Claude Code to start unrelated future phases.

---

# 25. Definition of Done for Any Feature

A feature is not done merely because the UI appears to work.

A feature is done when:

- requirement is satisfied
- tests exist at the appropriate level
- tests pass
- lint passes
- type-check passes
- errors are handled
- naming is understandable
- no secrets are committed
- documentation is updated when behavior/contracts changed
- API/schema changes have migrations or contract updates
- commit is small and coherent

---

# 26. Pull Request Mindset Even When Working Solo

Work in short-lived branches:

```text
feat/geospatial-ingestion
feat/scoring-engine
feat/service-area-api
feat/h3-map-layer
```

Before merging to `main`:

- review diff
- run CI-equivalent checks
- remove debug code
- inspect generated files
- confirm migration
- update docs
- squash only if it improves history

`main` should remain runnable.

---

# 27. Suggested Branch Strategy

Simple trunk-based flow:

```text
main
  |
  |-- feat/repository-foundation
  |-- feat/domain-schema
  |-- feat/osm-pipeline
  |-- feat/scoring-engine
  |-- feat/read-api
  |-- feat/frontend-mvp
```

No long-lived `develop` branch needed for a solo portfolio project.

---

# 28. Secrets and Configuration

Never commit:

- Mapbox token
- database password
- API keys
- local paths
- personal credentials

Commit:

```text
.env.example
```

Example:

```text
DATABASE_URL=
MAPBOX_ACCESS_TOKEN=
LOG_LEVEL=INFO
H3_RESOLUTION=
```

---

# 29. Observability

Even locally, use structured logs.

Pipeline logs should contain:

- analysis_run_id
- service_area_id
- pipeline stage
- duration
- record counts
- warning count

Example:

```json
{
  "event": "metric_calculation_completed",
  "analysis_run_id": "...",
  "service_area_id": "...",
  "metric": "intersection_density",
  "cell_count": 312,
  "duration_ms": 842
}
```

---

# 30. Performance Targets for Portfolio Scale

Do not over-engineer.

Reasonable initial targets:

- summary API: < 300 ms locally
- comparison API: < 500 ms locally
- viewport H3 request: < 500 ms locally
- dashboard initial useful render: < 2 seconds after API is available

Pipeline runtime can be longer because it is offline/batch.

---

# 31. Security Scope

No authentication is required for the first portfolio MVP.

However:

- validate all request bodies
- parameterize database queries
- use ORM/query builder safely
- configure CORS narrowly
- never expose database credentials
- limit API payload size
- validate metric names and sorting fields

If deployed publicly later, add appropriate authentication/rate limiting then.

---

# 32. JD Skill Alignment

This project intentionally covers the core skills in the target Program Tooling & Analytics Developer JD.

| JD Skill | Project Coverage |
|---|---|
| Python | FastAPI, pipelines, geospatial processing, scoring |
| SQL | PostgreSQL/PostGIS queries and data modeling |
| React / TypeScript | Primary frontend |
| Streamlit / Dash / Flask UI | Not used; React/TypeScript satisfies the alternative frontend requirement |
| Plotly / D3 or similar | Plotly.js used for analytical visualization |
| Claude Code / generative coding tools | Used as an implementation assistant with review/test discipline |
| GeoPandas | Geospatial transformation and analysis |
| Shapely | Geometry operations |
| OSMnx | OpenStreetMap road-network ingestion/analysis |
| H3 | Spatial indexing and aggregation |
| Mapbox | Interactive geospatial rendering |
| OpenStreetMap | Primary public map/road data source |
| Graph / network analysis | OSMnx road graph metrics |
| Data pipelines | Batch geospatial/analytics pipeline |
| Internal dashboards | Core product |
| Messy/incomplete data | Explicit quality rules, confidence, missing-value handling |
| Databricks / PySpark | Not required for MVP; only add if data scale justifies distributed processing |
| Tableau / Looker | Not required for MVP; custom React/Plotly dashboard demonstrates equivalent decision-support work |
| Mobility/autonomous domain | Service-area decision-support use case with public/synthetic data |

Engineering rule:

> Do not add a technology solely to match a JD keyword. Add it only when it has a defensible role in the architecture.

For example, PySpark would be unnecessary for a few candidate cities and a portfolio-scale dataset. If later synthetic telemetry is expanded to a genuinely large dataset, a distributed-processing extension can be evaluated as a separate phase.

---

# 33. Future Enhancements

Only after the core project is complete:

- Databricks/PySpark version of pipeline
- Tableau/Looker export
- route-level analytics
- travel-time accessibility
- richer POI analysis
- scheduled pipeline refresh
- background worker
- event-driven refresh
- cloud deployment
- user-defined service-area drawing
- saved scenarios
- downloadable decision report

Do not add these before MVP completion.

---

# 34. First Implementation Milestone

The first meaningful demo should be:

```text
Foster City
    |
    v
OpenStreetMap / OSMnx
    |
    v
road-network metrics
    |
    v
H3 cells
    |
    v
PostgreSQL + PostGIS
    |
    v
FastAPI
    |
    v
React + Mapbox
```

The UI only needs to show:

- Foster City boundary
- H3 cells
- intersection density
- road density
- connectivity metric
- data-quality indicator
- analysis timestamp

Once that is stable, add comparison and scoring.

---

# 35. Success Criteria

The project succeeds if an interviewer can see that you know how to:

- start from a business decision
- model data intentionally
- design schemas
- build repeatable data pipelines
- work with Python and SQL
- process geospatial data
- expose stable APIs
- build a usable React interface
- test business logic
- handle missing/unreliable data
- communicate assumptions
- use AI coding tools responsibly
- maintain clean Git history

The project does **not** need millions of records, Kubernetes, ML, or excessive distributed-systems complexity to demonstrate those skills.

---

# 36. Recommended First Claude Code Prompt

Use something similar to:

```text
Read PLAN.md completely before writing code.

We are starting Phase 0 only. Do not implement application code yet.

Your task:
1. Review the product goal and MVP.
2. Identify inconsistencies, missing decisions, or over-engineering in PLAN.md.
3. Draft:
   - docs/architecture.md
   - docs/data-model.md
   - docs/scoring-model.md
   - the ADRs listed for Phase 0
4. Do not initialize the backend or frontend yet.
5. Do not commit anything.
6. At the end, summarize the architecture decisions, unresolved questions, and files created.

Important engineering rules:
- Prefer simple, testable architecture.
- Public/synthetic data only.
- Do not claim synthetic data is real.
- Do not add technologies that are not justified by a current requirement.
- All future Git commits must use the local Git identity configured for Kenil Gopani and must never add Claude attribution.
```

---

# 37. Recommended Development Philosophy

The goal is not:

> "Make Claude generate the whole project."

The goal is:

> "Use Claude Code as an implementation partner while keeping architecture, requirements, review, tests, and Git history under deliberate engineering control."

For every phase, understand the code Claude produces well enough to explain:

- why the component exists
- its input/output
- its failure cases
- its tests
- its tradeoffs
- what you would change at larger scale

That is what will make the project useful in an interview.
