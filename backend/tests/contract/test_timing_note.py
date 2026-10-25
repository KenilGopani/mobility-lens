"""Non-asserting timing note (PLAN section 30 budgets). Prints only; run with -s."""

import time

import pytest
from fastapi.testclient import TestClient

from tests.contract.conftest import World

pytestmark = pytest.mark.integration


def test_timing_note(client: TestClient, world: World) -> None:
    ids = [str(world.ids[n]) for n in ("Alpha", "Beta", "Gamma")]
    calls = {
        "summary(<300ms)": lambda: client.get(
            f"/api/v1/service-areas/{world.ids['Alpha']}/summary"
        ),
        "comparison(<500ms)": lambda: client.post(
            "/api/v1/comparisons", json={"service_area_ids": ids}
        ),
        "cells viewport(<500ms)": lambda: client.get(
            f"/api/v1/service-areas/{world.ids['Alpha']}/cells"
        ),
    }
    for name, call in calls.items():
        start = time.perf_counter()
        assert call().status_code == 200
        print(f"timing {name}: {(time.perf_counter() - start) * 1000:.0f} ms")
