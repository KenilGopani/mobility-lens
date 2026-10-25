from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session bound to the configured database."""
    engine = make_engine(get_settings().database_url)
    with sessionmaker(engine)() as session:
        yield session
