"""
PARWA Error Panel Service (F-091) — Operator Error Dashboard

Surfaces recent errors for operators in the Jarvis Command Center.
Provides grouped error views, dismissal, filtering, and real-time
push via Socket.io events.

Features:
- Get recent errors (default last 5, configurable)
- Group identical errors (same error_type + message hash) with count badge
- Dismiss errors (soft delete — preserves in logs)
- Filter by subsystem, severity, date range
- Real-time push via Socket.io events
- Track error storms (100+ errors in 10 seconds → summary badge)

Methods:
- get_recent_errors() — Paginated recent errors with grouping
- get_error_detail() — Full detail for a single error
- dismiss_error() — Soft-delete an error from the panel
- get_error_stats() — Aggregated error statistics

Building Codes: BC-001 (multi-tenant), BC-005 (real-time),
               BC-012 (error handling)
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("error_panel_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Default number of recent errors to return
DEFAULT_LIMIT = 5

# Maximum errors to return
MAX_LIMIT = 100

# Error storm detection: threshold and window
ERROR_STORM_THRESHOLD = 100
ERROR_STORM_WINDOW_SECONDS = 10

# Socket.io event names for real-time push
SOCKETIO_EVENT_NEW_ERROR = "error_panel:new_error"
SOCKETIO_EVENT_ERROR_DISMISSED = "error_panel:error_dismissed"
SOCKETIO_EVENT_ERROR_STORM = "error_panel:error_storm"
SOCKETIO_EVENT_ERROR_STATS_UPDATE = "error_panel:stats_update"

# Valid severity levels for filtering
VALID_SEVERITIES = {"debug", "info", "warning", "error", "critical"}


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _hash_message(message: str) -> str:
    """Create a deterministic hash for error grouping.

    Groups errors that have the same error_type + message content.
    """
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def get_recent_errors(
    company_id: str,
    db,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    severity: Optional[str] = None,
    subsystem: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Get recent errors for the Error Panel.

    Returns non-dismissed errors, optionally filtered, with
    grouping for identical errors (count badge).

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        limit: Number of errors to return (default 5).
        offset: Pagination offset.
        severity: Optional severity filter.
        subsystem: Optional subsystem filter.
        from_date: ISO 8601 start date filter.
        to_date: ISO 8601 end date filter.

    Returns:
        Dictionary with errors list, total count, and storm alert.
    """
    try:
        from app.models.system_health import ErrorLog
        from sqlalchemy import func

        query = db.query(ErrorLog).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(False),
        )

        # Apply filters
        if severity and severity in VALID_SEVERITIES:
            query = query.filter(ErrorLog.severity == severity)
        if subsystem:
            query = query.filter(ErrorLog.subsystem == subsystem)
        if from_date:
            try:
                dt = datetime.fromisoformat(from_date)
                query = query.filter(ErrorLog.created_at >= dt)
            except (ValueError, TypeError):
                pass
        if to_date:
            try:
                dt = datetime.fromisoformat(to_date)
                query = query.filter(ErrorLog.created_at <= dt)
            except (ValueError, TypeError):
                pass

        # Total count (before pagination)
        total = query.count()

        # Apply pagination
        effective_limit = min(max(limit, 1), MAX_LIMIT)
        errors = (
            query
            .order_by(ErrorLog.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
            .all()
        )

        # Build error entries
        error_entries = []
        for err in errors:
            error_entries.append({
                "id": str(err.id),
                "error_type": err.error_type,
                "message": err.message[:500],  # Truncate for display
                "severity": err.severity,
                "subsystem": err.subsystem,
                "affected_ticket_id": err.affected_ticket_id,
                "affected_agent_id": err.affected_agent_id,
                "created_at": (
                    err.created_at.isoformat() if err.created_at else None
                ),
                "message_hash": _hash_message(err.message),
            })

        # Group identical errors (same error_type + message hash)
        grouped = _group_errors(error_entries)

        # Check for error storm
        storm_alert = _check_error_storm(company_id, db)

        return {
            "errors": error_entries,
            "grouped": grouped,
            "total": total,
            "limit": effective_limit,
            "offset": offset,
            "storm_alert": storm_alert,
        }

    except Exception as exc:
        logger.error(
            "error_panel_recent_errors_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "errors": [],
            "grouped": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "storm_alert": None,
            "error": str(exc)[:200],
        }


def get_error_detail(
    error_id: str,
    company_id: str,
    db,
) -> Dict[str, Any]:
    """Get full detail for a single error.

    Includes the full stack trace and all metadata.

    Args:
        error_id: The error log UUID.
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.

    Returns:
        Dictionary with full error detail.
    """
    try:
        from app.models.system_health import ErrorLog

        error = db.query(ErrorLog).filter(
            ErrorLog.id == error_id,
            ErrorLog.company_id == company_id,
        ).first()

        if not error:
            return {
                "error": "Error not found",
                "error_id": error_id,
            }

        return {
            "id": str(error.id),
            "company_id": error.company_id,
            "error_type": error.error_type,
            "message": error.message,
            "stack_trace": error.stack_trace,
            "severity": error.severity,
            "subsystem": error.subsystem,
            "affected_ticket_id": error.affected_ticket_id,
            "affected_agent_id": error.affected_agent_id,
            "dismissed": error.dismissed,
            "dismissed_by": error.dismissed_by,
            "created_at": (
                error.created_at.isoformat() if error.created_at else None
            ),
        }

    except Exception as exc:
        logger.error(
            "error_panel_detail_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "error_id": error_id,
        }


def dismiss_error(
    error_id: str,
    company_id: str,
    user_id: str,
    db,
) -> Dict[str, Any]:
    """Dismiss an error from the Error Panel (soft delete).

    The error remains in the database for audit purposes but is
    hidden from the operator panel.

    Args:
        error_id: The error log UUID.
        company_id: Tenant identifier (BC-001).
        user_id: ID of the user dismissing the error.
        db: SQLAlchemy session.

    Returns:
        Dictionary with dismissal confirmation.
    """
    try:
        from app.models.system_health import ErrorLog

        error = db.query(ErrorLog).filter(
            ErrorLog.id == error_id,
            ErrorLog.company_id == company_id,
        ).first()

        if not error:
            return {
                "error": "Error not found",
                "error_id": error_id,
            }

        if error.dismissed:
            return {
                "message": "Error already dismissed",
                "error_id": error_id,
                "dismissed": True,
            }

        error.dismissed = True
        error.dismissed_by = user_id
        db.flush()

        logger.info(
            "error_panel_dismissed",
            company_id=company_id,
            error_id=error_id,
            dismissed_by=user_id,
        )

        return {
            "message": "Error dismissed successfully",
            "error_id": error_id,
            "dismissed": True,
            "dismissed_by": user_id,
            "dismissed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            "error_panel_dismiss_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "error_id": error_id,
        }


def get_error_stats(
    company_id: str,
    db,
    hours: int = 24,
) -> Dict[str, Any]:
    """Get aggregated error statistics for the Error Panel.

    Provides counts by severity, subsystem, and time window for
    the operator dashboard.

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        hours: Time window in hours (default 24).

    Returns:
        Dictionary with error statistics.
    """
    try:
        from app.models.system_health import ErrorLog
        from sqlalchemy import func

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Total errors in window (non-dismissed)
        total_errors = db.query(func.count(ErrorLog.id)).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(False),
            ErrorLog.created_at >= since,
        ).scalar() or 0

        # By severity
        severity_counts = db.query(
            ErrorLog.severity, func.count(ErrorLog.id),
        ).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(False),
            ErrorLog.created_at >= since,
        ).group_by(ErrorLog.severity).all()

        by_severity = {
            row[0]: row[1] for row in severity_counts
        }

        # By subsystem (top 10)
        subsystem_counts = db.query(
            ErrorLog.subsystem, func.count(ErrorLog.id),
        ).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(False),
            ErrorLog.created_at >= since,
        ).group_by(ErrorLog.subsystem).order_by(
            func.count(ErrorLog.id).desc(),
        ).limit(10).all()

        by_subsystem = [
            {"subsystem": row[0] or "unknown", "count": row[1]}
            for row in subsystem_counts
        ]

        # Error types (top 10)
        type_counts = db.query(
            ErrorLog.error_type, func.count(ErrorLog.id),
        ).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(False),
            ErrorLog.created_at >= since,
        ).group_by(ErrorLog.error_type).order_by(
            func.count(ErrorLog.id).desc(),
        ).limit(10).all()

        by_type = [
            {"error_type": row[0], "count": row[1]}
            for row in type_counts
        ]

        # Dismissed count
        dismissed_count = db.query(func.count(ErrorLog.id)).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.dismissed.is_(True),
            ErrorLog.created_at >= since,
        ).scalar() or 0

        # Error storm detection
        storm_alert = _check_error_storm(company_id, db)

        return {
            "total_errors": total_errors,
            "dismissed_count": dismissed_count,
            "by_severity": by_severity,
            "by_subsystem": by_subsystem,
            "by_type": by_type,
            "storm_alert": storm_alert,
            "period_hours": hours,
            "since": since.isoformat(),
        }

    except Exception as exc:
        logger.error(
            "error_panel_stats_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "total_errors": 0,
            "dismissed_count": 0,
            "by_severity": {},
            "by_subsystem": [],
            "by_type": [],
            "storm_alert": None,
            "error": str(exc)[:200],
        }


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _group_errors(
    errors: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group identical errors by error_type + message_hash.

    Returns a list of groups, each with a count badge and the
    most recent error from the group.
    """
    groups: Dict[str, Dict[str, Any]] = {}

    for err in errors:
        group_key = f"{err['error_type']}:{err['message_hash']}"

        if group_key not in groups:
            groups[group_key] = {
                "group_key": group_key,
                "error_type": err["error_type"],
                "message_hash": err["message_hash"],
                "message_preview": err["message"][:200],
                "severity": err["severity"],
                "subsystem": err["subsystem"],
                "count": 0,
                "latest_error_id": err["id"],
                "latest_created_at": err["created_at"],
                "error_ids": [],
            }

        groups[group_key]["count"] += 1
        groups[group_key]["error_ids"].append(err["id"])

        # Keep the most recent as representative
        if err["created_at"] and groups[group_key]["latest_created_at"]:
            if err["created_at"] >= groups[group_key]["latest_created_at"]:
                groups[group_key]["latest_error_id"] = err["id"]
                groups[group_key]["latest_created_at"] = err["created_at"]

    return sorted(groups.values(), key=lambda g: g["count"], reverse=True)


def _check_error_storm(
    company_id: str,
    db,
) -> Optional[Dict[str, Any]]:
    """Check if an error storm is occurring.

    An error storm is defined as 100+ errors in a 10-second window.

    Args:
        company_id: Tenant identifier.
        db: SQLAlchemy session.

    Returns:
        Storm alert dict if a storm is detected, None otherwise.
    """
    try:
        from app.models.system_health import ErrorLog
        from sqlalchemy import func

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=ERROR_STORM_WINDOW_SECONDS)

        count = db.query(func.count(ErrorLog.id)).filter(
            ErrorLog.company_id == company_id,
            ErrorLog.created_at >= window_start,
        ).scalar() or 0

        if count >= ERROR_STORM_THRESHOLD:
            return {
                "active": True,
                "error_count": count,
                "window_seconds": ERROR_STORM_WINDOW_SECONDS,
                "threshold": ERROR_STORM_THRESHOLD,
                "detected_at": now.isoformat(),
                "severity": (
                    "critical" if count >= ERROR_STORM_THRESHOLD * 3
                    else "high"
                ),
            }

        return None

    except Exception as exc:
        logger.warning(
            "error_storm_check_failed",
            company_id=company_id,
            error=str(exc),
        )
        return None


__all__ = [
    "SOCKETIO_EVENT_NEW_ERROR",
    "SOCKETIO_EVENT_ERROR_DISMISSED",
    "SOCKETIO_EVENT_ERROR_STORM",
    "SOCKETIO_EVENT_ERROR_STATS_UPDATE",
    "get_recent_errors",
    "get_error_detail",
    "dismiss_error",
    "get_error_stats",
]
