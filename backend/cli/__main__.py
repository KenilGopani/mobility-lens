"""MobilityLens CLI.

backend/ is the project root, so the package is importable as `cli` and is run
from backend/ as `uv run python -m cli` (PLAN.md says `python -m backend.cli`,
which would require running from the repo root and treating backend/ as a package).
"""

import typer

app = typer.Typer(help="MobilityLens data and analysis commands.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MobilityLens CLI."""


@app.command()
def version() -> None:
    """Print the CLI version (placeholder until real commands land)."""
    typer.echo("mobility-lens 0.1.0")


if __name__ == "__main__":
    app()
