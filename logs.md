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
