"""
PARWA Phase 1 — Multi-Tenant Isolation

Ensures every data access is scoped to a tenant_id.
Provides:
  - TenantContext manager for request-scoped isolation
  - DataQuery helper that auto-filters by tenant_id
  - Validation utilities for cross-tenant safety checks

Production: PostgreSQL RLS via set_tenant_context() SQL function
Phase 1: Python-level enforcement (same logic, no DB required for testing)
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from app.core.auth.access_control import (
    set_tenant_context,
    get_tenant_context,
    clear_tenant_context,
)

logger = logging.getLogger("parwa.tenant")

# ── Tenant Store (in-memory for Phase 1) ──────────────────────

# Production: tenants table with RLS
# Phase 1: in-memory store
_tenants: Dict[str, Dict[str, Any]] = {}


def create_tenant(
    name: str,
    slug: str,
    tier: str = "mini",
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new tenant. Returns tenant record."""
    tenant_id = str(uuid.uuid4())

    if slug in [t["slug"] for t in _tenants.values()]:
        raise ValueError(f"Tenant slug '{slug}' already exists")

    if tier not in ("mini", "parwa", "high"):
        raise ValueError(f"Invalid tier: {tier}. Must be mini, parwa, or high")

    _tenants[tenant_id] = {
        "id": tenant_id,
        "name": name,
        "slug": slug,
        "tier": tier,
        "status": "active",
        "settings": settings or {},
    }

    logger.info("Tenant created: id=%s slug=%s tier=%s", tenant_id, slug, tier)
    return _tenants[tenant_id]


def get_tenant(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Get a tenant by ID. Returns None if not found."""
    return _tenants.get(tenant_id)


def get_tenant_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Get a tenant by slug."""
    for t in _tenants.values():
        if t["slug"] == slug:
            return t
    return None


def list_tenants() -> List[Dict[str, Any]]:
    """List all tenants (admin/superuser only in production)."""
    return list(_tenants.values())


def update_tenant(tenant_id: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Update tenant fields."""
    tenant = _tenants.get(tenant_id)
    if not tenant:
        return None

    for key in ("name", "slug", "tier", "status", "settings"):
        if key in kwargs:
            if key == "tier" and kwargs[key] not in ("mini", "parwa", "high"):
                raise ValueError(f"Invalid tier: {kwargs[key]}")
            tenant[key] = kwargs[key]

    logger.info("Tenant updated: id=%s", tenant_id)
    return tenant


def suspend_tenant(tenant_id: str) -> bool:
    """Suspend a tenant (no API access)."""
    tenant = _tenants.get(tenant_id)
    if not tenant:
        return False
    tenant["status"] = "suspended"
    logger.warning("Tenant suspended: id=%s", tenant_id)
    return True


# ── Tenant-Scoped Request Context ─────────────────────────────


@contextmanager
def tenant_request(
    tenant_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    auth_method: str = "api_key",
) -> Generator[Dict[str, Any], None, None]:
    """Context manager that sets tenant isolation for a request.

    Usage:
        with tenant_request(tenant_id="abc", user_id="xyz") as ctx:
            # All data operations auto-filter by this tenant
            # ctx contains tenant_id, user_id, etc.
            pass
    """
    # Verify tenant exists and is active
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise PermissionError(f"Tenant not found: {tenant_id}")
    if tenant["status"] != "active":
        raise PermissionError(f"Tenant suspended: {tenant_id}")

    context = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "auth_method": auth_method,
        "tenant_tier": tenant["tier"],
        "tenant_name": tenant["name"],
    }

    set_tenant_context(context)
    logger.debug("Tenant context set: %s (tier=%s)", tenant_id, tenant["tier"])

    try:
        yield context
    finally:
        clear_tenant_context()
        logger.debug("Tenant context cleared: %s", tenant_id)


# ── Data Isolation Helpers ────────────────────────────────────


def validate_tenant_access(data_tenant_id: str) -> bool:
    """Check if data belongs to the current tenant context.

    Use before returning any data to verify tenant isolation.
    """
    ctx = get_tenant_context()
    if not ctx:
        raise PermissionError("No tenant context set")
    return ctx["tenant_id"] == data_tenant_id


def filter_by_tenant(records: List[Dict[str, Any]], tenant_id_key: str = "tenant_id") -> List[Dict[str, Any]]:
    """Filter a list of records to only include those belonging to the current tenant.

    Safety net: even if a query returns cross-tenant data, this removes it.
    """
    ctx = get_tenant_context()
    if not ctx:
        raise PermissionError("No tenant context set")
    current_tenant = ctx["tenant_id"]

    filtered = [r for r in records if r.get(tenant_id_key) == current_tenant]

    # Log if any records were filtered out (potential security issue)
    if len(filtered) != len(records):
        logger.warning(
            "Tenant isolation filtered %d/%d records for tenant %s",
            len(records) - len(filtered), len(records), current_tenant,
        )

    return filtered


def audit_log(
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an audit log entry for tenant-scoped operations.

    Production: writes to key_usage_audit table
    Phase 1: returns dict for logging
    """
    ctx = get_tenant_context()
    entry = {
        "tenant_id": ctx["tenant_id"] if ctx else "unknown",
        "user_id": ctx.get("user_id") if ctx else None,
        "session_id": ctx.get("session_id") if ctx else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
    }
    logger.info("AUDIT: %s %s/%s by tenant=%s", action, resource_type, resource_id, entry["tenant_id"])
    return entry


# ── Tier Permission Checks ────────────────────────────────────

# Maps to tier_permissions.py in production
TIER_CAPABILITIES = {
    "mini": {
        "max_llm_calls_per_ticket": 10,
        "allowed_nodes": [1, 2, 3, 7],  # simple path only
        "can_use_complex_path": False,
        "can_use_super_node": False,
        "wiki_access": "read",  # read only
        "max_kb_documents": 50,
    },
    "parwa": {
        "max_llm_calls_per_ticket": 30,
        "allowed_nodes": [1, 2, 3, 4, 5, 6, 7],
        "can_use_complex_path": True,
        "can_use_super_node": False,
        "wiki_access": "read+learn",
        "max_kb_documents": 500,
    },
    "high": {
        "max_llm_calls_per_ticket": 60,
        "allowed_nodes": [1, 2, 3, 4, 5, 6, 7, 8],
        "can_use_complex_path": True,
        "can_use_super_node": True,
        "wiki_access": "read+write+learn",
        "max_kb_documents": 5000,
    },
}


def get_tier_permissions(tier: str) -> Dict[str, Any]:
    """Get the capability set for a tier."""
    return TIER_CAPABILITIES.get(tier, TIER_CAPABILITIES["mini"])


def check_tier_capability(tier: str, capability: str) -> bool:
    """Check if a tier has a specific capability."""
    perms = get_tier_permissions(tier)
    return perms.get(capability, False)


def get_current_tenant_tier() -> str:
    """Get the tier of the current request's tenant."""
    ctx = get_tenant_context()
    if not ctx:
        raise PermissionError("No tenant context set")
    return ctx.get("tenant_tier", "mini")