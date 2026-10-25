# ADR-005: Transparent weighted scoring instead of ML

**Status:** Accepted

## Context
There is no labeled outcome data, and the audience needs to challenge assumptions. An opaque model would be unjustified and unexplainable.

## Decision
Use a deterministic weighted sum of normalized metrics. Normalization uses fixed, versioned reference ranges, not peer-relative min-max, because with 2-3 areas peer-relative scaling is degenerate. Missing metrics are excluded explicitly with renormalized weights, a warning, and reduced confidence. Below 50% available weight the score is `NULL`. Scoring is one pure function, reused by persistence, comparison, and what-if preview.

Full rules: [scoring-model.md](../scoring-model.md).

## Consequences
- Every score decomposes into raw value, normalized value, weight, and contribution.
- Weights and ranges are assumptions and are documented as such.
- Fixed ranges need calibration (Phase 4) and a version bump if changed.
