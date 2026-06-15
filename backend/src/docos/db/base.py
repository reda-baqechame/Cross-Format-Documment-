"""SQLAlchemy engine, session factory, and declarative base.

The engine is created lazily so that importing the package does not require a
database driver or a reachable database — important for tests that swap in SQLite
via dependency overrides.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from docos.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for workers/scripts outside the request lifecycle."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
