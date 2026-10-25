"""Unified error shape ``{"error": {"code", "message", "details"}}`` and its handlers."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.errors import InvalidRequestError, NotFoundError

log = structlog.get_logger()

_HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}


def error_response(
    status: int, code: str, message: str, details: Any | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return error_response(404, "not_found", exc.message, exc.details)


async def _invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
    return error_response(422, "validation_error", exc.message, exc.details)


async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return error_response(422, "validation_error", "Request validation failed", details)


async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = "Resource not found" if exc.status_code == 404 else str(exc.detail)
    return error_response(exc.status_code, code, message)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.error("api.unhandled_exception", error_type=type(exc).__name__, exc_info=exc)
    return error_response(500, "internal", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidRequestError, _invalid)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _request_validation)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled)
