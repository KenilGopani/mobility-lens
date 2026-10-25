"""Domain errors raised by services; app.api.errors maps them to the unified error shape."""

from typing import Any


class ServiceError(Exception):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ServiceError):
    """Unknown resource (HTTP 404)."""


class InvalidRequestError(ServiceError):
    """Semantically invalid request (HTTP 422)."""
