"""
PARWA Date/Time Utilities (BC-012)

All datetime operations use timezone-aware UTC.
No raw datetime.now() calls — always utcnow() or parse from ISO string.
This prevents timezone mixing bugs across the entire application.
"""

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime.

    Always use this instead of datetime.now() to prevent timezone bugs.
    Returns a datetime with tzinfo=timezone.utc.
    """
    return datetime.now(timezone.utc)


def to_iso(dt: Optional[datetime] = None) -> str:
    """Convert a datetime to ISO 8601 string.

    If dt is None, uses current UTC time.
    Always produces 'Z' suffix for UTC (not +00:00).
    """
    if dt is None:
        dt = utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def from_iso(s: str) -> Optional[datetime]:
    """Parse an ISO 8601 string to a timezone-aware datetime.

    Returns None if parsing fails (malformed input).
    Handles both 'Z' suffix and +00:00 offset.
    """
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to human-readable string.

    Examples: 0.5s -> '500ms', 1.2s -> '1.20s', 65.0s -> '1m 5.0s',
    3665.0s -> '1h 1m 5.0s'.
    Used for request timing in request logger.
    """
    if seconds < 0:
        return "0ms"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{int(mins)}m {secs:.1f}s"
    hours, mins = divmod(mins, 60)
    return f"{int(hours)}h {int(mins)}m {secs:.1f}s"


def is_expired(dt: datetime) -> bool:
    """Check if a datetime is in the past (before now in UTC).

    Used for token expiration, consent expiry, etc.
    """
    now = utcnow()
    return dt < now
