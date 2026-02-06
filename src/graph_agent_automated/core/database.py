from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from graph_agent_automated.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative model base."""


def _create_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, echo=settings.sql_echo, future=True, connect_args=connect_args)


ENGINE = _create_engine()
SessionLocal = sessionmaker(bind=ENGINE, class_=Session, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
