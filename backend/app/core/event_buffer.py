"""
PARWA Event Buffer (BC-005, BC-001)

Provides a Redis-based event buffer for Socket.io reconnection recovery.
Every Socket.io emit also stores the event in this buffer so that clients
can fetch missed events after reconnection.

BC-005 Requirements:
- Event buffer retention: 24 hours (86400 seconds)
- Events stored with: tenant_id, event_type, payload (JSON), created_at
- On reconnect: GET /api/events/since?last_seen={timestamp}
  fetches missed events
- Graceful degradation: if Redis is down, emit still works
  (event just not buffered)

Key namespace: parwa:{company_id}:events (BC-001 — tenant isolation)
Key type: Redis Sorted Set (score = epoch timestamp for range queries)

Usage:
    from app.core.event_buffer import (
        store_event, get_events_since, cleanup_old_events
    )

    # Store an event (called automatically by emit_to_tenant)
    await store_event("acme", "ticket:new", {"id": "123"})

    # Fetch events since a timestamp (for reconnection recovery)
    events = await get_events_since("acme", last_seen=1700000000.0)

    # Cleanup old events (24h TTL via Redis EXPIRE + explicit cleanup)
    await cleanup_old_events("acme")
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.redis import get_redis, make_key
from app.logger import get_logger

logger = get_logger("event_buffer")

# BC-005: Event buffer retention period — 24 hours
EVENT_BUFFER_TTL_SECONDS = 86400

# Redis sorted set key suffix
EVENT_BUFFER_KEY_SUFFIX = "events"

# Maximum number of events to return per query (prevent DoS)
MAX_EVENTS_PER_QUERY = 500


def _event_key(company_id: str) -> str:
    """Build the Redis sorted set key for a tenant's event buffer.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        Redis key: parwa:{company_id}:events
    """
    return make_key(company_id, EVENT_BUFFER_KEY_SUFFIX)


async def store_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> bool:
    """Store an event in the tenant's event buffer.

    Events are stored in a Redis Sorted Set with the score being the
    epoch timestamp. This allows efficient range queries for fetching
    events since a given time.

    BC-005: Every Socket.io emit MUST also store in event buffer.
    BC-001: Events are stored per tenant (company_id scoping).

    Args:
        company_id: Tenant identifier (required, BC-001).
        event_type: Event type string (e.g., "ticket:new", "ai:response").
        payload: Event data dictionary.

    Returns:
        True if stored successfully, False otherwise (fail-open).
    """
    try:
        client = await get_redis()
        key = _event_key(company_id)
        now = time.time()

        # Build the event record
        event_record = json.dumps(
            {
                "event_type": event_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "timestamp": now,
            },
            default=str,
        )

        # Add to sorted set with timestamp as score
        await client.zadd(key, {event_record: now})

        # Set TTL on the key (auto-cleanup, BC-005)
        await client.expire(key, EVENT_BUFFER_TTL_SECONDS)

        return True
    except Exception as exc:
        # BC-005: Event buffer failure should NOT break the emit
        logger.warning(
            "event_buffer_store_failed",
            company_id=company_id,
            event_type=event_type,
            error=str(exc),
        )
        return False


async def get_events_since(
    company_id: str,
    last_seen: Optional[float] = None,
    limit: int = MAX_EVENTS_PER_QUERY,
) -> List[Dict[str, Any]]:
    """Fetch events from the buffer since a given timestamp.

    Used by the reconnection endpoint GET /api/events/since?last_seen=...
    to deliver missed events to reconnecting clients.

    BC-005: On reconnect, client fetches all events missed during
    the disconnection period.

    Args:
        company_id: Tenant identifier (BC-001).
        last_seen: Epoch timestamp of last received event.
                   If None, returns the most recent events.
        limit: Maximum events to return (default 500, capped).

    Returns:
        List of event dictionaries, ordered by timestamp ascending.
    """
    try:
        client = await get_redis()
        key = _event_key(company_id)

        # Cap limit to prevent DoS
        limit = min(limit, MAX_EVENTS_PER_QUERY)

        # Use last_seen or default to 0 (return all)
        if last_seen is None:
            last_seen = 0.0

        # Query sorted set: events with score > last_seen
        # Use ( as open interval to exclude exact match
        raw_events = await client.zrangebyscore(
            key,
            f"({last_seen}",
            "+inf",
            start=0,
            num=limit,
        )

        # Parse JSON events
        events = []
        for raw in raw_events:
            try:
                event = json.loads(raw)
                events.append(event)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "event_buffer_parse_error",
                    company_id=company_id,
                    raw_preview=raw[:100] if raw else "empty",
                )
                continue

        return events
    except Exception as exc:
        logger.warning(
            "event_buffer_fetch_failed",
            company_id=company_id,
            error=str(exc),
        )
        return []


async def cleanup_old_events(company_id: str) -> int:
    """Remove events older than 24 hours from the buffer.

    BC-005: Event buffer retention is 24 hours. Events older than 24h
    are cleaned up. Redis EXPIRE on the key handles full key cleanup,
    but this function also trims individual entries.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        Number of events removed.
    """
    try:
        client = await get_redis()
        key = _event_key(company_id)
        cutoff = time.time() - EVENT_BUFFER_TTL_SECONDS

        # Remove entries with score < cutoff (older than 24h)
        removed = await client.zremrangebyscore(key, "-in", f"({cutoff}")
        return removed
    except Exception as exc:
        logger.warning(
            "event_buffer_cleanup_failed",
            company_id=company_id,
            error=str(exc),
        )
        return 0


async def get_buffer_stats(company_id: str) -> Dict[str, Any]:
    """Get statistics about the event buffer for a tenant.

    Useful for monitoring and debugging.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        Dict with 'total_events', 'oldest_event_age_hours',
        'newest_event_age_hours'.
    """
    try:
        client = await get_redis()
        key = _event_key(company_id)

        total = await client.zcard(key)
        if total == 0:
            return {
                "total_events": 0,
                "oldest_event_age_hours": None,
                "newest_event_age_hours": None,
            }

        now = time.time()
        # Get oldest and newest by score
        oldest_raw = await client.zrange(key, 0, 0)
        newest_raw = await client.zrange(key, -1, -1)

        oldest_age = None
        newest_age = None

        if oldest_raw:
            try:
                oldest_event = json.loads(oldest_raw[0])
                oldest_ts = oldest_event.get("timestamp", now)
                oldest_age = round((now - oldest_ts) / 3600, 2)
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        if newest_raw:
            try:
                newest_event = json.loads(newest_raw[0])
                newest_ts = newest_event.get("timestamp", now)
                newest_age = round((now - newest_ts) / 3600, 2)
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        return {
            "total_events": total,
            "oldest_event_age_hours": oldest_age,
            "newest_event_age_hours": newest_age,
        }
    except Exception as exc:
        logger.warning(
            "event_buffer_stats_failed",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "total_events": 0,
            "oldest_event_age_hours": None,
            "newest_event_age_hours": None,
        }
