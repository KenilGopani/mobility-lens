# ADR-007: MapLibre GL JS instead of Mapbox GL JS

**Status:** Accepted (amends the stack in PLAN.md section 5)

## Context
PLAN.md specifies Mapbox GL JS. Mapbox GL JS v2+ requires an access token and is not open source. No token is available for this project.

## Decision
Use MapLibre GL JS, the open-source fork with a near-identical API. The basemap style URL is configuration (`MAP_STYLE_URL`), defaulting to a free style that needs no key. Boundary and H3 layers are plain GeoJSON sources and do not depend on the basemap. The `MAPBOX_ACCESS_TOKEN` entry in `.env.example` is dropped.

## Consequences
- No secrets are needed to run the project.
- Switching to Mapbox later is a small change, since the layer code is the same.
- Free public tile servers have usage limits. They are acceptable for local development and a portfolio demo, but would not be for production.
