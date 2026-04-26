"""Database engine and session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from investment_tracker.settings import AppSettings, get_settings


def create_engine_from_settings(settings: AppSettings) -> Engine:
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        echo=settings.database_echo,
        future=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_session_factory(settings: AppSettings | None = None) -> sessionmaker:
    resolved_settings = settings or get_settings()
    engine = create_engine_from_settings(resolved_settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_db_session() -> Session:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()

