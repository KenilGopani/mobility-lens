from typing import Literal

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()
log = structlog.get_logger()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database: Literal["ok", "unavailable"] = "ok"
    except SQLAlchemyError:
        log.warning("health.database_unavailable")
        database = "unavailable"
    return HealthResponse(status="ok", database=database)


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"description": "Database unavailable"}},
)
def readiness(request: Request) -> HealthResponse | JSONResponse:
    result = health(request)
    if result.database != "ok":
        return JSONResponse(status_code=503, content=result.model_dump())
    return result
