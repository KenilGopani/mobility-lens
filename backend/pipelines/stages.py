"""Structured per-stage logging: analysis_run_id, service_area_id, stage, duration_ms, counts."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog


def get_run_logger(analysis_run_id: object, service_area_id: object) -> Any:
    return structlog.get_logger("pipeline").bind(
        analysis_run_id=str(analysis_run_id), service_area_id=str(service_area_id)
    )


@contextmanager
def stage(log: Any, name: str) -> Iterator[dict[str, Any]]:
    """Time a stage; the yielded dict collects record counts that are logged on completion."""
    counts: dict[str, Any] = {}
    start = time.perf_counter()
    try:
        yield counts
    except Exception as exc:
        log.error(
            "stage_failed",
            stage=name,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    log.info(
        "stage_completed",
        stage=name,
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
        **counts,
    )
