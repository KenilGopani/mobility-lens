# Scoring Model

Deterministic weighted model. Weights and reference ranges are **assumptions, not objective truth**.

## Metric definitions (MVP)

Network: OSMnx `network_type="drive"`, simplified, as an undirected view for degree/density metrics. Cell and area geometry are measured in a local UTM CRS.

| Key | Definition | Unit | Direction |
|---|---|---|---|
| `intersection_density` | Nodes with `street_count >= 3` inside the region / region land area | per km2 | higher better |
| `road_density` | Sum of drivable edge length clipped to the region (undirected, each physical street counted once) / region area | km/km2 | higher better |
| `avg_node_degree` | Mean `street_count` over nodes inside the region | streets/node | higher better |
| `network_directness` | `1 / circuity_avg`, where circuity = edge length / straight-line distance between its endpoints, length-weighted | ratio (0,1] | higher better |
| `metadata_completeness` | Mean over tags {`maxspeed`, `lanes`, `name`} of the fraction of drivable edges having that tag | fraction | higher better |

"Region" is an H3 cell clipped to the service-area boundary for cell metrics, and the whole boundary for area metrics. Area metrics are computed directly on the whole area (area-weighted), **not** as a mean of cell values.

`metadata_completeness` is a tag-presence statistic. It is not geographic coverage and must not be labeled as such.

"Higher is better" is itself an assumption (denser, better-connected grids are treated as easier to serve). It is documented in `metric_definitions` and shown in the UI.

## Normalization

Method `minmax_fixed`, version `v1`:

```text
n = clip((raw - ref_min) / (ref_max - ref_min), 0, 1)       if higher_is_better
n = 1 - that value                                          otherwise
```

- Reference ranges are **fixed and versioned** in `metric_definitions`, not derived from the peer set. With only 2-3 areas, peer-relative min-max would force one area to 0 and one to 1 on every metric.
- Raw values outside the range are clipped; clipping is recorded in `metadata`.
- `raw = NULL` gives `normalized = NULL` (never 0).
- `ref_max == ref_min` is a configuration error and is rejected at validation.

Provisional reference ranges (to be calibrated against real Bay Area output in Phase 4, then frozen as `v1`):

| Key | ref_min | ref_max |
|---|---|---|
| intersection_density | 0 | 150 |
| road_density | 0 | 25 |
| avg_node_degree | 2.0 | 3.5 |
| network_directness | 0.7 | 1.0 |
| metadata_completeness | 0 | 1 |

## Weights

Default model `baseline` v1:

```text
intersection_density   0.25
road_density           0.25
avg_node_degree        0.20
network_directness     0.15
metadata_completeness  0.15
```

## Score

```text
score = 100 * sum(weight_i * normalized_i)        over available metrics, weights renormalized
```

Rules:

1. Weights must contain exactly the required keys, each >= 0, summing to 1.0 (tolerance 1e-6); otherwise rejected.
2. Metrics with `normalized = NULL` are excluded and the remaining weights are renormalized to sum to 1. A warning `missing_metric:<key>` is emitted.
3. Let `available_weight` be the original weight mass of available metrics. If `available_weight < 0.5`, `score = NULL` with warning `insufficient_data` (a score from under half the model is not trustworthy).
4. A value of `0` is a valid value and is included.
5. Score is within [0, 100] by construction.
6. `contribution_i = 100 * (weight_i / available_weight) * normalized_i`; contributions sum to the score (tested to within floating-point tolerance).

## Confidence

Each metric has a confidence in [0, 1]:

- Cell metrics: `min(1, overlap_ratio / 0.5)` scaled further by a sample-size factor `min(1, node_count / 10)` for node-based metrics.
- Area metrics: derived from data-quality inputs (node count, completeness), see DQ rules.

Score confidence:

```text
confidence = available_weight * sum(w'_i * c_i)          w'_i = renormalized weights
```

So both low-confidence components and missing components reduce overall confidence, and neither is hidden.

Confidence is a **reliability signal**, not a probability.

## Output shape

```json
{
  "score": 84.7,
  "confidence": 0.91,
  "components": [
    {"metric": "road_density", "raw_value": 18.3, "normalized_value": 0.88,
     "weight": 0.25, "contribution": 22.0, "confidence": 0.95}
  ],
  "warnings": []
}
```

## Data-quality rules

| Code | Condition | Severity | Persisted |
|---|---|---|---|
| DQ-001 | A required metric is unavailable | critical | yes |
| DQ-002 | `metadata_completeness` < 0.5 (configurable) | warning | yes |
| DQ-003 | Analysis area < 2 km2 (configurable) | warning | yes |
| DQ-004 | Fewer than 100 network nodes (configurable) | critical | yes |
| DQ-005 | OSM fetch returned < expected minimum edges for area size | critical | yes |
| DQ-006 | Metric deviates > 2 MAD from peer areas | info | no, computed at read time |

Each finding carries code, severity, human-readable message, and `affected_fraction` where applicable. Thresholds live in run `parameters` so a run records what it was judged against.

## Testing

Required unit tests are listed in PLAN.md section 16 and are written before the implementation.
