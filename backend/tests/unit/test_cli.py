from typer.testing import CliRunner

from cli.__main__ import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_seed_commands_registered() -> None:
    result = CliRunner().invoke(app, ["--help"])
    for name in ("seed-service-areas", "seed-metric-definitions", "seed-scoring-model"):
        assert name in result.stdout
