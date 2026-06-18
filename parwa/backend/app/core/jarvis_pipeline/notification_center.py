"""
Notification Center — DB-Backed (Wave 1 Migration)

Replaces in-memory store with jarvis_db backend.
Same public API, now async, now persistent.

All storage delegated to jarvis_db (InMemory or Supabase).

Rules (unchanged):
  1. UNSOLVED/STUCK ONLY — never notify on resolved tickets
  2. UNIQUE KEY per notification: PARWA-NFY-XXX
  3. BATCH SIMILAR — group within 5-min window
  4. NOISE FILTER — LOW priority logged but not pushed
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .jarvis_db import (
    get_db,
    PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
    PRIORITY_THRESHOLDS,
    TYPE_STUCK_TICKET, TYPE_QUOTA_LOW, TYPE_INTEGRATION_DOWN,
    TYPE_POLICY_CHANGE, TYPE_ACCURACY_DROP, TYPE_SLA_RISK,
)

logger = logging.getLogger("jarvis.notifications")

# Re-export constants for backward compatibility
__all__ = [
    "create_notification", "get_notification", "get_tenant_notifications",
    "resolve_notification", "dismiss_notification",
    "add_to_batch", "flush_batches", "get_stats", "clear_all",
    "PRIORITY_CRITICAL", "PRIORITY_HIGH", "PRIORITY_MEDIUM", "PRIORITY_LOW",
    "PRIORITY_THRESHOLDS", "TYPE_STUCK_TICKET", "TYPE_QUOTA_LOW",
    "TYPE_INTEGRATION_DOWN", "TYPE_POLICY_CHANGE", "TYPE_ACCURACY_DROP",
    "TYPE_SLA_RISK",
]

BATCH_WINDOW_S = 300


# ── Core Functions (now async, backed by jarvis_db) ──────────


async def create_notification(
    tenant_id: str,
    ntype: str,
    priority_score: float,
    title: str,
    description: str,
    related_tickets: Optional[List[str]] = None,
    batch_key: Optional[str] = None,
    source_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a new notification with unique key. Persists to DB."""
    db = get_db()
    return await db.create_notification(
        tenant_id=tenant_id,
        ntype=ntype,
        priority_score=priority_score,
        title=title,
        description=description,
        related_tickets=related_tickets,
        batch_key=batch_key,
        source_data=source_data,
    )


async def get_notification(key: str) -> Optional[Dict[str, Any]]:
    """Look up notification by unique key."""
    db = get_db()
    return await db.get_notification(key)


async def get_tenant_notifications(
    tenant_id: str,
    include_resolved: bool = False,
    min_priority: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get all notifications for a tenant, ordered by priority."""
    db = get_db()
    return await db.get_notifications(
        tenant_id=tenant_id,
        include_resolved=include_resolved,
        min_priority=min_priority,
    )


async def resolve_notification(key: str) -> bool:
    """Mark a notification as resolved."""
    db = get_db()
    return await db.resolve_notification(key)


async def dismiss_notification(key: str) -> bool:
    """Mark a notification as read (dismissed)."""
    db = get_db()
    return await db.dismiss_notification(key)


# ── Batching (delegated to jarvis_db) ────────────────────────


async def add_to_batch(
    tenant_id: str,
    batch_key: str,
    signal: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Add signal to batch buffer via DB."""
    db = get_db()
    confidence = signal.get("priority_score", 0.5)
    ticket_id = signal.get("ticket_id", "")
    return await db.add_to_batch(
        tenant_id=tenant_id,
        batch_key=batch_key,
        ticket_id=ticket_id,
        confidence=confidence,
    )


async def flush_batches(tenant_id: str) -> List[Dict[str, Any]]:
    """Force-flush all pending batches for a tenant."""
    db = get_db()
    return await db.flush_batches(tenant_id)


# ── Stats ───────────────────────────────────────────────────


async def get_stats(tenant_id: str) -> Dict[str, Any]:
    """Get notification stats for a tenant."""
    db = get_db()
    return await db.get_notification_stats(tenant_id)


# ── Test Helper ─────────────────────────────────────────────


def clear_all():
    """Clear all data (for testing). Resets the global backend."""
    from .jarvis_db import use_in_memory, reset_db
    reset_db()
    use_in_memory()
    logger.info("Notification center cleared and reset to InMemory mode")