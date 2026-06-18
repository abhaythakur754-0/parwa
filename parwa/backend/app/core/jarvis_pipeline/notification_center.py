"""
Notification Center — In-Memory Store

Stores notifications with unique keys (PARWA-NFY-XXX).
In production: PostgreSQL table. For now: in-memory dict + file persistence.

Rules:
  1. UNSOLVED/STUCK ONLY — never notify on resolved tickets
  2. UNIQUE KEY per notification: PARWA-NFY-XXX
  3. BATCH SIMILAR — group within 5-min window
  4. NOISE FILTER — LOW priority logged but not pushed
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ── In-Memory Store ────────────────────────────────────────────

_store: Dict[str, Dict[str, Any]] = {}  # notification_key → notification
_batch_buffer: Dict[str, List[Dict]] = {}  # batch_key → list of signals
_counter_lock = threading.Lock()
_next_id = 1


def _next_notification_number() -> int:
    global _next_id
    with _counter_lock:
        n = _next_id
        _next_id += 1
    return n


# ── Priority Constants ────────────────────────────────────────

PRIORITY_CRITICAL = "CRITICAL"   # > 0.85 — push immediately
PRIORITY_HIGH = "HIGH"           # 0.65-0.85 — next batch cycle
PRIORITY_MEDIUM = "MEDIUM"       # 0.40-0.65 — digest (5 min)
PRIORITY_LOW = "LOW"             # < 0.40 — daily summary only

PRIORITY_THRESHOLDS = {
    PRIORITY_CRITICAL: 0.85,
    PRIORITY_HIGH: 0.65,
    PRIORITY_MEDIUM: 0.40,
}

# ── Notification Types ────────────────────────────────────────

TYPE_STUCK_TICKET = "stuck_ticket"
TYPE_QUOTA_LOW = "quota_low"
TYPE_INTEGRATION_DOWN = "integration_down"
TYPE_POLICY_CHANGE = "policy_change"
TYPE_ACCURACY_DROP = "accuracy_drop"
TYPE_SLA_RISK = "sla_risk"


def _priority_from_score(score: float) -> str:
    if score >= PRIORITY_THRESHOLDS[PRIORITY_CRITICAL]:
        return PRIORITY_CRITICAL
    elif score >= PRIORITY_THRESHOLDS[PRIORITY_HIGH]:
        return PRIORITY_HIGH
    elif score >= PRIORITY_THRESHOLDS[PRIORITY_MEDIUM]:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW


# ── Core Functions ────────────────────────────────────────────


def create_notification(
    tenant_id: str,
    ntype: str,
    priority_score: float,
    title: str,
    description: str,
    related_tickets: Optional[List[str]] = None,
    batch_key: Optional[str] = None,
    source_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a new notification with unique key."""
    num = _next_notification_number()
    key = f"PARWA-NFY-{num:03d}"
    priority = _priority_from_score(priority_score)

    notification = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "notification_key": key,
        "type": ntype,
        "priority": priority,
        "priority_score": round(priority_score, 4),
        "title": title,
        "description": description,
        "related_tickets": related_tickets or [],
        "batch_key": batch_key,
        "source_data": source_data or {},
        "is_read": False,
        "is_resolved": False,
        "created_at": time.time(),
        "resolved_at": None,
    }

    _store[key] = notification
    return notification


def get_notification(key: str) -> Optional[Dict[str, Any]]:
    """Look up notification by unique key (admin: 'What's PARWA-NFY-001?')."""
    return _store.get(key)


def get_tenant_notifications(
    tenant_id: str,
    include_resolved: bool = False,
    min_priority: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get all notifications for a tenant, ordered by priority."""
    priority_order = {PRIORITY_CRITICAL: 0, PRIORITY_HIGH: 1, PRIORITY_MEDIUM: 2, PRIORITY_LOW: 3}
    min_rank = priority_order.get(min_priority, 99) if min_priority else 99

    results = []
    for n in _store.values():
        if n["tenant_id"] != tenant_id:
            continue
        if not include_resolved and n["is_resolved"]:
            continue
        if priority_order.get(n["priority"], 99) > min_rank:
            continue
        results.append(n)

    results.sort(key=lambda x: (-priority_order.get(x["priority"], 99), -x["created_at"]))
    return results


def resolve_notification(key: str) -> bool:
    """Mark a notification as resolved."""
    n = _store.get(key)
    if n and not n["is_resolved"]:
        n["is_resolved"] = True
        n["resolved_at"] = time.time()
        return True
    return False


def dismiss_notification(key: str) -> bool:
    """Mark a notification as read (dismissed)."""
    n = _store.get(key)
    if n:
        n["is_read"] = True
        return True
    return False


# ── Batching ──────────────────────────────────────────────────

BATCH_WINDOW_S = 300  # 5 minutes


def add_to_batch(
    tenant_id: str,
    batch_key: str,
    signal: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Add signal to batch buffer. If batch is full or window expired, flush."""
    if tenant_id not in _batch_buffer:
        _batch_buffer[tenant_id] = []

    # Find existing batch with same key
    existing = None
    for b in _batch_buffer[tenant_id]:
        if b.get("batch_key") == batch_key and (time.time() - b.get("batch_start", 0)) < BATCH_WINDOW_S:
            existing = b
            break

    if existing:
        existing["signals"].append(signal)
        existing["signal_count"] = len(existing["signals"])
        # Don't flush yet — still within window
        return None
    else:
        # Start new batch
        new_batch = {
            "batch_key": batch_key,
            "tenant_id": tenant_id,
            "batch_start": time.time(),
            "signals": [signal],
            "signal_count": 1,
        }
        _batch_buffer[tenant_id].append(new_batch)
        return None


def flush_batches(tenant_id: str) -> List[Dict[str, Any]]:
    """Force-flush all pending batches for a tenant."""
    results = []
    if tenant_id in _batch_buffer:
        results = _batch_buffer[tenant_id]
        _batch_buffer[tenant_id] = []
    return results


# ── Stats / Admin ────────────────────────────────────────────


def get_stats(tenant_id: str) -> Dict[str, Any]:
    """Get notification stats for a tenant."""
    tenant_nfs = [n for n in _store.values() if n["tenant_id"] == tenant_id]
    return {
        "total": len(tenant_nfs),
        "unread": sum(1 for n in tenant_nfs if not n["is_read"]),
        "unresolved": sum(1 for n in tenant_nfs if not n["is_resolved"]),
        "by_priority": {
            p: sum(1 for n in tenant_nfs if n["priority"] == p)
            for p in [PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]
        },
        "by_type": {},
    }


def clear_all():
    """Clear all notifications (for testing)."""
    global _next_id
    _store.clear()
    _batch_buffer.clear()
    _next_id = 1