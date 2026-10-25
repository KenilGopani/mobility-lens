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
from app.db.session import make_engine
from cli import seed

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


if __name__ == "__main__":
    app()
