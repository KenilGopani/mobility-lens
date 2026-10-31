from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pipelines import batch


def test_batch_continues_after_failure_and_resumes_success(monkeypatch):
    session = Mock()
    areas = [SimpleNamespace(id=i, slug=str(i)) for i in range(3)]
    monkeypatch.setattr(batch.service_areas, "list_light", lambda s: areas)
    monkeypatch.setattr(
        batch.analysis_runs,
        "latest_succeeded_for_area",
        lambda s, id: (
            SimpleNamespace(
                pipeline_version=batch.PIPELINE_VERSION, parameters={"h3_resolution": 9}
            )
            if id == 0
            else None
        ),
    )

    def analyze(s, slug):
        if slug == "1":
            raise RuntimeError("source unavailable")
        return SimpleNamespace(analysis_run_id="ok")

    monkeypatch.setattr(batch, "analyze_area", analyze)
    result = batch.analyze_all(session, resume=True)
    assert result.skipped == ["0"]
    assert result.failed == {"1": "RuntimeError: source unavailable"}
    assert len(result.succeeded) == 1
    session.rollback.assert_called_once()


def test_empty_batch_is_explicit(monkeypatch):
    monkeypatch.setattr(batch.service_areas, "list_light", lambda s: [])
    with pytest.raises(ValueError, match="No service areas"):
        batch.analyze_all(Mock())
