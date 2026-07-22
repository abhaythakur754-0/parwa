"""
Jarvis Awareness Alert CRUD — extracted from jarvis_awareness_engine.py

These 5 functions are independent (no cross-function calls).
Extracted for maintainability.
"""


import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from app.logger import get_logger
from database.models.jarvis import JarvisSession, JarvisMessage
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)

logger = get_logger("jarvis_awareness_engine")


# ── Constants ──────────────────────────────────────────────────────

DEFAULT_TICK_INTERVAL_SECONDS = 30
MAX_SNAPSHOTS_PER_SESSION = 2880  # 24h at 30s intervals
SNAPSHOT_PRUNE_BATCH = 100
MAX_ALERTS_PER_SESSION = 50
ALERT_PRUNE_BATCH = 20

# Spike detection: volume > SPIKE_MULTIPLIER * avg = spike
SPIKE_MULTIPLIER = 2.0
# Utilization warning: > UTILIZATION_WARN_THRESHOLD = warning alert
UTILIZATION_WARN_THRESHOLD = 80.0
# Utilization critical: > UTILIZATION_CRITICAL_THRESHOLD = critical alert
UTILIZATION_CRITICAL_THRESHOLD = 95.0
# Quality score below this = warning
QUALITY_WARN_THRESHOLD = 0.70
# Quality score below this = critical
QUALITY_CRITICAL_THRESHOLD = 0.50
# Drift score above this = warning
DRIFT_WARN_THRESHOLD = 0.30
# Drift score above this = critical
DRIFT_CRITICAL_THRESHOLD = 0.60
# Plan usage above this = warning
PLAN_USAGE_WARN_THRESHOLD = 80.0
# Plan usage above this = critical
PLAN_USAGE_CRITICAL_THRESHOLD = 95.0
# Days until renewal below this = info
RENEWAL_INFO_THRESHOLD = 7
# Days until renewal below this = warning
RENEWAL_WARN_THRESHOLD = 3

# Alert TTL defaults (seconds)
ALERT_TTL_INFO = 3600       # 1 hour
ALERT_TTL_WARNING = 14400   # 4 hours
ALERT_TTL_CRITICAL = 86400  # 24 hours
ALERT_TTL_EMERGENCY = 0     # No expiry

# Cooldown: prevent alert spam during sustained issues (5 minutes)
RULE_COOLDOWN_SECONDS = 300
# Error rate thresholds (percentage of errors vs ticket volume)
ERROR_RATE_WARN_THRESHOLD = 0.10    # 10% error rate = warning
ERROR_RATE_CRITICAL_THRESHOLD = 0.25  # 25% error rate = critical
# Training mistake count threshold
TRAINING_MISTAKE_WARN_THRESHOLD = 10

__all__ = [
    # Only export functions defined in THIS file
    "get_snapshot_history",
    "get_active_alerts",
    "acknowledge_alert",
    "dismiss_alert",
    "resolve_alert",
]


# ══════════════════════════════════════════════════════════════════
# MAIN TICK: The Heart of the Awareness Engine
# ══════════════════════════════════════════════════════════════════




def get_snapshot_history(
    db: Session,
    session_id: str,
    company_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisAwarenessSnapshot], int]:
    """Get paginated snapshot history for a session.

    Returns snapshots in reverse chronological order (newest first).

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        limit: Max snapshots to return.
        offset: Pagination offset.

    Returns:
        Tuple of (snapshots_list, total_count).
    """
    query = (
        db.query(JarvisAwarenessSnapshot)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
    )
    total = query.count()
    snapshots = query.offset(offset).limit(limit).all()
    return snapshots, total


def get_active_alerts(
    db: Session,
    session_id: str,
    company_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisProactiveAlert], int]:
    """Get active (non-resolved, non-expired) alerts for a session.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        severity: Filter by severity (optional).
        category: Filter by category (optional).
        limit: Max alerts to return.
        offset: Pagination offset.

    Returns:
        Tuple of (alerts_list, total_count).
    """
    query = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
    )

    if severity:
        query = query.filter(JarvisProactiveAlert.severity == severity)
    if category:
        query = query.filter(JarvisProactiveAlert.category == category)

    query = query.order_by(
        # Emergency first, then critical, warning, info
        JarvisProactiveAlert.severity.desc(),
        JarvisProactiveAlert.created_at.desc(),
    )

    total = query.count()
    alerts = query.offset(offset).limit(limit).all()
    return alerts, total


def acknowledge_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
    user_id: str,
) -> JarvisProactiveAlert:
    """Acknowledge an active alert.

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.
        user_id: User ID who acknowledged.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found or not in active state.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status == "active",
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Active alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "acknowledged"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_acknowledged: id=%s, user=%s, session=%s",
        alert_id, user_id, session_id,
    )

    return alert


def dismiss_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
    user_id: str,
) -> JarvisProactiveAlert:
    """Dismiss an active or acknowledged alert.

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.
        user_id: User ID who dismissed.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found or already resolved/expired.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Dismissible alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "dismissed"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = alert.acknowledged_at or datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_dismissed: id=%s, user=%s, session=%s",
        alert_id, user_id, session_id,
    )

    return alert


def resolve_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
) -> JarvisProactiveAlert:
    """Resolve an active or acknowledged alert.

    Typically called when the underlying issue has been fixed
    (e.g., system health recovered, quality score improved).

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Resolvable alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_resolved: id=%s, type=%s, session=%s",
        alert_id, alert.alert_type, session_id,
    )

    return alert


