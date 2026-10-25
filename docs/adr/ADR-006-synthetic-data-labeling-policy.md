# ADR-006: Synthetic data labeling policy

**Status:** Accepted

## Context
Phase 8 adds simulated operational data. It must never be mistaken for real fleet or company data.

## Decision
- All synthetic tables have a non-null `is_synthetic` boolean with a CHECK constraint forcing `true`, and are prefixed or documented as synthetic.
- API responses for synthetic metrics include `"synthetic": true`.
- The UI shows a persistent "Synthetic data" badge on any view containing them.
- Generators are seeded and deterministic, and the seed is stored on the simulation run.
- Documentation and README state that no proprietary data is used.
- Synthetic data is not mixed into the geospatial score unless an explicit, labeled scoring model version includes it.

## Consequences
- Slightly more schema and UI work, in exchange for protection against misrepresentation.
- Not started until the geospatial MVP is stable.
