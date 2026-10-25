"""Comparison and what-if scoring. Preview never writes: the session is only ever read."""

import uuid
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.models import ServiceArea
from app.repositories import service_areas
from app.schemas.api import (
    AreaScoreResult,
    ComparisonResponse,
    PreviewResponse,
    ScoringModelRef,
)
from app.scoring.engine import InvalidWeightsError, validate_weights
from app.services import evaluation as ev
from app.services.errors import InvalidRequestError, NotFoundError


def _load_areas(session: Session, ids: list[uuid.UUID]) -> list[ServiceArea]:
    found = service_areas.get_many_light(session, ids)
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise NotFoundError("Service area not found", {"service_area_ids": missing})
    return [found[i] for i in ids]  # request order


def _score_set(
    session: Session,
    ids: list[uuid.UUID],
    weights: Mapping[str, float],
    required: set[str] | None,
) -> list[AreaScoreResult]:
    areas = _load_areas(session, ids)
    defs = ev.definitions(session)
    evals = ev.evaluate_areas(session, areas, weights, required)
    outliers = ev.peer_outliers(evals, weights.keys())
    out: list[AreaScoreResult] = []
    for e in evals:
        base = {"service_area_id": e.area.id, "name": e.area.name, "slug": e.area.slug}
        if e.result is None:
            out.append(AreaScoreResult(**base, warnings=[ev.NO_SUCCESSFUL_RUN]))
            continue
        components = ev.components_out(e.result, defs)
        strengths, risks = ev.highlights(components, defs)
        found = outliers.get(str(e.area.id), [])
        out.append(
            AreaScoreResult(
                **base,
                score=e.result.score,
                confidence=e.result.confidence,
                rank=e.rank,
                components=components,
                strengths=strengths,
                risks=risks,
                warnings=[*e.result.warnings, *(f"peer_outlier:{o.metric}" for o in found)],
                peer_outliers=found,
                run=ev.run_ref(e.run),
            )
        )
    return out


def compare(
    session: Session, ids: list[uuid.UUID], scoring_model_id: uuid.UUID | None
) -> ComparisonResponse:
    if scoring_model_id is not None:
        model = ev.get_model_or_404(session, scoring_model_id)
    else:
        default = ev.default_model(session)
        if default is None:
            raise NotFoundError("No default scoring model configured")
        model = default
    weights = {k: float(v) for k, v in model.weights.items()}
    return ComparisonResponse(
        scoring_model=ev.model_ref(model), areas=_score_set(session, ids, weights, None)
    )


def preview(session: Session, ids: list[uuid.UUID], weights: dict[str, float]) -> PreviewResponse:
    required = set(ev.definitions(session))
    try:
        validate_weights(weights, required)
    except InvalidWeightsError as exc:
        keys = set(weights)
        raise InvalidRequestError(
            "Invalid scoring weights",
            [
                {
                    "loc": ["body", "weights"],
                    "msg": str(exc),
                    "type": "invalid_weights",
                    "missing": sorted(required - keys),
                    "unexpected": sorted(keys - required),
                }
            ],
        ) from exc
    return PreviewResponse(
        scoring_model=ScoringModelRef(name="custom (preview)", weights=weights),
        areas=_score_set(session, ids, weights, required),
    )
