# Reference-range review

This is a descriptive review of the latest persisted public-data snapshots, not an outcome-based validation of service feasibility. Fixed v1 ranges and weights remain explicit modeling assumptions. No peer-relative rescaling or automatic parameter fitting is performed.

| Area | Metric | Raw value | Fixed range | Normalized | Clipped |
| --- | --- | --- | --- | --- | --- |
| Foster City | avg_node_degree | 2.6822323462414577 | 2.0-3.5 | 0.4548215641609718 | no |
| Foster City | intersection_density | 59.36442655315067 | 0.0-150.0 | 0.3957628436876712 | no |
| Foster City | metadata_completeness | 0.6339031339031339 | 0.0-1.0 | 0.6339031339031339 | no |
| Foster City | network_directness | 0.9329832810413073 | 0.7-1.0 | 0.7766109368043579 | no |
| Foster City | road_density | 11.883523053438473 | 0.0-25.0 | 0.4753409221375389 | no |
| Mountain View | avg_node_degree | 2.971172325432415 | 2.0-3.5 | 0.6474482169549433 | no |
| Mountain View | intersection_density | 42.54996321684504 | 0.0-150.0 | 0.28366642144563364 | no |
| Mountain View | metadata_completeness | 0.7019005847953217 | 0.0-1.0 | 0.7019005847953217 | no |
| Mountain View | network_directness | 0.9376481707228626 | 0.7-1.0 | 0.7921605690762086 | no |
| Mountain View | road_density | 10.229489228431174 | 0.0-25.0 | 0.40917956913724696 | no |
| San Jose | avg_node_degree | 2.7926759214935375 | 2.0-3.5 | 0.528450614329025 | no |
| San Jose | intersection_density | 35.71775604244828 | 0.0-150.0 | 0.23811837361632185 | no |
| San Jose | metadata_completeness | 0.49092711719812776 | 0.0-1.0 | 0.49092711719812776 | no |
| San Jose | network_directness | 0.9396662187373395 | 0.7-1.0 | 0.7988873957911315 | no |
| San Jose | road_density | 8.259087089603593 | 0.0-25.0 | 0.33036348358414375 | no |

## Decision

Retain and freeze the documented v1 ranges for this portfolio release. Three city samples are too few to justify fitting a stronger expansion-success claim or tuning weights to force a preferred city. Geographic density/connectivity/directness preferences are explicit assumptions, not established operational advantages.

Area outputs are calculated directly on each land-clipped boundary; they are not averages of cell values. Small boundary cells may clip against the same fixed reference ranges and have reduced overlap/sample confidence. Metadata completeness measures tag presence, not geographic coverage.

The present area-confidence implementation uses network sample size. A value of 1 means its sample-size factor reached the threshold; it does not establish map completeness, operational safety or a probability of success. Quality findings and raw provenance must be inspected separately.

A future range/formula change requires a new normalization version and new analysis runs. Do not silently edit historical metric definitions. Refresh public snapshots through the CLI when needed; this review does not fetch new data.
