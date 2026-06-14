"""
PARWA Tenant Context (BC-001)

Provides tenant context propagation across:
- Async contexts (FastAPI request → DB session → Redis → Celery dispatch)
- Sync contexts (Celery worker → DB session → Redis)

Uses threading.local() for sync (Celery workers) and contextvars for async (FastAPI).

Usage:
    from app.core.tenant_context import (
        set_tenant_context, get_tenant_context, clear_tenant_context,
    )

    # In middleware:
    set_tenant_context("acme")
    try:
        # All downstream code can call get_tenant_context()
        await some_service.do_work()
    finally:
        clear_tenant_context()
"""

import threading
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Generator, Optional

from app.logger import get_logger

logger = get_logger("tenant_context")

# Async context var (for FastAPI/asyncio)
_tenant_ctx_var: ContextVar[Optional[str]] = ContextVar(
    "tenant_company_id", default=None
)

# Thread-local (for Celery sync workers)
_tenant_local = threading.local()

# Header name used to propagate company_id to Celery tasks
TENANT_HEADER_KEY = "X-Parwa-Company-ID"


def set_tenant_context(company_id: str) -> None:
    """Set the tenant context for the current async task or thread.

    Sets both the context var (async) and thread-local (sync) so that
    all downstream code regardless of execution model can access it.

    Args:
        company_id: The tenant identifier.

    Raises:
        ValueError: If company_id is empty or not a string.
    """
    if not company_id or not isinstance(company_id, str):
        raise ValueError(
            "company_id must be a non-empty string (BC-001)"
        )
    company_id = company_id.strip()
    if not company_id:
        raise ValueError(
            "company_id must not be whitespace-only (BC-001)"
        )
    _tenant_ctx_var.set(company_id)
    _tenant_local.company_id = company_id


def get_tenant_context() -> Optional[str]:
    """Get the current tenant context.

    Returns:
        The company_id string, or None if not set.
    """
    # Try async context var first
    value = _tenant_ctx_var.get()
    if value is not None:
        return value
    # Fall back to thread-local
    return getattr(_tenant_local, "company_id", None)


def clear_tenant_context() -> None:
    """Clear the tenant context for the current async task or thread."""
    _tenant_ctx_var.set(None)
    _bypass_ctx_var.set(False)
    _bypass_reason_ctx_var.set(None)
    try:
        delattr(_tenant_local, "company_id")
    except AttributeError:
        pass


@contextmanager
def tenant_context(company_id: str) -> Generator[None, None, None]:
    """Context manager that sets and clears tenant context.

    Args:
        company_id: The tenant identifier.

    Yields:
        None

    Example:
        with tenant_context("acme"):
            # All code here has "acme" as tenant context
            do_tenant_work()
    """
    set_tenant_context(company_id)
    try:
        yield
    finally:
        clear_tenant_context()


@contextmanager
def requires_tenant_context() -> Generator[str, None, None]:
    """Context manager that raises if no tenant context is set.

    Yields:
        The company_id string.

    Raises:
        RuntimeError: If no tenant context is set.

    Example:
        with requires_tenant_context() as company_id:
            # Guaranteed to have company_id here
            query_tenant_data(company_id)
    """
    company_id = get_tenant_context()
    if not company_id:
        raise RuntimeError(
            "Tenant context is required but not set (BC-001). "
            "Ensure the request has passed through TenantMiddleware."
        )
    yield company_id


def get_task_headers(company_id: str) -> dict:
    """Build Celery task headers with tenant context.

    Called when dispatching a task from an API request to propagate
    the tenant context to the Celery worker.

    Args:
        company_id: The tenant identifier.

    Returns:
        Dict with tenant header for Celery task delivery_info.
    """
    return {TENANT_HEADER_KEY: company_id}


def extract_company_id_from_headers(headers: dict) -> Optional[str]:
    """Extract company_id from Celery task headers.

    Called at the start of task execution to restore tenant context.

    Args:
        headers: Celery task headers dict.

    Returns:
        Company ID string or None if not found.
    """
    return headers.get(TENANT_HEADER_KEY)


def reset_tenant_context() -> None:
    """Reset tenant context (for testing only)."""
    _tenant_ctx_var.set(None)
    _bypass_ctx_var.set(False)
    _bypass_reason_ctx_var.set(None)
    try:
        delattr(_tenant_local, "company_id")
    except AttributeError:
        pass


# ── Tenant Bypass (for admin/system queries) ───────────────


_bypass_ctx_var: ContextVar[bool] = ContextVar("tenant_bypass", default=False)
_bypass_reason_ctx_var: ContextVar[Optional[str]] = ContextVar(
    "tenant_bypass_reason", default=None
)


def set_tenant_bypass(enabled: bool = True, reason: str = "") -> None:
    """Enable or disable tenant bypass mode.

    When bypass is enabled, DB auto-injection and Redis key validation
    are skipped (for admin/system queries).

    Args:
        enabled: True to enable bypass, False to disable.
        reason: Reason for bypass (audit log). Empty string logs warning.
    """
    _bypass_ctx_var.set(enabled)
    if enabled:
        _bypass_reason_ctx_var.set(reason)
        if not reason:
            logger.warning(
                "tenant_bypass_enabled_without_reason",
            )
        else:
            logger.info(
                "tenant_bypass_enabled",
                reason=reason,
            )
    else:
        _bypass_reason_ctx_var.set(None)


def is_tenant_bypassed() -> bool:
    """Check if tenant bypass is currently enabled.

    Returns:
        True if bypass is active, False otherwise.
    """
    return _bypass_ctx_var.get()


def get_bypass_reason() -> Optional[str]:
    """Get the reason for the current bypass.

    Returns:
        Reason string or None if not bypassed.
    """
    if not _bypass_ctx_var.get():
        return None
    return _bypass_reason_ctx_var.get()


@contextmanager
def tenant_bypass(reason: str) -> Generator[None, None, None]:
    """Context manager for tenant bypass.

    Args:
        reason: Reason for bypass (audit log).

    Example:
        with tenant_bypass(reason="admin dashboard query"):
            # DB/Redis tenant checks are skipped
            results = db.query(AllCompanies).all()
    """
    previous = _bypass_ctx_var.get()
    previous_reason = _bypass_reason_ctx_var.get()
    set_tenant_bypass(enabled=True, reason=reason)
    try:
        yield
    finally:
        _bypass_ctx_var.set(previous)
        _bypass_reason_ctx_var.set(previous_reason)
