"""
PARWA Event Emitter (BC-005, BC-001)

High-level helpers for emitting typed events with:
- Automatic payload validation via EventRegistry
- correlation_id injection for distributed tracing
- Timestamp injection
- Graceful error handling (never crashes caller)
- Tenant-scoped emission (BC-001)
"""

import json
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, Optional

from backend.app.core.events import EventRegistry, get_event_registry
from backend.app.logger import get_logger

logger = get_logger("event_emitter")

# ── Per-tenant rate limiting (BC-005) ──────────────────────
# Tracks emit timestamps per (company_id, event_type) in a sliding window.
# NOT thread-safe — acceptable because Socket.io server is single-threaded asyncio.
_rate_tracker: Dict[str, list] = defaultdict(list)
RATE_WINDOW_SECONDS = 1.0


def _check_rate_limit(company_id: str, event_type: str, limit: int) -> bool:
    """Check if emit is within rate limit.

    Uses a sliding window of RATE_WINDOW_SECONDS.
    Returns True if within limit, False if rate-limited.
    """
    key = f"{company_id}:{event_type}"
    now = time.time()
    timestamps = _rate_tracker[key]

    # Remove timestamps outside the window
    cutoff = now - RATE_WINDOW_SECONDS
    _rate_tracker[key] = [ts for ts in timestamps if ts > cutoff]

    if len(_rate_tracker[key]) >= limit:
        logger.warning(
            "emit_rate_limited",
            company_id=company_id,
            event_type=event_type,
            limit=limit,
            window=RATE_WINDOW_SECONDS,
        )
        return False

    _rate_tracker[key].append(now)
    return True


def reset_rate_tracker() -> None:
    """Reset rate tracker (for testing only)."""
    _rate_tracker.clear()


def _estimate_bytes(value: Any) -> int:
    """Rough byte estimate of a Python value when JSON-serialized."""
    try:
        return len(json.dumps(value, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _enrich_payload(
    payload: Dict[str, Any],
    company_id: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add correlation_id, timestamp, and company_id to payload."""
    enriched = dict(payload)
    enriched["_meta"] = {
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "timestamp": time.time(),
        "company_id": company_id,
    }
    return enriched


async def emit_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    registry: Optional[EventRegistry] = None,
) -> bool:
    """Emit a validated, enriched event to a tenant room.

    Validates event type and payload via registry, enriches with
    metadata, then delegates to emit_to_tenant.

    Args:
        company_id: Tenant identifier (BC-001).
        event_type: Registered event type string.
        payload: Event data (must match schema).
        correlation_id: Optional trace ID for distributed tracing.
        registry: EventRegistry instance (uses singleton if None).

    Returns:
        True if emitted successfully, False if validation failed.
    """
    reg = registry or get_event_registry()

    # Validate event type exists
    et = reg.get(event_type)
    if et is None:
        logger.warning(
            "emit_unknown_event_type",
            event_type=event_type,
            company_id=company_id,
        )
        return False

    # Check payload size
    payload_bytes = _estimate_bytes(payload)
    if payload_bytes > et.max_payload_bytes:
        logger.warning(
            "emit_payload_too_large",
            event_type=event_type,
            company_id=company_id,
            payload_bytes=payload_bytes,
            max_bytes=et.max_payload_bytes,
        )
        return False

    # Validate payload against schema
    try:
        cleaned = reg.validate(event_type, payload)
    except (ValueError, Exception) as exc:
        logger.warning(
            "emit_payload_validation_failed",
            event_type=event_type,
            company_id=company_id,
            error=str(exc),
        )
        return False

    # Check rate limit (BC-005: max 100 events/sec per tenant per type)
    if not _check_rate_limit(company_id, event_type, et.rate_limit_per_sec):
        return False

    # Enrich with metadata
    enriched = _enrich_payload(cleaned, company_id, correlation_id)

    # Emit to tenant room (never crash the caller — BC-005)
    try:
        from backend.app.core.socketio import emit_to_tenant

        await emit_to_tenant(
            company_id=company_id,
            event_type=event_type,
            payload=enriched,
        )
        logger.info(
            "event_emitted",
            event_type=event_type,
            company_id=company_id,
            category=et.category.value,
        )
        return True
    except Exception as exc:
        logger.error(
            "emit_failed",
            event_type=event_type,
            company_id=company_id,
            error=str(exc),
        )
        return False


# ── Convenience Helpers by Category ───────────────────────


async def emit_ticket_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit a ticket-scoped event (must start with 'ticket:')."""
    if not event_type.startswith("ticket:"):
        logger.warning("emit_ticket_mismatch", event_type=event_type)
        return False
    return await emit_event(company_id, event_type, payload, correlation_id)


async def emit_ai_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit an AI-scoped event (must start with 'ai:')."""
    if not event_type.startswith("ai:"):
        logger.warning("emit_ai_mismatch", event_type=event_type)
        return False
    return await emit_event(company_id, event_type, payload, correlation_id)


async def emit_approval_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit an approval-scoped event (must start with 'approval:')."""
    if not event_type.startswith("approval:"):
        logger.warning("emit_approval_mismatch", event_type=event_type)
        return False
    return await emit_event(company_id, event_type, payload, correlation_id)


async def emit_notification_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit a notification-scoped event (must start with 'notification:')."""
    if not event_type.startswith("notification:"):
        logger.warning("emit_notification_mismatch", event_type=event_type)
        return False
    return await emit_event(company_id, event_type, payload, correlation_id)


async def emit_system_event(
    event_type: str,
    payload: Dict[str, Any],
    company_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit a system event (can be global or tenant-scoped)."""
    if not event_type.startswith("system:"):
        logger.warning("emit_system_mismatch", event_type=event_type)
        return False
    cid = company_id or payload.get("company_id") or "system"
    return await emit_event(cid, event_type, payload, correlation_id)
