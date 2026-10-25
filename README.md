# MobilityLens

A full-stack geospatial decision-intelligence platform for comparing mobility service areas using road-network, accessibility, operational, and data-quality metrics.

> **Status:** Phase 0 (design). No application code yet. See [PLAN.md](PLAN.md) for the full roadmap.

## Problem

A program manager or operations analyst must decide where a mobility service should expand next. The question this tool answers:

> Which candidate service area is the strongest expansion option, and what evidence, assumptions, risks, and data-quality limitations support that recommendation?

Initial candidates: Foster City, San Jose, Mountain View.

## What it is (and is not)

- Uses **public OpenStreetMap data** and, in a later phase, **clearly labeled synthetic** operational data.
- Uses a **deterministic, explainable weighted score**. No ML.
- Makes missing and low-confidence data visible instead of hiding it.
- It is **not** an autonomous-driving system and uses no proprietary fleet data.

## Design documents

| Doc | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Components, data flow, boundaries |
| [docs/data-model.md](docs/data-model.md) | Domain entities and PostGIS schema |
| [docs/scoring-model.md](docs/scoring-model.md) | Metrics, normalization, weights, confidence |
| [docs/api.md](docs/api.md) | Draft REST contract |
| [docs/adr/](docs/adr/) | Architecture decision records |

## Data disclaimer

Real-world data: OpenStreetMap contributors (ODbL). Any operational/simulation data added in Phase 8 is synthetic and will be labeled as such in the schema, API and UI.
