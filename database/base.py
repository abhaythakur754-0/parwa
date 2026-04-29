"""
PARWA Database Base Configuration

Provides SQLAlchemy engine, session factory, and declarative base.
Supports both PostgreSQL (production) and SQLite (CI tests).

Day 20: Added tenant-aware session with automatic company_id injection:
- TenantSession wraps SessionLocal with before_flush event listener
- @bypass_tenant decorator/context-manager skips auto-injection for admin ops
- get_tenant_db() FastAPI dependency creates a session with tenant context
- Auto-injection reads company_id from tenant_context and sets it on
  any new object being flushed that has a company_id attribute
"""

import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Generator

from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session
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
    # Use JSON for SQLite compatibility (JSONB is PostgreSQL-only)
    JSONType = JSON
else:
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })
    # Use JSONB for PostgreSQL (better performance)
    from sqlalchemy.dialects.postgresql import JSONB as JSONType  # type: ignore[misc]

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()  # type: ignore[misc]

logger = logging.getLogger("parwa.database")

# Thread-local flag for per-session bypass control
# Actual bypass mechanism lives in backend.app.core.tenant_context
_session_bypass_flag: Any = None  # placeholder


def get_db():
    """FastAPI dependency that yields a database session.

    Automatically commits on success and rolls back on exception,
    ensuring data written during the request is persisted.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager that yields a database session.

    Unlike get_db() (which is a FastAPI dependency generator), this is a
    plain context manager for use in Celery tasks, scripts, or any
    non-request context.

    Usage:
        with get_db_context() as db:
            db.query(Model).all()
            db.commit()

    Automatically commits on success and rolls back on exception.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_tenant_db():
    """FastAPI dependency that yields a tenant-aware database session.

    Unlike get_db(), this creates a session that has the before_flush
    event listener for automatic company_id injection.

    The session will auto-inject company_id from tenant_context
    on any new object that has a company_id attribute.
    """
    from backend.app.core.tenant_context import get_tenant_context

    db = TenantSession()
    company_id = get_tenant_context()
    if company_id:
        db.info["tenant_company_id"] = company_id
    try:
        yield db
    finally:
        db.close()


# ── Tenant Auto-Injection Event ──────────────────────────────────

def _auto_inject_company_id(session: Session, context: Any, instances: Any) -> None:
    """SQLAlchemy before_flush event: auto-inject company_id on new objects.

    This event fires before any session.flush(). It checks all new objects
    (not yet persisted) and sets company_id from the tenant context if:
    1. The object has a company_id attribute (column)
    2. The company_id is not already set
    3. Tenant bypass is not active

    If no tenant context is available, a warning is logged (potential
    data leak if bypass is not explicitly enabled).
    """
    from backend.app.core.tenant_context import (
        get_tenant_context,
        is_tenant_bypassed,
    )

    # Skip injection if bypass is enabled for this thread
    if is_tenant_bypassed():
        return

    company_id = get_tenant_context()

    for instance in session.new:
        # Check if the object has a company_id column
        if not hasattr(instance, "company_id"):
            continue

        # If company_id is already set, skip (explicit override)
        if getattr(instance, "company_id", None) is not None:
            continue

        # Auto-inject from tenant context
        if company_id is not None:
            instance.company_id = company_id
            logger.debug(
                "auto_injected_company_id",
                extra={
                    "model": instance.__class__.__name__,
                    "company_id": company_id,
                },
            )
        else:
            # No tenant context available — log warning
            logger.warning(
                "auto_inject_no_tenant_context",
                extra={
                    "model": instance.__class__.__name__,
                    "warning": (
                        "New object with company_id column flushed without "
                        "tenant context. This may be a data leak. Use "
                        "@bypass_tenant or tenant_bypass() if intentional."
                    ),
                },
            )


# ── TenantSession Class ──────────────────────────────────────────

class TenantSession(Session):
    """SQLAlchemy Session with automatic company_id injection.

    Inherits from Session and registers the before_flush event listener
    for tenant-aware auto-injection.

    Usage as context manager:
        with TenantSession() as session:
            obj = MyModel(name="test")
            session.add(obj)
            session.flush()  # company_id auto-injected from context
            session.commit()

    Usage as dependency:
        @app.get("/items")
        async def get_items(db: Session = Depends(get_tenant_db)):
            ...
    """

    def __init__(self, **kwargs: Any):
        # Use the existing bind from SessionLocal
        if "bind" not in kwargs:
            kwargs["bind"] = engine
        if "autocommit" not in kwargs:
            kwargs["autocommit"] = False
        if "autoflush" not in kwargs:
            kwargs["autoflush"] = False

        super().__init__(**kwargs)

        # Register the auto-injection event
        event.listen(self, "before_flush", _auto_inject_company_id)

    # Allow context manager usage
    def __enter__(self) -> "TenantSession":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None:
            try:
                self.commit()
            except Exception:
                self.rollback()
                raise
        else:
            self.rollback()
        self.close()


# ── bypass_tenant Decorator ──────────────────────────────────────

def bypass_tenant(func: Callable = None, *, reason: str = "") -> Any:
    """Decorator or context manager that skips tenant auto-injection.

    This must be EXPLICITLY opted-in for admin/system queries.
    Every bypass is audit-logged.

    Usage as decorator:
        @bypass_tenant(reason="admin aggregate query")
        def get_all_companies_stats():
            ...

    Usage as context manager:
        with bypass_tenant(reason="system migration"):
            db.query(Model).all()

    Args:
        func: The function to wrap (when used as decorator).
        reason: Audit reason for bypassing tenant isolation.

    Returns:
        Wrapped function or context manager.
    """
    from backend.app.core.tenant_context import tenant_bypass

    if func is not None:
        # Used as @bypass_tenant (without parentheses)
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            with tenant_bypass(reason=reason):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any):
            with tenant_bypass(reason=reason):
                return await func(*args, **kwargs)

        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    else:
        # Used as @bypass_tenant(reason="...") or bypass_tenant(reason="...")
        # Return a context manager
        return tenant_bypass(reason=reason)


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
