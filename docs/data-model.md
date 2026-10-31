# Data Model

PostgreSQL 16 + PostGIS. All geometries are stored in EPSG:4326 (WGS84). Metrics requiring metric units are computed in a projected UTM CRS inside the pipeline and never stored in projected form.

## Entities

| Entity | Meaning |
|---|---|
| ServiceArea | A candidate geographic area |
| AnalysisRun | One execution of the pipeline for one service area |
| H3Cell | A shared spatial unit (global, reusable across areas and runs) |
| AnalysisRunCell | Which cells a run covered, and how much of each cell lies inside the boundary |
| MetricDefinition | What a metric is, its direction, normalization reference range, and version |
| CellMetric / AreaMetric | Raw value, normalized value, confidence |
| ScoringModel | Named, versioned weight set |
| AreaScore | Score + confidence + breakdown for (run, scoring model) |
| DataQualityFinding | Explicit quality issue for a run |

## Tables

Follows PLAN.md section 8, with the refinements marked **(changed)**.

```text
service_areas
  id UUID PK
  name VARCHAR NOT NULL
  slug VARCHAR UNIQUE NOT NULL
  boundary GEOMETRY(MULTIPOLYGON, 4326) NOT NULL
  source VARCHAR NOT NULL                -- e.g. "census-cb-2023:<GEOID>" (default) or "osm-nominatim:<osm_id>"
  created_at, updated_at TIMESTAMPTZ

analysis_runs
  id UUID PK
  service_area_id UUID FK NOT NULL
  pipeline_version VARCHAR NOT NULL
  parameters JSONB NOT NULL              -- h3_resolution, network_type, thresholds
  status VARCHAR NOT NULL                -- running | succeeded | failed   (CHECK)   (changed: constrained)
  started_at TIMESTAMPTZ NOT NULL
  completed_at TIMESTAMPTZ NULL
  error_message TEXT NULL
  source_metadata JSONB NOT NULL         -- OSM query, cache key, fetched_at, node/edge counts

h3_cells
  h3_index VARCHAR PK
  resolution INT NOT NULL
  boundary GEOMETRY(POLYGON, 4326) NOT NULL   -- GiST index (needed for viewport queries in MVP) (changed)
  centroid GEOMETRY(POINT, 4326) NOT NULL

analysis_run_cells
  analysis_run_id UUID FK, h3_index FK
  overlap_ratio DOUBLE PRECISION NOT NULL      -- 0..1 share of the cell inside the boundary (CHECK)
  PK (analysis_run_id, h3_index)

metric_definitions
  key VARCHAR PK
  display_name, description, unit
  higher_is_better BOOLEAN NOT NULL
  normalization_method VARCHAR NOT NULL        -- "minmax_fixed"
  ref_min DOUBLE PRECISION, ref_max DOUBLE PRECISION   -- fixed reference range     (changed: added)
  version VARCHAR NOT NULL

cell_metrics
  analysis_run_id, h3_index, metric_key  -> PK
  raw_value, normalized_value, confidence DOUBLE PRECISION NULL
  metadata JSONB
  FK (analysis_run_id, h3_index) -> analysis_run_cells                               (changed: composite FK)

area_metrics
  analysis_run_id, metric_key -> PK
  raw_value, normalized_value, confidence DOUBLE PRECISION NULL

scoring_models
  id UUID PK
  name, version VARCHAR
  weights JSONB NOT NULL
  normalization_version VARCHAR NOT NULL
  is_default BOOLEAN NOT NULL DEFAULT false    -- partial unique index: at most one default   (changed: added)
  created_at TIMESTAMPTZ
  UNIQUE (name, version)

area_scores
  analysis_run_id, scoring_model_id -> PK
  score DOUBLE PRECISION NULL                  -- NULL when too little data (see scoring-model.md)  (changed: nullable)
  confidence DOUBLE PRECISION NOT NULL
  component_breakdown JSONB NOT NULL
  calculated_at TIMESTAMPTZ NOT NULL

data_quality_findings
  id UUID PK
  analysis_run_id UUID FK
  rule_key VARCHAR NOT NULL                    -- DQ-001 ... DQ-005
  severity VARCHAR NOT NULL                    -- info | warning | critical (CHECK)
  message TEXT NOT NULL
  affected_fraction DOUBLE PRECISION NULL
  metadata JSONB
```

Constraints: CHECK `normalized_value BETWEEN 0 AND 1`, `confidence BETWEEN 0 AND 1`, `overlap_ratio BETWEEN 0 AND 1`.

## Design decisions

- **Nullability carries meaning.** `NULL` raw/normalized = unavailable. `0` is a real value. Confidence is separate from value.
- **H3 cells are shared**, not per-run; run membership and overlap live in `analysis_run_cells`.
- **DQ-006 (peer outlier) is not persisted.** It depends on the set of areas being compared, so it is computed at read time by the comparison service. Stored findings are limited to DQ-001..005, which depend only on a single run.
- **Idempotency:** re-running an area creates a new `analysis_runs` row. Old runs are retained. Failed runs keep their error and partial writes are rolled back (single transaction for data tables).
- **Indexes in MVP:** PKs, FKs used by joins, GiST on `h3_cells.boundary` and `service_areas.boundary`. Anything else waits for Phase 9 query-plan evidence.
- **Synthetic data (Phase 8)** gets its own tables with a mandatory `is_synthetic` column that is always `true` and a CHECK constraint enforcing it. Not part of the MVP schema.

## Metric keys (MVP)

`intersection_density`, `road_density`, `avg_node_degree`, `network_directness`, `metadata_completeness`. See [scoring-model.md](scoring-model.md) for definitions.

## Synthetic operational entities (Phase 8)

`simulation_runs` references a successful `analysis_runs` row and stores the seed, generator version, immutable scenario key, parameters and simulated start time. `route_events` and `operational_issues` belong to that scenario and cascade on scenario deletion. All three tables enforce non-null `is_synthetic = true`.

Route attempts contain times, distance, duration, completion and intervention count. Issues contain category, severity, open/resolved state and consistent resolution timestamps. API aggregates are read from these tables, never mixed into geographic scores. See ADR-008 for denominator definitions and labeling rules.
