"""Export real local API examples and a traceable decision narrative for portfolio review."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "docs" / "sample-responses"
    output.mkdir(parents=True, exist_ok=True)

    def request(path, body=None):
        req = Request(
            args.api.rstrip("/") + path,
            data=json.dumps(body).encode() if body else None,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read())

    def save(name, payload):
        (output / name).write_text(json.dumps(payload, indent=2) + "\n")

    listing = request("/api/v1/service-areas?limit=200")
    areas = listing["items"][:3]
    if len(areas) < 2 or any(a["score"] is None for a in areas):
        raise ValueError(
            "Two or three successfully scored areas are required for the walkthrough"
        )
    comparison = request(
        "/api/v1/comparisons", {"service_area_ids": [a["id"] for a in areas]}
    )
    ranked = sorted(comparison["areas"], key=lambda a: a["rank"])
    leader = ranked[0]
    prefix = "/api/v1/service-areas/" + leader["service_area_id"]
    summary = request(prefix + "/summary")
    metrics = request(prefix + "/metrics")
    quality = request(prefix + "/quality")
    operations = request(prefix + "/operations")
    weights = {
        key: 1 if key == "intersection_density" else 0
        for key in comparison["scoring_model"]["weights"]
    }
    what_if = request(
        "/api/v1/scoring/preview",
        {"service_area_ids": [a["id"] for a in areas], "weights": weights},
    )
    for name, payload in [
        ("service-areas.json", listing),
        ("comparison.json", comparison),
        ("summary.json", summary),
        ("metrics.json", metrics),
        ("quality.json", quality),
        ("operations-synthetic.json", operations),
        ("what-if-intersections.json", what_if),
    ]:
        save(name, payload)
    lines = [
        "# A decision walkthrough",
        "",
        "This example uses persisted public OSM/Census analysis snapshots. It demonstrates the decision workflow and explicit assumptions, not a validated prediction of expansion success.",
        "",
        "## Baseline ranking",
        "",
        "| Area | Score / 100 | Rank |",
        "| --- | --- | --- |",
    ]
    lines += [
        "| {} | {:.2f} | {} |".format(a["name"], a["score"], a["rank"]) for a in ranked
    ]
    lines += [
        "",
        "{} leads under {} {} by {:.2f} points over {}. The small margin makes assumption review especially relevant.".format(
            leader["name"],
            comparison["scoring_model"]["name"],
            comparison["scoring_model"]["version"],
            leader["score"] - ranked[1]["score"],
            ranked[1]["name"],
        ),
        "",
        "## Why that score?",
        "",
        "| Metric | Raw | Normalized | Weight | Contribution |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        "| {} | {:.4f} | {:.4f} | {:.0%} | {:.2f} |".format(
            c["display_name"],
            c["raw_value"],
            c["normalized_value"],
            c["weight"],
            c["contribution"],
        )
        for c in leader["components"]
        if c["normalized_value"] is not None
    ]
    lines += [
        "",
        "Contributions sum to the score. Missing components would be excluded with reduced confidence and explicit warnings. Current confidence is a sample-size reliability factor; 100% does not imply map completeness, operational safety or certainty.",
        "",
        "## Challenge the assumption",
        "",
        "Set intersection density to 100% and all other weights to zero in What-if Analysis. This temporary scenario changes the ranking:",
        "",
        "| Area | Temporary score | Rank |",
        "| --- | --- | --- |",
    ]
    lines += [
        "| {} | {:.2f} | {} |".format(a["name"], a["score"], a["rank"])
        for a in sorted(what_if["areas"], key=lambda a: a["rank"])
    ]
    lines += [
        "",
        "The preview is not persisted. Restore the default model to return to baseline. This sensitivity is why weights are presented as assumptions rather than objective truth.",
        "",
        "## Inspect reliability and source",
        "",
        "Open Data Quality for each area. San Jose metadata completeness is below the configured 0.5 threshold in these snapshots. This measures tag presence, not geographic coverage. Review source/run timestamps, raw metrics, missing-value fractions and boundary-cell confidence before using the ranking.",
        "",
        "The geographic snapshots are from 2026-10-25. This walkthrough does not claim that public map data was refreshed on the capture date. See calibration.md for the observed ranges and reliability limitations.",
        "",
        "## Keep operational simulation separate",
        "",
        "Operations shows reproducible seeded route and issue scenarios with a persistent synthetic-data label. Completion/intervention rates and resolution times there are illustrative generated values, never observed fleet performance and never inputs to this geographic ranking.",
        "",
        "Machine-readable evidence: [comparison](sample-responses/comparison.json), [metrics](sample-responses/metrics.json), [quality](sample-responses/quality.json), [temporary preview](sample-responses/what-if-intersections.json), [synthetic operations](sample-responses/operations-synthetic.json).",
        "",
    ]
    (root / "docs" / "decision-walkthrough.md").write_text("\n".join(lines))
    print("Exported API examples and decision walkthrough.")


if __name__ == "__main__":
    main()
