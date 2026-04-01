"""
PARWA Database Base Configuration

Provides SQLAlchemy engine, session factory, and declarative base.
Supports both PostgreSQL (production) and SQLite (CI tests).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _get_db_url() -> str:
    env = os.environ.get("ENVIRONMENT", "")
    if env == "test":
        return os.environ.get(
            "DATABASE_URL", "sqlite:///:memory:"
        )
    try:
        from backend.app.config import get_settings  # noqa: E402
        settings = get_settings()
        return settings.DATABASE_URL
    except Exception:
        # Must not crash at module import time (BC-011)
        return os.environ.get("DATABASE_URL", "sqlite:///:memory:")


_db_url = _get_db_url()

# SQLite in-memory: use StaticPool so all connections share
# the same database (required for tests)
_engine_kwargs = {"echo": False}
if _db_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in _db_url:
        _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()  # type: ignore[misc]


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (used in tests and initial setup)."""
    Base.metadata.create_all(bind=engine)


async def check_db_health() -> dict:
    """Check database connectivity and return health status.

    Used by the /health and /ready endpoints (BC-012) to detect
    database failures.

    Returns:
        Dict with 'status' ('healthy' or 'unhealthy'), 'latency_ms',
        and optional 'error'.
    """
    import time

    start = time.monotonic()
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        latency = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return {
            "status": "unhealthy",
            "latency_ms": latency,
            "error": str(exc),
        }
