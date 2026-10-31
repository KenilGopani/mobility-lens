# ADR-008: Reproducible synthetic operational scenarios

**Status:** Accepted

## Context
The geospatial pipeline and all three city snapshots have passed database/contract validation. Phase 8 adds a separate operational-analytics example. No actual fleet outcomes are available.

## Decision

- `simulation_runs` pins an existing successful analysis run and records seed, generator version, event count, simulated start time and a unique scenario key.
- `route_events` records simulated attempt times, distance, duration, completion and intervention count. `operational_issues` records simulated category, severity, status and resolution time.
- All three tables require `is_synthetic = true` via non-null CHECK constraints. APIs return `synthetic: true`; the operations page always displays a synthetic-data banner.
- A pure seeded generator creates repeatable event content. Repeating identical inputs returns the existing scenario, without appending duplicate events. Writes are one CLI transaction; HTTP endpoints are read-only.
- Summary metrics: route completion fraction (completed / attempts), intervention fraction (attempts with >=1 intervention / attempts), mean duration of completed attempts, issue counts by severity, and mean resolution hours for resolved issues. Empty denominators return null.
- Daily series use simulated UTC dates. Scenarios are illustrations, not forecasts, calibration data or evidence about service feasibility.
- Scenario records never affect normalization, geographic scores, confidence or rankings.

## Consequences
The original five-page geospatial workflow remains usable without simulations. Operational analytics is opt-in through a batch CLI command and a separate page. No proprietary information, production inference or city-specific behavior is implied by synthetic events.
