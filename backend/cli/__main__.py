"""MobilityLens CLI.

backend/ is the project root, so the package is importable as `cli` and is run
from backend/ as `uv run python -m cli` (PLAN.md says `python -m backend.cli`,
which would require running from the repo root and treating backend/ as a package).
"""

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import make_engine
from cli import openapi, seed

app = typer.Typer(help="MobilityLens data and analysis commands.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MobilityLens CLI."""


@app.command()
def version() -> None:
    """Print the CLI version (placeholder until real commands land)."""
    typer.echo("mobility-lens 0.1.0")


def _session() -> Session:
    return Session(make_engine(get_settings().database_url))


@app.command("seed-service-areas")
def seed_service_areas(
    boundary_dir: Annotated[
        Path, typer.Option(help="Directory holding <slug>.geojson boundary files.")
    ] = seed.BOUNDARY_DIR,
) -> None:
    """Upsert service areas from data/boundaries/<slug>.geojson (files are produced in Phase 3)."""
    with _session() as session, session.begin():
        report = seed.seed_service_areas(session, boundary_dir)
    for slug in report.created:
        typer.echo(f"created: {slug}")
    for slug in report.updated:
        typer.echo(f"updated: {slug}")
    for slug in report.missing:
        typer.echo(f"MISSING boundary file: {boundary_dir / (slug + '.geojson')}", err=True)
    if report.missing:
        typer.echo(
            f"{len(report.missing)} area(s) not seeded: boundary files are produced in Phase 3.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("seed-metric-definitions")
def seed_metric_definitions() -> None:
    """Upsert the 5 MVP metric definitions (version v1, provisional reference ranges)."""
    with _session() as session, session.begin():
        report = seed.seed_metric_definitions(session)
    typer.echo(f"metric definitions: {len(report.created)} created, {len(report.updated)} updated")


@app.command("seed-scoring-model")
def seed_scoring_model() -> None:
    """Upsert the baseline v1 scoring model and mark it the default."""
    with _session() as session, session.begin():
        report = seed.seed_scoring_model(session)
    typer.echo(f"scoring model baseline:v1: {'created' if report.created else 'updated'}")


@app.command("fetch-boundary")
def fetch_boundary_command(
    slug: Annotated[str, typer.Argument(help="Service-area slug, e.g. foster-city.")],
    query: Annotated[
        str,
        typer.Argument(help='Place name ("Foster City") for census; geocoding query for osm.'),
    ],
    source: Annotated[
        str, typer.Option(help="census (land-clipped, default) or osm (may include water).")
    ] = "census",
    state_fips: Annotated[str, typer.Option(help="Census state FIPS (06 = California).")] = "06",
    geoid: Annotated[
        str | None, typer.Option(help="Census GEOID to disambiguate same-named places.")
    ] = None,
    out_dir: Annotated[
        Path, typer.Option(help="Directory to write <slug>.geojson into.")
    ] = seed.BOUNDARY_DIR,
) -> None:
    """Fetch a boundary and write data/boundaries/<slug>.geojson (EPSG:4326)."""
    from pipelines.boundaries import write_boundary

    configure_logging(get_settings().log_level)
    path = write_boundary(
        slug,
        query,
        out_dir=out_dir,
        source=source,
        state_fips=state_fips,
        geoid=geoid,
    )
    typer.echo(f"wrote {path}")


@app.command("analyze-area")
def analyze_area_command(
    slug: Annotated[str, typer.Argument(help="Service-area slug (must be seeded).")],
    h3_resolution: Annotated[
        int | None, typer.Option(help="H3 resolution (default: H3_RESOLUTION setting).")
    ] = None,
) -> None:
    """Run the geospatial pipeline for one service area and persist a new analysis run."""
    from pipelines.analyze import AreaNotFoundError, analyze_area

    settings = get_settings()
    configure_logging(settings.log_level)
    with _session() as session:
        try:
            summary = analyze_area(session, slug, h3_resolution=h3_resolution)
        except AreaNotFoundError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except Exception as exc:
            typer.echo(f"analysis of {slug!r} failed (run recorded as failed): {exc}", err=True)
            raise typer.Exit(code=1) from exc
    typer.echo(
        f"run {summary.analysis_run_id}: {summary.cell_count} cells, {summary.area_km2:.2f} km2"
    )
    for key, value in summary.area_metrics.items():
        typer.echo(f"  {key}: {'unavailable' if value is None else f'{value:.4f}'}")
    score = "unavailable" if summary.score is None else f"{summary.score:.1f}"
    confidence = summary.score_confidence or 0.0
    typer.echo(f"  score: {score} (confidence {confidence:.2f}), findings: {summary.findings}")


@app.command("analyze-all")
def analyze_all_command(
    resume: Annotated[
        bool,
        typer.Option(help="Skip compatible successes when resuming an unchanged batch."),
    ] = False,
) -> None:
    """Analyze every seeded area; continue after individual failures and report all results."""
    from pipelines.batch import analyze_all

    configure_logging(get_settings().log_level)
    with _session() as session:
        try:
            result = analyze_all(session, resume=resume)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
    for summary in result.succeeded:
        typer.echo(
            f"succeeded: {summary.service_area_id} "
            f"run={summary.analysis_run_id} score={summary.score}"
        )
    for slug in result.skipped:
        typer.echo(f"skipped: {slug} (successful run already available)")
    for slug, error in result.failed.items():
        typer.echo(f"failed: {slug}: {error}", err=True)
    if result.failed:
        raise typer.Exit(code=1)


@app.command("export-openapi")
def export_openapi(
    output: Annotated[Path, typer.Option(help="Where to write the OpenAPI document.")] = (
        openapi.OPENAPI_PATH
    ),
) -> None:
    """Write the API's OpenAPI document (committed as docs/openapi.json; CI checks drift)."""
    output.write_text(openapi.render_openapi())
    typer.echo(f"wrote {output}")


if __name__ == "__main__":
    app()
