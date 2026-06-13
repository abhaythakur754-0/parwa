"""
PARWA Jarvis Event Dispatcher (Phase 2.4)

Dispatches real-time events when the awareness engine detects changes.
Supports two delivery channels:
  1. Redis Pub/Sub → WebSocket server → browser
  2. SSE (Server-Sent Events) fallback for simpler setups

Event Types:
  - jarvis:activity  — New alert created, alert acknowledged/resolved
  - jarvis:tick      — Awareness tick completed with summary
  - jarvis:state     — System state changed (health, quality, etc.)

Architecture:
  Awareness Engine → alert created
      → EventDispatcher.dispatch("jarvis:activity", payload)
      → Redis PUBLISH jarvis:events:{company_id}
      → WebSocket server picks up → pushes to browser

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_event_dispatcher")


# ── Redis channel patterns ────────────────────────────────────────

REDIS_CHANNEL_PREFIX = "jarvis:events"
REDIS_CHANNEL_COMPANY = f"{REDIS_CHANNEL_PREFIX}:{{company_id}}"

# Event type constants
EVENT_ACTIVITY = "jarvis:activity"
EVENT_TICK = "jarvis:tick"
EVENT_STATE = "jarvis:state"

__all__ = [
    "dispatch_event",
    "dispatch_alert_event",
    "dispatch_tick_event",
    "dispatch_state_event",
    "get_redis_channel",
    "build_event_payload",
]


# ══════════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ══════════════════════════════════════════════════════════════════


def dispatch_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
) -> bool:
    """Dispatch a real-time event via Redis Pub/Sub.

    This is the main entry point. It publishes the event to a
    Redis channel scoped to the company_id. A WebSocket server
    (or SSE endpoint) subscribes to these channels and pushes
    the event to connected browsers.

    Args:
        company_id: Company ID for channel scoping (BC-001).
        event_type: One of jarvis:activity, jarvis:tick, jarvis:state.
        payload: Event-specific data dict.
        session_id: Optional session ID for client-side routing.

    Returns:
        True if dispatch succeeded, False otherwise.
    """
    try:
        channel = get_redis_channel(company_id)

        event = build_event_payload(
            company_id=company_id,
            event_type=event_type,
            payload=payload,
            session_id=session_id,
        )

        # Publish to Redis
        _redis_publish(channel, event)

        logger.debug(
            "event_dispatched: channel=%s, type=%s, company=%s",
            channel, event_type, company_id,
        )
        return True

    except Exception:
        logger.exception(
            "event_dispatch_failed: type=%s, company=%s",
            event_type, company_id,
        )
        return False


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE DISPATCHERS
# ══════════════════════════════════════════════════════════════════


def dispatch_alert_event(
    company_id: str,
    session_id: str,
    alert_id: str,
    alert_type: str,
    severity: str,
    title: str,
    action: str = "created",
) -> bool:
    """Dispatch an alert-related event.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        alert_id: Alert ID.
        alert_type: Type of alert (e.g., ticket_volume_spike).
        severity: Alert severity.
        title: Alert title.
        action: One of created, acknowledged, dismissed, resolved.

    Returns:
        True if dispatch succeeded.
    """
    payload = {
        "alert_id": alert_id,
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "action": action,
    }
    return dispatch_event(
        company_id=company_id,
        event_type=EVENT_ACTIVITY,
        payload=payload,
        session_id=session_id,
    )


def dispatch_tick_event(
    company_id: str,
    session_id: str,
    tick_number: int,
    tick_type: str,
    system_health: str,
    alerts_created: int,
    quality_score: Optional[float] = None,
    drift_score: Optional[float] = None,
) -> bool:
    """Dispatch a tick completion event.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        tick_number: Tick counter.
        tick_type: periodic, on_change, manual, emergency.
        system_health: Current system health status.
        alerts_created: Number of alerts created in this tick.
        quality_score: Current quality score (optional).
        drift_score: Current drift score (optional).

    Returns:
        True if dispatch succeeded.
    """
    payload = {
        "tick_number": tick_number,
        "tick_type": tick_type,
        "system_health": system_health,
        "alerts_created": alerts_created,
        "quality_score": quality_score,
        "drift_score": drift_score,
    }
    return dispatch_event(
        company_id=company_id,
        event_type=EVENT_TICK,
        payload=payload,
        session_id=session_id,
    )


def dispatch_state_event(
    company_id: str,
    session_id: str,
    field: str,
    old_value: Any,
    new_value: Any,
    change_type: str = "changed",
) -> bool:
    """Dispatch a state change event.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        field: The field that changed (e.g., system_health).
        old_value: Previous value.
        new_value: New value.
        change_type: One of changed, worsened, improved, recovered.

    Returns:
        True if dispatch succeeded.
    """
    payload = {
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "change_type": change_type,
    }
    return dispatch_event(
        company_id=company_id,
        event_type=EVENT_STATE,
        payload=payload,
        session_id=session_id,
    )


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def get_redis_channel(company_id: str) -> str:
    """Get the Redis Pub/Sub channel for a company.

    Args:
        company_id: Company ID.

    Returns:
        Channel name string.
    """
    return f"{REDIS_CHANNEL_PREFIX}:{company_id}"


def build_event_payload(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
) -> str:
    """Build a JSON event payload for Redis publish.

    Args:
        company_id: Company ID.
        event_type: Event type string.
        payload: Event-specific data.
        session_id: Optional session ID.

    Returns:
        JSON string ready for Redis PUBLISH.
    """
    event = {
        "type": event_type,
        "company_id": company_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    return json.dumps(event, default=str)


def _redis_publish(channel: str, message: str) -> bool:
    """Publish a message to a Redis channel.

    Safely handles Redis connection failures. If Redis is unavailable,
    the event is silently dropped (BC-008: never crash).

    Args:
        channel: Redis channel name.
        message: JSON message string.

    Returns:
        True if published successfully.
    """
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()

        redis_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.publish(channel, message)
        return True
    except ImportError:
        # Redis not installed — events are fire-and-forget
        logger.debug("redis_not_available: event dropped, channel=%s", channel)
        return False
    except Exception:
        logger.debug("redis_publish_failed: channel=%s", channel, exc_info=True)
        return False
