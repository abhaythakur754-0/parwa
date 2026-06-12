"""
PARWA Phase 3 — Database Base Configuration

SQLAlchemy base, engine factory, session management, and UUID helper.
All timestamps are UTC. Every table enforces multi-tenant isolation via company_id.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# UUID helper
# ---------------------------------------------------------------------------

def _uuid() -> str:
    """Generate a new UUID4 string for use as a default primary key."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Single declarative base for all PARWA models."""
    pass


# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

_default_db_url = os.getenv("PARWA_DATABASE_URL", "sqlite:///./parwa_phase3.db")


def create_engine_from_url(database_url: str | None = None, **engine_kwargs):
    """
    Create a SQLAlchemy engine.

    Parameters
    ----------
    database_url:
        Connection string. Falls back to the ``PARWA_DATABASE_URL`` env var,
        then to a local SQLite file.
    engine_kwargs:
        Extra keyword arguments forwarded to ``create_engine``.
    """
    url = database_url or _default_db_url

    # SQLite-specific tuning
    connect_args = engine_kwargs.pop("connect_args", {})
    if url.startswith("sqlite"):
        connect_args.setdefault("check_same_thread", False)

    return create_engine(url, connect_args=connect_args, **engine_kwargs)


def create_session_factory(engine=None, **session_kwargs) -> sessionmaker:
    """
    Return a ``sessionmaker`` bound to *engine*.

    The session class is ``Session`` and ``expire_on_commit`` defaults to False
    so detached objects remain usable after commit.
    """
    if engine is None:
        engine = create_engine_from_url()
    session_kwargs.setdefault("expire_on_commit", False)
    return sessionmaker(bind=engine, class_=Session, **session_kwargs)


# Module-level convenience instances (created lazily on first import)
engine = create_engine_from_url()
SessionLocal = create_session_factory(engine)


# ---------------------------------------------------------------------------
# FastAPI-style dependency generator
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session and guarantee cleanup.

    Usage with FastAPI::

        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
