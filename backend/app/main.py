from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.middleware import BodySizeLimitMiddleware, RequestTelemetryMiddleware
from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import make_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="MobilityLens API", version="0.1.0")
    app.state.engine = make_engine(settings.database_url)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RequestTelemetryMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)  # unversioned operational endpoint
    app.include_router(v1_router)
    return app


app = create_app()
