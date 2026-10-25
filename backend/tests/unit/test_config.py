import pytest

from app.core.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "LOG_LEVEL", "H3_RESOLUTION", "CORS_ORIGINS"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.h3_resolution == 9
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "http://localhost:5173" in settings.cors_origins


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@h:5432/d")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("H3_RESOLUTION", "8")
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.test","http://b.test"]')
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql+psycopg://a:b@h:5432/d"
    assert settings.log_level == "DEBUG"
    assert settings.h3_resolution == 8
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_h3_resolution_bounds() -> None:
    with pytest.raises(ValueError):
        Settings(h3_resolution=16)
