from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: a session on the app's engine (built from settings in create_app).

    Read endpoints never commit; the session is closed (and any transaction rolled back).
    """
    with sessionmaker(request.app.state.engine)() as session:
        yield session
