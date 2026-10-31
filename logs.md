# Implementation log

## Working conventions

- Each feature is a separate Conventional Commit. Add implementation, validation and handoff notes here before committing.
- Git author and committer: Kenil Gopani, using the repository's configured email.
- Preserve unavailable values as `null`; scores and rankings come from the backend.
- Use `docs/api.md` and `docs/openapi.json` as the implemented API contract. Accepted ADRs supersede earlier choices in `PLAN.md`.

## Baseline reviewed — 2026-10-31

Backend implements domain/migrations, Census boundaries, cached OSM ingestion, H3 cells, metrics, normalization, weighted scoring, quality rules and Phase 5 read APIs. Frontend previously contained only the overview placeholder and health client. Existing validation: 101 selected backend unit tests and 5 frontend tests passed. Database integration/contract tests were not rerun during the initial review.

## Phase 6 — Frontend MVP

### Feature 1: API integration and executive overview

- Added typed v1 requests with cancellation, pagination, POST payloads and server error messages.
- Added responsive navigation shell, shared loading/error/empty states, confidence/value formatting and lazy Plotly charts.
- Overview shows live rankings, leading candidate, confidence, raw metrics, contribution/weight breakdown, warnings and analysis timestamps.
- Scores stay server-owned; absent metrics display `Unavailable`, including a fully unscored candidate set.
- Validation: frontend lint, strict typecheck, 7 tests and production build passed. Plotly is lazy-loaded; its vendor chunk exceeds the default size advisory.
- Next: implement comparison, quality, temporary weights and geographic exploration.

### Feature 2: Area comparison

- Added selection of two or three candidates, backed by `/comparisons` and isolated query keys.
- Shared results show Plotly score contributions, raw/normalized metrics, effective weights, confidence, selected-set ranks, timestamps, strengths, risks and peer-outlier warnings.
- Charts preserve null gaps and reject non-finite numbers; tables retain exact unavailable states.
- Validation: frontend lint, strict typecheck and 8 tests passed, including selection constraints, zero scores, null metrics and confidence state.

### Feature 3: Data quality and provenance

- Added area selection via shareable URL, severity filtering, persisted findings, missing-value counts/shares and low-confidence cell summaries.
- Shows analysis/run metadata, boundary source and full public source provenance, plus the distinction between tag completeness and geographic coverage.
- Added configurable chart axis labels for completeness counts.
- Validation: frontend lint, strict typecheck and 9 tests passed; quality interaction covers severity filtering, provenance and unavailable shares for an empty grid.

### Feature 4: Temporary what-if scoring

- Added model-backed weight sliders, one-to-three area selection, 300 ms debounced/cancellable server previews and one-click baseline restoration.
- Weight redistribution uses integer basis points and largest remainders so weights stay nonnegative and total exactly 100% to API tolerance, including 100%/0% edge cases.
- Outdated results are hidden during updates; temporary assumptions are visibly labeled and never persisted.
- Validation: frontend lint, strict typecheck and 11 tests passed. Tests cover repeated redistribution, 100%/0% boundaries, preview payloads, visible score changes and restoration.

### Feature 5: Interactive geographic exploration

- Added lazy MapLibre map with service-area boundary, normalized H3 fill colors, low-confidence outlines, safe text tooltips and selected-cell details.
- Map movement fetches only the visible bounding box (2,000-cell limit), with request cancellation and explicit truncation guidance.
- Area/metric selection is shareable through URL parameters. Added accessible cell table, source/run timestamps, raw values and documented normalization assumptions.
- Map/WebGL failures retain the usable cell table. Overview links now open geographic exploration and quality review.
- Validation: frontend lint, strict typecheck, 12 tests and production build passed. Map test covers bounded queries, metric changes, zero values, selected cells and truncation. Browser review follows in the integration/handoff entry.

### Map worker integration fix

- Browser QA exposed a worker URL failure in MapLibre 6 when Vite prebundles the library. Added an explicit Vite-bundled module-worker URL so dev and production both include the worker and shared imports.
- Verified rendered H3 cells, gray unavailable values, amber low-confidence outlines, area/metric changes and zoom controls in the browser.
- Validation: lint, format check, strict typecheck, 15 tests and production build passed.

### Integration, browser QA and handoff — 2026-10-31

- Added an isolated, explicitly synthetic browser fixture server at `127.0.0.1:8011`, importing the backend scoring engine. It is opt-in, writes no database records and is excluded from the production app.
- Browser-checked all five pages: overview ranking/chart; two-area comparison; severity filtering; weight redistribution to 100% and baseline restoration; San Jose area/metric selection; H3 fills, low-confidence outlines and map zoom. Checked the narrow layout and 1440 px desktop layout.
- Browser verification caught and resolved the MapLibre module-worker integration issue. Added page-scroll reset on route changes and 0.01% slider precision to match displayed weights.
- Expanded API tests for pagination, viewport bbox, cancellable POST payloads and server error messages. What-if test now checks that Plotly receives the updated score-contribution series.
- Replaced stale README status with current setup, architecture, checks and test-fixture instructions.
- Final automated verification: frontend lint, formatting, strict typecheck, **15 tests** and production build passed. Fixture Python passed Ruff and compilation. Backend application code was not changed.

## Feature commit index

| Module                                | Commit                                                                              |
| ------------------------------------- | ----------------------------------------------------------------------------------- |
| API client, shell, executive overview | `dbe8044` — `feat(frontend): build API-backed executive overview`                   |
| Comparison                            | `524a6eb` — `feat(frontend): compare service areas with score breakdowns`           |
| Data quality                          | `a9c1c96` — `feat(frontend): surface data quality findings and provenance`          |
| What-if analysis                      | `de8c0c0` — `feat(frontend): preview temporary scoring weights`                     |
| Interactive H3 map                    | `6967128` — `feat(frontend): explore service areas on an interactive H3 map`        |
| Map worker integration                | `eda4d00` — `fix(frontend): bundle MapLibre workers for development and production` |

## Historical handoff after Phase 6

This earlier handoff is superseded by the full-roadmap completion entries below. At that time Phase 6 page implementation was complete, but live-data acceptance was **not certified yet**: no local API or Docker daemon was running during this session. Browser checks used the labeled test-only API, and automated UI tests used deterministic mocks. No real scores or live-data results were fabricated. The previously generated, untracked `graphify-out/` analysis folder was left out of feature commits.

1. Start Docker/PostGIS and follow README setup. Seed all three candidate areas and produce successful runs with the same pipeline (Phase 7). Existing boundary files alone do not prove those runs exist.
2. Rerun backend integration/contract tests against a dedicated `_test` database, then execute the six PLAN E2E flows against the real API. The browser checks above are manual verification, not an automated Playwright suite.
3. Confirm real score calibration/reference ranges and inspect metadata completeness/source quality before making expansion decisions.
4. Profile live queries, large-city cell truncation and map request timing before adding indexes/caches (Phase 9). Lazy MapLibre and Plotly vendor chunks exceed Vite's 500 kB advisory; the initial app is separate.
5. Review dependency audit findings before deployment: npm reported 12 moderate findings during installation; no forced dependency upgrades were applied.
6. Keep Phase 8 synthetic operational analytics deferred until the geospatial MVP is validated. Phase 10 screenshots, demo and portfolio polish can follow real-data acceptance.

### Continuing development

- Main UI: `frontend/src/pages/`. Shared states/formatters, charts and score tables: `frontend/src/components/`.
- API shapes and functions: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`; match `docs/openapi.json` when changing contracts.
- Map lifecycle/worker/layers: `frontend/src/features/map/AreaMap.tsx`. Pure weight redistribution: `frontend/src/features/scoring/weights.ts`.
- Add a dated feature entry here with implementation, validation and limitations, then make one Conventional Commit for that module. Use the configured repository author/committer identity.

## Full roadmap completion — 2026-10-31

### Phase 7: Candidate verification and batch recovery

- Started the existing PostGIS container and verified persisted real OSM/Census runs for all three cities. Latest results: Foster City 127 cells / 52.03 score; Mountain View 350 / 52.68; San Jose 4,865 / 44.13. These are existing 2026-10-25 snapshots, not newly fetched observations.
- Full pre-change backend verification passed: 236 tests, Ruff and strict MyPy. All database/contract tests used the dedicated `_test` database.
- Added `analyze-all` with failure isolation and explicit `--resume` batch recovery. Recovery skips a successful run only at the current pipeline version and configured H3 resolution; omit resume after input/config changes or when a fresh snapshot is required.
- Validation: Ruff, strict MyPy and two new batch tests passed; `analyze-all --resume` correctly skipped all three compatible successful runs.

### Phases 6–7: Automated browser acceptance and dependency audit

- Added Playwright coverage for all six planned geospatial E2E flows (map area/metric flows share one test), with CI fixture mode and real-API local mode. All five browser tests passed against the persisted real city analyses.
- Configured CI browser installation and failure artifacts; excluded generated reports from source lint/formatting.
- Applied a scoped patched `minimatch` override rather than downgrading the lint toolchain. npm audit now reports zero vulnerabilities.
- Validation: frontend lint, typecheck and 15 unit tests passed, plus real-API browser tests.

### Phase 8 module 1: Synthetic scenarios and read APIs

- Added ADR-008, an additive migration and three tables: simulation runs, route events and operational issues. Each table enforces `is_synthetic = true`; issue timestamps/status and route measures have database constraints.
- Added deterministic seeded generation, scenario deduplication, source-run pinning and transactional `simulate-area` CLI. Requires a successful geographic run and leaves all geographic metrics/scores untouched.
- Added paginated scenario listing and per-area operational summaries with daily UTC series, completion/intervention rates, completed-trip duration, severity/status counts and resolution hours. Responses explicitly set `synthetic: true`.
- Migration review excluded extension-owned tables from autogeneration; the reviewed migration only creates the three application tables. No PostGIS/Tiger extension tables are altered.
- Validation: full backend suite **247 passed**, Ruff formatting/lint and strict MyPy passed; includes migration upgrade/downgrade, reproducibility, duplicate prevention, synthetic-only constraints, aggregate math and HTTP contract tests.

### Phase 8 module 2: Operational analytics dashboard

- Added a separate Operations page with persistent synthetic-only labeling, area/scenario selection, completion and intervention rates, trip duration, severity counts, resolution time, daily trend/table and pinned-run/seed provenance.
- Geographic scoring remains server-owned and unchanged; a simulation is never described as observed performance.
- Expanded isolated CI fixtures and browser acceptance to cover the dashboard. Generated 500-event scenarios for each existing city analysis via the new CLI, using seeds 42/43/44.
- Validation: frontend lint, strict typecheck, **16 unit tests**, production build and **6 real-API browser tests** passed (the original six flows plus operations; area/metric flows share a test).

### Phase 9: Observability, recovery and measured performance

- Added generated request IDs, response timing headers, structured route/status/duration logs, database readiness (503 on dependency failure), and per-stage warning/critical counts.
- Added preview-first stale-running recovery with explicit apply and row-lock protection; recent and successful runs are excluded. Existing bounded OSM retry, transactional rollback and batch resume provide retry/recovery without adding background infrastructure.
- Public provenance excludes workstation cache locations; source identifiers remain available and the database retains full local provenance.
- Added repeatable `benchmark-api` with local HTTP samples and a parameterized EXPLAIN ANALYZE/BUFFERS plan. The captured viewport plan uses `ix_h3_cells_boundary`; no speculative new indexes or caches were added.
- Measured final p95 (10 warm samples): summary 5.04 ms, comparison 3.78 ms, viewport 54.66 ms, full_area_cells 159.73 ms, synthetic_operations 22.05 ms.
- Added `calibration-report` and reviewed all three real city outputs. Retained fixed v1 ranges/weights rather than tuning to force an outcome; no area-level clipping was observed. Corrected the written directness definition to match the existing, unchanged computation.
- Validation: full backend **250 tests passed**, Ruff and strict MyPy passed; stale-run preview found no interrupted runs needing changes. See `docs/reliability.md`, `docs/performance.json` and `docs/calibration.md` for evidence and limitations.

### Phase 10: Portfolio artifacts and delivery checklist

- Added an opt-in `npm run demo:record` workflow and captured a short WebM walkthrough plus overview, real H3 map, comparison and clearly labeled synthetic Operations screenshots.
- Captured useful overview render at 738 ms in the local browser. Screenshots use actual persisted OSM/Census results; only the Operations scenario is synthetic. Capture metadata records that distinction.
- Added reusable Mermaid architecture source, public API example JSON, an export script and a source-grounded decision walkthrough. The example explains Mountain View's 0.65-point baseline lead and the temporary intersection-only model that favors Foster City.
- Expanded README with problem/audience, screenshots/demo, architecture/stack/data flow, metrics/assumptions, quality design, synthetic disclaimer, setup/tests, tradeoffs and optional future work. Updated PLAN with a phase-by-phase delivery status while preserving the original roadmap history.
- Final checks: **250 backend tests passed, 92% branch-inclusive coverage**, Ruff format/lint, strict MyPy, **16 frontend tests**, ESLint/Prettier, strict TypeScript and production build passed. **6 browser tests passed** against the real API and in CI fixture mode; recording passed separately. The normal suite intentionally skips the opt-in demo-recording test and the backend excludes external live-data tests by default.
- Live migration is at `0002 (head)`; Alembic check reports no new upgrade operations. npm audit reports zero vulnerabilities. Remote CI was configured but not triggered, and no public deployment/push/merge was performed.

## Current delivery status

All defined phases 0–10 are implemented and locally validated for the portfolio scope. Earlier historical handoff limitations above have been resolved by the full-roadmap entries. The PLAN's optional future enhancements are outside these delivered phases.

| Phase | Status and evidence |
| --- | --- |
| 0: Design | Architecture, domain/scoring/API documents and accepted ADRs |
| 1: Foundation | Toolchains, PostGIS Compose, lint/type/build checks and CI workflows |
| 2: Database | ORM/schema parity, migration round trips and persistence tests |
| 3: Ingestion | Public OSM/Census runs, deterministic spatial fixtures and atomic rollback |
| 4: Scoring | Pure normalization/scoring tests and real-output reference-range review |
| 5: API | OpenAPI contract, consistent errors and real PostGIS integration tests |
| 6: Frontend | Five decision pages with component and browser acceptance |
| 7: Candidates | Three cities, same pipeline/version/resolution; batch execution/recovery |
| 8: Operations | Strict synthetic labeling, seeded scenarios, read APIs and dashboard |
| 9: Reliability | Request diagnostics/readiness, recovery, measured latency and spatial query plan |
| 10: Portfolio | Screenshots, video, API examples, diagram and decision walkthrough |

### New module commits

- `df9ba1b`: candidate batch analysis and recovery.
- `ba4d612`: real-API/CI browser workflows and patched dependency tooling.
- `62eb274`: synthetic scenario schema, generation and read APIs.
- `e129904`: explicitly synthetic operational dashboard.
- `1e4d56d`: diagnostics, recovery, performance evidence and range review.
- Portfolio artifacts and the current checklist are included in the accompanying `docs(portfolio): complete roadmap evidence and demo handoff` commit.

### Continuing from this release

Use README for setup, `docs/reliability.md` for recovery/profiling and `docs/decision-walkthrough.md` for the demo narrative. Refresh public snapshots deliberately through the CLI; the captured geographic runs are from 2026-10-25. Geographic weights/ranges remain explicit assumptions, and simulated route outcomes are never evidence of real service performance. Local validation does not constitute production certification. If continuing with optional features or deployment, append a new dated module entry here and keep the same focused-commit convention and repository owner identity.

### README and MIT license — 2026-10-31

- Reworked the README around the expansion-planning use case, the six UI views, existing screenshots/demo, scoring assumptions and the batch/API/frontend architecture.
- Added a concise implementation map and links to detailed documentation, with brief local setup instructions at the end.
- Added the MIT source-code license with Kenil Gopani's copyright; retained the distinction between project licensing and third-party data/dependency licenses.
- Validation: checked local documentation/image links, Markdown formatting, setup commands against the CLI, and the final diff. Documentation-only change; application tests were not rerun.
