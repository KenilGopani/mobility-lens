"""Review fixed reference assumptions against stored real area outputs without mutating them."""

from sqlalchemy.orm import Session

from app.repositories import analysis_runs, metric_definitions, metrics, service_areas


def report(session: Session) -> str:
    areas = service_areas.list_light(session)
    runs = analysis_runs.latest_succeeded_for_areas(session, [a.id for a in areas])
    values = metrics.area_metrics_for_runs(session, [r.id for r in runs.values()])
    definitions = metric_definitions.get_all(session)
    lines = [
        "# Reference-range review",
        "",
        (
            "This is a descriptive review of the latest persisted public-data "
            "snapshots, not an outcome-based validation of service feasibility. "
            "Fixed v1 ranges and weights remain explicit modeling assumptions. No "
            "peer-relative rescaling or automatic parameter fitting is performed."
        ),
        "",
        "| Area | Metric | Raw value | Fixed range | Normalized | Clipped |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for area in areas:
        run = runs.get(area.id)
        if run is None:
            raise ValueError(f"{area.slug} has no successful analysis")
        for key, d in sorted(definitions.items()):
            m = values.get(run.id, {}).get(key)
            raw = m.raw_value if m else None
            norm = m.normalized_value if m else None
            clipped = (
                raw is not None
                and d.ref_min is not None
                and d.ref_max is not None
                and not d.ref_min <= raw <= d.ref_max
            )
            lines.append(
                f"| {area.name} | {key} | {raw if raw is not None else 'Unavailable'} "
                f"| {d.ref_min}-{d.ref_max} | {norm if norm is not None else 'Unavailable'} "
                f"| {'yes' if clipped else 'no'} |"
            )
    lines += [
        "",
        "## Decision",
        "",
        (
            "Retain and freeze the documented v1 ranges for this portfolio release. "
            "Three city samples are too few to justify fitting a stronger "
            "expansion-success claim or tuning weights to force a preferred city. "
            "Geographic density/connectivity/directness preferences are explicit "
            "assumptions, not established operational advantages."
        ),
        "",
        (
            "Area outputs are calculated directly on each land-clipped boundary; "
            "they are not averages of cell values. Small boundary cells may clip "
            "against the same fixed reference ranges and have reduced "
            "overlap/sample confidence. Metadata completeness measures tag "
            "presence, not geographic coverage."
        ),
        "",
        (
            "The present area-confidence implementation uses network sample size. A "
            "value of 1 means its sample-size factor reached the threshold; it does "
            "not establish map completeness, operational safety or a probability of "
            "success. Quality findings and raw provenance must be inspected "
            "separately."
        ),
        "",
        (
            "A future range/formula change requires a new normalization version and "
            "new analysis runs. Do not silently edit historical metric definitions. "
            "Refresh public snapshots through the CLI when needed; this review does "
            "not fetch new data."
        ),
        "",
    ]
    return "\n".join(lines)
