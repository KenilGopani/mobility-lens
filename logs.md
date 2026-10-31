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

## Current handoff and remaining work

Phase 6 page implementation is complete. Its full live-data acceptance is **not certified yet**: no local API or Docker daemon was running during this session. Browser checks used the labeled test-only API, and automated UI tests used deterministic mocks. No real scores or live-data results were fabricated. The previously generated, untracked `graphify-out/` analysis folder was left out of feature commits.

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
