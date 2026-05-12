"""
CROSS-17: Set PostgreSQL RLS tenant context on connection checkout.

This module hooks into SQLAlchemy's connection pool to execute
SET LOCAL app.current_tenant_id = '<company_id>' on every connection
before it's used by application code.

The RLS policies in migration 022_enable_rls use app.current_tenant_id()
to restrict data access to the current tenant.

Integration:
    The module reads the tenant context from ``app.core.tenant_context``
    (ContextVar + threading.local) which is set by the TenantMiddleware
    for every authenticated request.

    When tenant bypass is active (admin / system queries), the hook
    is a no-op — the ``parwa_admin`` PostgreSQL role already has
    BYPASSRLS granted.

Usage:
    from app.core.db_rls import register_rls_hooks

    engine = create_engine(DATABASE_URL, ...)
    register_rls_hooks(engine)
"""

import logging
import threading
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("parwa.rls")

# ── Thread-local storage for current tenant ID ────────────────────
# Kept as a thin standalone cache so this module can work even if
# app.core.tenant_context is not importable (e.g. in standalone scripts).
_tenant_context = threading.local()


def set_tenant_context(company_id: str) -> None:
    """Set the current tenant ID for this thread.

    In the main application, prefer ``app.core.tenant_context.set_tenant_context``
    which updates both ContextVar and threading.local simultaneously.
    This function is provided for standalone / test usage.
    """
    _tenant_context.company_id = company_id


def get_tenant_context() -> Optional[str]:
    """Get the current tenant ID for this thread.

    First tries ``app.core.tenant_context`` (async ContextVar-aware),
    then falls back to the local threading.local cache.
    """
    # Try the full tenant_context module first (handles both async + sync)
    try:
        from app.core.tenant_context import get_tenant_context as _gtx

        value = _gtx()
        if value is not None:
            return value
    except ImportError:
        pass
    # Fall back to local threading.local
    return getattr(_tenant_context, "company_id", None)


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    try:
        from app.core.tenant_context import clear_tenant_context as _ctx

        _ctx()
    except ImportError:
        pass
    try:
        delattr(_tenant_context, "company_id")
    except AttributeError:
        pass


def is_tenant_bypassed() -> bool:
    """Check if tenant bypass is currently active."""
    try:
        from app.core.tenant_context import is_tenant_bypassed as _ib

        return _ib()
    except ImportError:
        return False


@contextmanager
def tenant_scope(company_id: str) -> Generator[None, None, None]:
    """Context manager for tenant-scoped database operations.

    Sets the tenant context so that the SQLAlchemy RLS hook injects
    ``SET LOCAL app.current_tenant_id`` on every statement.

    Example::

        with tenant_scope("comp-abc-123"):
            users = db.execute(select(User)).scalars().all()
            # Only users from comp-abc-123 are returned
    """
    set_tenant_context(company_id)
    try:
        yield
    finally:
        clear_tenant_context()


# ═══════════════════════════════════════════════════════════════════
# SQLAlchemy event hook
# ═══════════════════════════════════════════════════════════════════

def register_rls_hooks(engine: Engine) -> None:
    """Register SQLAlchemy event hooks for RLS tenant context.

    Call **once** when creating the database engine::

        engine = create_engine(DATABASE_URL)
        register_rls_hooks(engine)

    After registration, every SQL statement executed through *engine*
    will be prefixed with::

        SET LOCAL app.current_tenant_id = '<company_id>';

    ``SET LOCAL`` is transaction-scoped, so the value is automatically
    cleared when the transaction commits/rolls back.

    When tenant bypass is active, the hook is a no-op (the DB user
    ``parwa_admin`` has BYPASSRLS).
    """

    @event.listens_for(engine, "before_cursor_execute")
    def _set_tenant_on_cursor(
        conn,
        cursor,
        statement: str,
        parameters,
        context,
        executemany: bool,
    ) -> None:
        # Skip if tenant bypass is active (admin queries)
        if is_tenant_bypassed():
            return

        company_id = get_tenant_context()
        if company_id:
            # Use parameterised SET to avoid SQL-injection surface
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (company_id,),
            )

    logger.info(
        "rls_hooks_registered",
        extra={"table_count": 122},
    )
