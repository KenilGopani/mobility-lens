# A decision walkthrough

This example uses persisted public OSM/Census analysis snapshots. It demonstrates the decision workflow and explicit assumptions, not a validated prediction of expansion success.

## Baseline ranking

| Area          | Score / 100 | Rank |
| ------------- | ----------- | ---- |
| Mountain View | 52.68       | 1    |
| Foster City   | 52.03       | 2    |
| San Jose      | 44.13       | 3    |

Mountain View leads under baseline v1 by 0.65 points over Foster City. The small margin makes assumption review especially relevant.

## Why that score?

| Metric                | Raw     | Normalized | Weight | Contribution |
| --------------------- | ------- | ---------- | ------ | ------------ |
| Road density          | 10.2295 | 0.4092     | 25%    | 10.23        |
| Average node degree   | 2.9712  | 0.6474     | 20%    | 12.95        |
| Network directness    | 0.9376  | 0.7922     | 15%    | 11.88        |
| Intersection density  | 42.5500 | 0.2837     | 25%    | 7.09         |
| Metadata completeness | 0.7019  | 0.7019     | 15%    | 10.53        |

Contributions sum to the score. Missing components would be excluded with reduced confidence and explicit warnings. Current confidence is a sample-size reliability factor; 100% does not imply map completeness, operational safety or certainty.

## Challenge the assumption

Set intersection density to 100% and all other weights to zero in What-if Analysis. This temporary scenario changes the ranking:

| Area          | Temporary score | Rank |
| ------------- | --------------- | ---- |
| Foster City   | 39.58           | 1    |
| Mountain View | 28.37           | 2    |
| San Jose      | 23.81           | 3    |

The preview is not persisted. Restore the default model to return to baseline. This sensitivity is why weights are presented as assumptions rather than objective truth.

## Inspect reliability and source

Open Data Quality for each area. San Jose metadata completeness is below the configured 0.5 threshold in these snapshots. This measures tag presence, not geographic coverage. Review source/run timestamps, raw metrics, missing-value fractions and boundary-cell confidence before using the ranking.

The geographic snapshots are from 2026-10-25. This walkthrough does not claim that public map data was refreshed on the capture date. See calibration.md for the observed ranges and reliability limitations.

## Keep operational simulation separate

Operations shows reproducible seeded route and issue scenarios with a persistent synthetic-data label. Completion/intervention rates and resolution times there are illustrative generated values, never observed fleet performance and never inputs to this geographic ranking.

Machine-readable evidence: [comparison](sample-responses/comparison.json), [metrics](sample-responses/metrics.json), [quality](sample-responses/quality.json), [temporary preview](sample-responses/what-if-intersections.json), [synthetic operations](sample-responses/operations-synthetic.json).
