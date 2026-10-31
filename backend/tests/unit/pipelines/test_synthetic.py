from datetime import UTC, datetime

import pytest

from pipelines.synthetic import generate_events

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_seed_repeats_events_and_changed_seed_changes_content():
    a, issues = generate_events(42, 200, START)
    assert (a, issues) == generate_events(42, 200, START)
    assert a != generate_events(43, 200, START)[0]
    assert len(a) == 200
    assert all(
        r.distance_km >= 0 and r.duration_minutes > 0 and r.ended_at >= r.started_at for r in a
    )
    assert all((i.status == "resolved") == (i.resolved_at is not None) for i in issues)
    assert any(not r.completed for r in a)


@pytest.mark.parametrize("seed,routes", [(-1, 10), (42, 0), (42, 100001)])
def test_invalid_generation_rejected(seed, routes):
    with pytest.raises(ValueError):
        generate_events(seed, routes, START)
