"""
PARWA Jarvis Awareness Engine

The brain that makes Jarvis PROACTIVE. Like a human employee who notices
things ("hey, ticket volume just spiked 3x"), the Awareness Engine monitors
the system state and generates alerts when something needs attention.

Architecture:
  7 Monitoring Domains (from GROUP 14 of ParwaGraphState):
    1. PLAN & SUBSCRIPTION  — plan usage, renewal, subscription status
    2. SYSTEM HEALTH        — overall health, per-channel health
    3. TICKET VOLUME        — today vs avg, spike detection
    4. AGENT POOL           — utilization, capacity warnings
    5. TRAINING             — Agent Lightning training state, mistake count
    6. DRIFT & QUALITY      — model drift, quality score, quality alerts
    7. ERRORS               — last 5 errors, error rate tracking

  Tick Types:
    - periodic:  Automatic tick (every 30 seconds via Celery/Redis beat)
    - on_change: Written when a monitored field changes significantly
    - manual:    Triggered by user/admin from dashboard
    - emergency: Written when emergency_state changes

  Data Flow:
    ParwaGraphState GROUP 14 fields
        → collect_awareness_state() reads real-time data
        → run_awareness_tick() runs rule checks
        → writes JarvisAwarenessSnapshot (always)
        → writes JarvisProactiveAlert (when threshold breached)
        → updates CC session context

  Fallback Strategy:
    The engine NEVER crashes. If a domain collector fails, that domain's
    data is marked as "unknown" and the engine continues with the other
    domains. Partial awareness is better than no awareness.

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
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

__all__ = [
    # Main tick
    "run_awareness_tick",
    # State collection
    "collect_awareness_state",
    # Snapshots
    "get_latest_snapshot",
    "get_snapshot_history",
    "create_snapshot",
    # Alerts
    "get_active_alerts",
    "acknowledge_alert",
    "dismiss_alert",
    "resolve_alert",
    "create_alert",
    # Pruning
    "prune_old_snapshots",
    "prune_expired_alerts",
    # Delta detection
    "compute_awareness_delta",
]


# ══════════════════════════════════════════════════════════════════
# MAIN TICK: The Heart of the Awareness Engine
# ══════════════════════════════════════════════════════════════════


def run_awareness_tick(
    db: Session,
    company_id: str,
    session_id: str,
    user_id: str,
    tick_type: str = "periodic",
    override_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a single awareness tick for a customer care session.

    This is the main entry point for the Awareness Engine.
    It collects current state, compares with previous snapshot,
    generates a new snapshot, and creates alerts if needed.

    Flow:
      1. Validate session (must be customer_care type)
      2. Collect current awareness state from 7 domains
      3. Get previous snapshot for delta detection
      4. Create new JarvisAwarenessSnapshot
      5. Run rule checks on each domain
      6. Create JarvisProactiveAlert for any threshold breaches
      7. Update CC session context
      8. Prune old snapshots if needed
      9. Return tick result with snapshot + alerts

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: User ID for security scoping.
        tick_type: One of periodic, on_change, manual, emergency.
        override_state: Optional pre-collected state (for testing/internal use).

    Returns:
        Dict with snapshot, alerts_created, tick_metadata.
    """
    start_time = time.monotonic()

    # ── Step 1: Validate session ──
    from app.services.jarvis_cc_service import get_cc_session

    session = get_cc_session(db, session_id, user_id, company_id)
    ctx = _safe_parse_json(session.context_json)

    # ── Step 2: Collect current awareness state ──
    if override_state:
        current_state = override_state
    else:
        current_state = collect_awareness_state(db, company_id, session_id)

    # ── Step 3: Get previous snapshot for delta ──
    previous_snapshot = get_latest_snapshot(db, session_id, company_id)
    previous_state = None
    if previous_snapshot:
        try:
            previous_state = _safe_parse_json(previous_snapshot.raw_state_json)
        except Exception:
            pass  # BC-008

    # ── Step 4: Compute tick number ──
    tick_number = 1
    if previous_snapshot and previous_snapshot.tick_number:
        tick_number = previous_snapshot.tick_number + 1

    # ── Step 5: Compute delta ──
    delta = compute_awareness_delta(current_state, previous_state)

    # ── Step 6: Create snapshot ──
    snapshot = create_snapshot(
        db=db,
        session_id=session_id,
        company_id=company_id,
        state=current_state,
        tick_type=tick_type,
        tick_number=tick_number,
    )

    # ── Step 7: Run rule checks → generate alerts ──
    alerts_created = _run_rule_checks(
        db=db,
        session_id=session_id,
        company_id=company_id,
        current_state=current_state,
        delta=delta,
        snapshot_id=str(snapshot.id),
    )

    # ── Step 8: Update CC session context ──
    try:
        ctx["awareness_enabled"] = True
        ctx["awareness_last_tick"] = datetime.now(timezone.utc).isoformat()
        ctx["awareness_tick_number"] = tick_number
        ctx["awareness_system_health"] = current_state.get("system_health", "unknown")
        ctx["awareness_quality_score"] = current_state.get("quality_score")
        ctx["awareness_drift_score"] = current_state.get("drift_score")
        ctx["awareness_ticket_volume_today"] = current_state.get("ticket_volume_today", 0)
        ctx["active_alerts_count"] = len(alerts_created)
        ctx["last_awareness_delta"] = delta

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()
    except Exception:
        logger.exception("Failed to update CC context after awareness tick")

    # ── Step 9: Prune old snapshots ──
    try:
        prune_old_snapshots(db, session_id, company_id)
    except Exception:
        logger.exception("Failed to prune old snapshots")

    # ── Step 10: Prune expired alerts ──
    try:
        prune_expired_alerts(db, session_id, company_id)
    except Exception:
        logger.exception("Failed to prune expired alerts")

    total_ms = round((time.monotonic() - start_time) * 1000, 2)

    tick_result = {
        "snapshot_id": str(snapshot.id),
        "tick_type": tick_type,
        "tick_number": tick_number,
        "alerts_created": len(alerts_created),
        "alert_ids": [str(a.id) for a in alerts_created],
        "system_health": current_state.get("system_health", "unknown"),
        "quality_score": current_state.get("quality_score"),
        "drift_score": current_state.get("drift_score"),
        "delta_significant": delta.get("has_significant_changes", False),
        "total_ms": total_ms,
    }

    logger.info(
        "awareness_tick_complete: session=%s, type=%s, tick=%d, "
        "alerts=%d, health=%s, quality=%s, delta=%s, ms=%s",
        session_id, tick_type, tick_number,
        len(alerts_created),
        current_state.get("system_health", "unknown"),
        current_state.get("quality_score", "N/A"),
        delta.get("has_significant_changes", False),
        total_ms,
    )

    return tick_result


# ══════════════════════════════════════════════════════════════════
# STATE COLLECTION: Read real-time data from 7 domains
# ══════════════════════════════════════════════════════════════════


def collect_awareness_state(
    db: Session,
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Collect current awareness state from all 7 monitoring domains.

    Each domain collector is independently wrapped in try/except (BC-008).
    If a collector fails, its fields are set to safe defaults and
    the engine continues with the other domains.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID for context lookup.

    Returns:
        Dict with all GROUP 14 fields populated from real-time data.
    """
    state: Dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
    }

    # Domain 1: Plan & Subscription
    state.update(_collect_plan_subscription(db, company_id))

    # Domain 2: System Health
    state.update(_collect_system_health(db, company_id))

    # Domain 3: Ticket Volume
    state.update(_collect_ticket_volume(db, company_id))

    # Domain 4: Agent Pool
    state.update(_collect_agent_pool(db, company_id))

    # Domain 5: Training (Agent Lightning)
    state.update(_collect_training(db, company_id))

    # Domain 6: Drift & Quality
    state.update(_collect_drift_quality(db, company_id))

    # Domain 7: Errors
    state.update(_collect_errors(db, company_id))

    return state


# ══════════════════════════════════════════════════════════════════
# SNAPSHOT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_snapshot(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    tick_type: str = "periodic",
    tick_number: int = 1,
) -> JarvisAwarenessSnapshot:
    """Create a new JarvisAwarenessSnapshot from collected state.

    Maps GROUP 14 fields from the state dict to the ORM model columns.
    Also stores the complete raw state in raw_state_json for recovery.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        state: Collected awareness state dict.
        tick_type: periodic, on_change, manual, or emergency.
        tick_number: Monotonically increasing tick counter.

    Returns:
        JarvisAwarenessSnapshot ORM instance.
    """
    # Channel health → JSON
    channel_health = state.get("channel_health", {})
    if isinstance(channel_health, dict):
        channel_health_json = json.dumps(channel_health)
    else:
        channel_health_json = json.dumps({})

    # Active alerts → JSON
    active_alerts = state.get("active_alerts", [])
    if isinstance(active_alerts, list):
        active_alerts_json = json.dumps(active_alerts)
        active_alerts_count = len(active_alerts)
    else:
        active_alerts_json = "[]"
        active_alerts_count = 0

    # Quality alerts → JSON
    quality_alerts = state.get("quality_alerts", [])
    quality_alerts_json = json.dumps(quality_alerts) if isinstance(quality_alerts, list) else "[]"

    # Last 5 errors → JSON
    last_5_errors = state.get("last_5_errors", [])
    last_5_errors_json = json.dumps(last_5_errors) if isinstance(last_5_errors, list) else "[]"

    # Raw state → JSON (complete dump for crash recovery)
    raw_state_json = json.dumps(state, default=str)

    snapshot = JarvisAwarenessSnapshot(
        session_id=session_id,
        company_id=company_id,
        snapshot_type=tick_type,
        tick_number=tick_number,
        current_plan=state.get("current_plan"),
        plan_usage_today=state.get("plan_usage_today"),
        subscription_status=state.get("subscription_status"),
        days_until_renewal=state.get("days_until_renewal"),
        system_health=state.get("system_health", "unknown"),
        channel_health_json=channel_health_json,
        active_alerts_count=active_alerts_count,
        active_alerts_json=active_alerts_json,
        ticket_volume_today=state.get("ticket_volume_today", 0),
        ticket_volume_avg=state.get("ticket_volume_avg"),
        ticket_volume_spike=state.get("ticket_volume_spike", False),
        active_agents=state.get("active_agents", 0),
        agent_pool_capacity=state.get("agent_pool_capacity", 0),
        agent_pool_utilization=state.get("agent_pool_utilization"),
        training_running=state.get("training_running", False),
        training_mistake_count=state.get("training_mistake_count", 0),
        training_model_version=state.get("training_model_version"),
        drift_status=state.get("drift_status", "none"),
        drift_score=state.get("drift_score"),
        quality_score=state.get("quality_score"),
        quality_alerts_json=quality_alerts_json,
        last_5_errors_json=last_5_errors_json,
        raw_state_json=raw_state_json,
    )
    db.add(snapshot)
    db.flush()

    logger.debug(
        "snapshot_created: id=%s, session=%s, tick=%d, type=%s, health=%s",
        snapshot.id, session_id, tick_number, tick_type,
        state.get("system_health", "unknown"),
    )

    return snapshot


def get_latest_snapshot(
    db: Session,
    session_id: str,
    company_id: str,
) -> Optional[JarvisAwarenessSnapshot]:
    """Get the most recent awareness snapshot for a session.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.

    Returns:
        JarvisAwarenessSnapshot or None.
    """
    return (
        db.query(JarvisAwarenessSnapshot)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
        .first()
    )


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


# ══════════════════════════════════════════════════════════════════
# ALERT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_alert(
    db: Session,
    session_id: str,
    company_id: str,
    alert_type: str,
    severity: str,
    category: str,
    title: str,
    message: str,
    details_json: str = "{}",
    action_required: bool = False,
    action_url: Optional[str] = None,
    ttl_seconds: int = 0,
    related_snapshot_id: Optional[str] = None,
    dedup_key: Optional[str] = None,
) -> Optional[JarvisProactiveAlert]:
    """Create a proactive alert, with optional deduplication.

    If a dedup_key is provided and an active alert with the same
    dedup_key (stored in details_json) already exists, no new alert
    is created. This prevents alert storms.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        alert_type: Type of alert (e.g., ticket_volume_spike).
        severity: info, warning, critical, emergency.
        category: Alert category (e.g., system_health).
        title: Short alert title.
        message: Detailed alert message.
        details_json: JSON string with structured details.
        action_required: Whether user action is needed.
        action_url: Deep link to dashboard section.
        ttl_seconds: Time-to-live in seconds (0 = no expiry).
        related_snapshot_id: ID of the triggering snapshot.
        dedup_key: Optional deduplication key.

    Returns:
        JarvisProactiveAlert or None if deduplicated.
    """
    # Deduplication check
    if dedup_key:
        existing = (
            db.query(JarvisProactiveAlert)
            .filter(
                JarvisProactiveAlert.session_id == session_id,
                JarvisProactiveAlert.company_id == company_id,
                JarvisProactiveAlert.alert_type == alert_type,
                JarvisProactiveAlert.status == "active",
            )
            .first()
        )
        if existing:
            # Check if details contain same dedup_key
            try:
                existing_details = _safe_parse_json(existing.details_json)
                if existing_details.get("_dedup_key") == dedup_key:
                    logger.debug(
                        "alert_deduped: type=%s, key=%s, session=%s",
                        alert_type, dedup_key, session_id,
                    )
                    return None  # Already have an active alert for this
            except Exception:
                pass

    # Add dedup_key to details
    try:
        details = _safe_parse_json(details_json)
        details["_dedup_key"] = dedup_key or ""
        details_json = json.dumps(details)
    except Exception:
        pass

    # Determine TTL based on severity if not specified
    if ttl_seconds == 0:
        ttl_seconds = {
            "info": ALERT_TTL_INFO,
            "warning": ALERT_TTL_WARNING,
            "critical": ALERT_TTL_CRITICAL,
            "emergency": ALERT_TTL_EMERGENCY,
        }.get(severity, ALERT_TTL_INFO)

    alert = JarvisProactiveAlert(
        session_id=session_id,
        company_id=company_id,
        alert_type=alert_type,
        severity=severity,
        category=category,
        title=title,
        message=message,
        details_json=details_json,
        action_required=action_required,
        action_url=action_url,
        ttl_seconds=ttl_seconds,
        related_snapshot_id=related_snapshot_id,
        status="active",
    )
    db.add(alert)
    db.flush()

    logger.info(
        "alert_created: id=%s, type=%s, severity=%s, category=%s, "
        "session=%s, action_required=%s",
        alert.id, alert_type, severity, category, session_id, action_required,
    )

    return alert


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


# ══════════════════════════════════════════════════════════════════
# PRUNING: Prevent unbounded growth
# ══════════════════════════════════════════════════════════════════


def prune_old_snapshots(
    db: Session,
    session_id: str,
    company_id: str,
    max_keep: int = MAX_SNAPSHOTS_PER_SESSION,
) -> int:
    """Prune old snapshots to prevent unbounded DB growth.

    Keeps the most recent `max_keep` snapshots per session.
    Emergency and on_change snapshots are always preserved.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        max_keep: Maximum snapshots to keep per session.

    Returns:
        Number of snapshots pruned.
    """
    # Count total snapshots for this session
    total = (
        db.query(func.count(JarvisAwarenessSnapshot.id))
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .scalar()
    )

    if total <= max_keep:
        return 0

    # Find IDs to keep (most recent + emergency/on_change)
    keep_ids = (
        db.query(JarvisAwarenessSnapshot.id)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
        .limit(max_keep)
        .all()
    )
    keep_id_set = {row[0] for row in keep_ids}

    # Also keep emergency and on_change snapshots
    special_ids = (
        db.query(JarvisAwarenessSnapshot.id)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
            JarvisAwarenessSnapshot.snapshot_type.in_(["emergency", "on_change"]),
        )
        .all()
    )
    keep_id_set.update(row[0] for row in special_ids)

    # Delete snapshots not in keep set
    pruned = (
        db.query(JarvisAwarenessSnapshot)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
            JarvisAwarenessSnapshot.id.notin_(keep_id_set),
        )
        .limit(SNAPSHOT_PRUNE_BATCH)
        .delete(synchronize_session="fetch")
    )
    db.flush()

    if pruned > 0:
        logger.info(
            "snapshots_pruned: session=%s, pruned=%d, kept=%d",
            session_id, pruned, len(keep_id_set),
        )

    return pruned


def prune_expired_alerts(
    db: Session,
    session_id: str,
    company_id: str,
) -> int:
    """Mark expired alerts (past their TTL) as expired.

    Only processes active alerts with non-zero TTL.
    Emergency alerts (TTL=0) never expire automatically.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.

    Returns:
        Number of alerts expired.
    """
    now = datetime.now(timezone.utc)

    # Find active alerts with TTL that have expired
    active_alerts = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status == "active",
            JarvisProactiveAlert.ttl_seconds > 0,
        )
        .all()
    )

    expired_count = 0
    for alert in active_alerts:
        if alert.created_at:
            expires_at = alert.created_at + timedelta(seconds=alert.ttl_seconds)
            if now > expires_at:
                alert.status = "expired"
                alert.updated_at = now
                expired_count += 1

    if expired_count > 0:
        db.flush()
        logger.info(
            "alerts_expired: session=%s, count=%d",
            session_id, expired_count,
        )

    return expired_count


# ══════════════════════════════════════════════════════════════════
# DELTA DETECTION: What changed since last tick?
# ══════════════════════════════════════════════════════════════════


def compute_awareness_delta(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute the delta between current and previous awareness state.

    Detects significant changes that might require alerts or
    on_change snapshots. A change is "significant" if it crosses
    a threshold or changes a discrete status value.

    Args:
        current: Current awareness state dict.
        previous: Previous awareness state dict (None if first tick).

    Returns:
        Dict with:
          - changed_fields: Dict of {field: {"from": old, "to": new}}
          - has_significant_changes: bool
          - new_alerts: List of alert-worthy changes
          - recovered: List of fields that improved
    """
    if previous is None:
        return {
            "changed_fields": {},
            "has_significant_changes": True,  # First tick is always significant
            "new_alerts": [],
            "recovered": [],
            "is_first_tick": True,
        }

    delta: Dict[str, Any] = {
        "changed_fields": {},
        "has_significant_changes": False,
        "new_alerts": [],
        "recovered": [],
        "is_first_tick": False,
    }

    # Fields to check for discrete status changes
    status_fields = [
        "system_health", "subscription_status", "drift_status",
    ]

    # Fields to check for threshold crossings
    threshold_fields = {
        "plan_usage_today": [PLAN_USAGE_WARN_THRESHOLD, PLAN_USAGE_CRITICAL_THRESHOLD],
        "agent_pool_utilization": [UTILIZATION_WARN_THRESHOLD, UTILIZATION_CRITICAL_THRESHOLD],
        "quality_score": [QUALITY_CRITICAL_THRESHOLD, QUALITY_WARN_THRESHOLD],  # Reversed: lower = worse
        "drift_score": [DRIFT_WARN_THRESHOLD, DRIFT_CRITICAL_THRESHOLD],
    }

    # Check discrete status changes
    for field in status_fields:
        old_val = previous.get(field)
        new_val = current.get(field)
        if old_val != new_val and old_val is not None and new_val is not None:
            delta["changed_fields"][field] = {"from": old_val, "to": new_val}

            # System health changes are always significant
            if field == "system_health":
                severity_order = {"healthy": 0, "degraded": 1, "critical": 2, "down": 3}
                old_sev = severity_order.get(old_val, 0)
                new_sev = severity_order.get(new_val, 0)
                if new_sev > old_sev:
                    delta["has_significant_changes"] = True
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })
                elif new_sev < old_sev:
                    delta["recovered"].append({
                        "field": field,
                        "change": "improved",
                        "from": old_val,
                        "to": new_val,
                    })

            # Subscription status changes
            if field == "subscription_status":
                delta["has_significant_changes"] = True
                if new_val in ("past_due", "cancelled"):
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })

            # Drift status changes
            if field == "drift_status":
                severity_order = {"none": 0, "slight": 1, "moderate": 2, "severe": 3}
                old_sev = severity_order.get(old_val, 0)
                new_sev = severity_order.get(new_val, 0)
                if new_sev > old_sev:
                    delta["has_significant_changes"] = True
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })
                elif new_sev < old_sev:
                    delta["recovered"].append({
                        "field": field,
                        "change": "improved",
                        "from": old_val,
                        "to": new_val,
                    })

    # Check threshold crossings
    for field, thresholds in threshold_fields.items():
        old_val = previous.get(field)
        new_val = current.get(field)

        if old_val is None or new_val is None:
            continue

        try:
            old_float = float(old_val)
            new_float = float(new_val)
        except (ValueError, TypeError):
            continue

        # For quality_score, lower is worse (reversed thresholds)
        if field == "quality_score":
            # thresholds = [QUALITY_CRITICAL_THRESHOLD, QUALITY_WARN_THRESHOLD]
            # = [0.50, 0.70] — crit first, warn second for quality
            crit_thresh, warn_thresh = thresholds  # crit=0.50, warn=0.70
            if new_float < crit_thresh and old_float >= crit_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_critical",
                    "from": old_float,
                    "to": new_float,
                    "threshold": crit_thresh,
                })
            elif new_float < warn_thresh and old_float >= warn_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_warning",
                    "from": old_float,
                    "to": new_float,
                    "threshold": warn_thresh,
                })
            elif new_float >= warn_thresh and old_float < warn_thresh:
                delta["recovered"].append({
                    "field": field,
                    "change": "recovered_above_warning",
                    "from": old_float,
                    "to": new_float,
                })
        else:
            warn_thresh, crit_thresh = thresholds  # warn < crit for others
            if new_float >= crit_thresh and old_float < crit_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_critical",
                    "from": old_float,
                    "to": new_float,
                    "threshold": crit_thresh,
                })
            elif new_float >= warn_thresh and old_float < warn_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_warning",
                    "from": old_float,
                    "to": new_float,
                    "threshold": warn_thresh,
                })
            elif new_float < warn_thresh and old_float >= warn_thresh:
                delta["recovered"].append({
                    "field": field,
                    "change": "recovered_below_warning",
                    "from": old_float,
                    "to": new_float,
                })

    # Check ticket volume spike
    old_spike = previous.get("ticket_volume_spike", False)
    new_spike = current.get("ticket_volume_spike", False)
    if new_spike and not old_spike:
        delta["has_significant_changes"] = True
        delta["new_alerts"].append({
            "field": "ticket_volume_spike",
            "change": "spike_detected",
            "today": current.get("ticket_volume_today"),
            "avg": current.get("ticket_volume_avg"),
        })

    return delta


# ══════════════════════════════════════════════════════════════════
# DOMAIN COLLECTORS: Read real-time data from each domain
# ══════════════════════════════════════════════════════════════════


def _collect_plan_subscription(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 1: Plan & Subscription.

    Reads subscription status, plan usage, and renewal info.
    """
    result = {
        "current_plan": "mini_parwa",
        "plan_usage_today": 0.0,
        "subscription_status": "active",
        "days_until_renewal": 30,
    }

    try:
        from database.models.core import Subscription
        subscription = (
            db.query(Subscription)
            .filter(Subscription.company_id == company_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if subscription:
            result["current_plan"] = subscription.plan_type or "mini_parwa"
            result["subscription_status"] = subscription.status or "active"
            if subscription.usage_percentage is not None:
                result["plan_usage_today"] = float(subscription.usage_percentage)
            if subscription.renewal_date:
                days_left = (subscription.renewal_date - datetime.now(timezone.utc).date()).days
                result["days_until_renewal"] = max(0, days_left)
    except Exception:
        logger.debug("plan_subscription_collection_failed: company=%s", company_id)

    return result


def _collect_system_health(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 2: System Health.

    Reads overall system health and per-channel health.
    """
    result = {
        "system_health": "healthy",
        "channel_health": {},
        "active_alerts": [],
    }

    try:
        from database.models.core import EmergencyState
        emergency = (
            db.query(EmergencyState)
            .filter(EmergencyState.company_id == company_id)
            .order_by(EmergencyState.created_at.desc())
            .first()
        )
        if emergency:
            if emergency.is_paused:
                result["system_health"] = "critical"
            elif emergency.paused_channels:
                result["system_health"] = "degraded"
                channels = emergency.paused_channels.split(",") if isinstance(emergency.paused_channels, str) else []
                for ch in channels:
                    result["channel_health"][ch.strip()] = "paused"
    except Exception:
        logger.debug("system_health_collection_failed: company=%s", company_id)

    # Per-channel health from recent delivery failures
    try:
        from database.models.tickets import Ticket
        from sqlalchemy import case

        # Check for recent delivery failures per channel
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        channel_stats = (
            db.query(
                Ticket.channel,
                func.count(Ticket.id).label("total"),
                func.sum(case(
                    (Ticket.status == "delivery_failed", 1),
                    else_=0,
                )).label("failed"),
            )
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= recent_cutoff,
            )
            .group_by(Ticket.channel)
            .all()
        )

        for ch, total, failed in channel_stats:
            if total and total > 0:
                failure_rate = (failed or 0) / total
                if failure_rate > 0.5:
                    result["channel_health"][ch] = "down"
                    result["system_health"] = "degraded"
                elif failure_rate > 0.2:
                    result["channel_health"][ch] = "degraded"
                else:
                    result["channel_health"][ch] = "healthy"
    except Exception:
        logger.debug("channel_health_collection_failed: company=%s", company_id)

    return result


def _collect_ticket_volume(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 3: Ticket Volume.

    Reads today's ticket count, 7-day average, and detects spikes.
    """
    result = {
        "ticket_volume_today": 0,
        "ticket_volume_avg": 0.0,
        "ticket_volume_spike": False,
    }

    try:
        from database.models.tickets import Ticket

        # Today's count
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        today_count = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= today_start,
            )
            .scalar()
        )
        result["ticket_volume_today"] = today_count or 0

        # 7-day average (excluding today)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        avg_result = (
            db.query(func.count(Ticket.id) / 7.0)
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= seven_days_ago,
                Ticket.created_at < today_start,
            )
            .scalar()
        )
        result["ticket_volume_avg"] = float(avg_result or 0)

        # Spike detection
        if result["ticket_volume_avg"] > 0:
            spike_ratio = result["ticket_volume_today"] / result["ticket_volume_avg"]
            result["ticket_volume_spike"] = spike_ratio >= SPIKE_MULTIPLIER

    except Exception:
        logger.debug("ticket_volume_collection_failed: company=%s", company_id)

    return result


def _collect_agent_pool(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 4: Agent Pool.

    Reads active agent count, capacity, and utilization.
    """
    result = {
        "active_agents": 0,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 0.0,
    }

    try:
        from database.models.core import VariantInstance
        instance = (
            db.query(VariantInstance)
            .filter(VariantInstance.company_id == company_id)
            .order_by(VariantInstance.created_at.desc())
            .first()
        )
        if instance:
            result["active_agents"] = getattr(instance, "active_agents", 0) or 0
            result["agent_pool_capacity"] = getattr(instance, "agent_capacity", 5) or 5
            if result["agent_pool_capacity"] > 0:
                result["agent_pool_utilization"] = round(
                    (result["active_agents"] / result["agent_pool_capacity"]) * 100, 2
                )
    except Exception:
        logger.debug("agent_pool_collection_failed: company=%s", company_id)

    return result


def _collect_training(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 5: Training (Agent Lightning).

    Reads training state, mistake count, and model version.
    """
    result = {
        "training_running": False,
        "training_mistake_count": 0,
        "training_model_version": "",
    }

    try:
        from database.models.core import TrainingJob
        job = (
            db.query(TrainingJob)
            .filter(TrainingJob.company_id == company_id)
            .order_by(TrainingJob.created_at.desc())
            .first()
        )
        if job:
            result["training_running"] = getattr(job, "status", "") == "running"
            result["training_mistake_count"] = getattr(job, "mistake_count", 0) or 0
            result["training_model_version"] = getattr(job, "model_version", "") or ""
    except Exception:
        logger.debug("training_collection_failed: company=%s", company_id)

    return result


def _collect_drift_quality(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 6: Drift & Quality.

    Reads model drift status, drift score, quality score, and quality alerts.
    """
    result = {
        "drift_status": "none",
        "drift_score": 0.0,
        "quality_score": 0.0,
        "quality_alerts": [],
    }

    try:
        from database.models.core import QualityMetric
        metric = (
            db.query(QualityMetric)
            .filter(QualityMetric.company_id == company_id)
            .order_by(QualityMetric.created_at.desc())
            .first()
        )
        if metric:
            result["drift_status"] = getattr(metric, "drift_status", "none") or "none"
            result["drift_score"] = float(getattr(metric, "drift_score", 0) or 0)
            result["quality_score"] = float(getattr(metric, "quality_score", 0) or 0)
    except Exception:
        logger.debug("drift_quality_collection_failed: company=%s", company_id)

    return result


def _collect_errors(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 7: Errors.

    Reads last 5 errors from the error log.
    """
    result = {
        "last_5_errors": [],
    }

    try:
        from database.models.core import ErrorLog
        errors = (
            db.query(ErrorLog)
            .filter(ErrorLog.company_id == company_id)
            .order_by(ErrorLog.created_at.desc())
            .limit(5)
            .all()
        )
        for err in errors:
            result["last_5_errors"].append({
                "error": getattr(err, "error_message", ""),
                "node": getattr(err, "node_name", ""),
                "timestamp": err.created_at.isoformat() if err.created_at else "",
                "tenant_id": company_id,
            })
    except Exception:
        logger.debug("errors_collection_failed: company=%s", company_id)

    return result


# ══════════════════════════════════════════════════════════════════
# RULE CHECKS: Generate alerts from state + delta
# ══════════════════════════════════════════════════════════════════


def _run_rule_checks(
    db: Session,
    session_id: str,
    company_id: str,
    current_state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
) -> List[JarvisProactiveAlert]:
    """Run all rule checks against current state and create alerts.

    Each rule is independently wrapped in try/except (BC-008).
    A rule failure does NOT prevent other rules from running.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        current_state: Current awareness state.
        delta: Delta from previous state.
        snapshot_id: ID of the snapshot that triggered this check.

    Returns:
        List of newly created alerts.
    """
    alerts: List[JarvisProactiveAlert] = []

    # Rule 1: System Health
    try:
        alert = _check_system_health(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("system_health_rule_failed: session=%s", session_id)

    # Rule 2: Ticket Volume Spike
    try:
        alert = _check_ticket_volume_spike(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("ticket_volume_rule_failed: session=%s", session_id)

    # Rule 3: Agent Pool Utilization
    try:
        alert = _check_agent_pool(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("agent_pool_rule_failed: session=%s", session_id)

    # Rule 4: Quality Score Drop
    try:
        alert = _check_quality(db, session_id, company_id, current_state, delta, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("quality_rule_failed: session=%s", session_id)

    # Rule 5: Model Drift
    try:
        alert = _check_drift(db, session_id, company_id, current_state, delta, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("drift_rule_failed: session=%s", session_id)

    # Rule 6: Plan Usage
    try:
        alert = _check_plan_usage(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("plan_usage_rule_failed: session=%s", session_id)

    # Rule 7: Subscription Status
    try:
        alert = _check_subscription(db, session_id, company_id, current_state, delta, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("subscription_rule_failed: session=%s", session_id)

    # Rule 8: Renewal Warning
    try:
        alert = _check_renewal(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("renewal_rule_failed: session=%s", session_id)

    # Rule 9: Error Rate
    try:
        alert = _check_error_rate(db, session_id, company_id, current_state, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("error_rate_rule_failed: session=%s", session_id)

    return alerts


def _check_system_health(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 1: System Health Check.

    Alerts when system health is degraded, critical, or down.
    """
    health = state.get("system_health", "healthy")
    if health == "healthy":
        return None

    severity_map = {
        "degraded": "warning",
        "critical": "critical",
        "down": "emergency",
    }
    severity = severity_map.get(health, "info")

    channel_health = state.get("channel_health", {})
    unhealthy_channels = [ch for ch, status in channel_health.items() if status != "healthy"]

    message = f"System health is {health}"
    if unhealthy_channels:
        message += f". Affected channels: {', '.join(unhealthy_channels)}"

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="system_health_degraded",
        severity=severity,
        category="system_health",
        title=f"System Health: {health.title()}",
        message=message,
        details_json=json.dumps({
            "system_health": health,
            "unhealthy_channels": unhealthy_channels,
            "channel_health": channel_health,
        }),
        action_required=health in ("critical", "down"),
        action_url="/dashboard/settings?tab=system-health",
        related_snapshot_id=snapshot_id,
        dedup_key=f"system_health_{health}",
    )


def _check_ticket_volume_spike(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 2: Ticket Volume Spike.

    Alerts when today's volume exceeds 2x the 7-day average.
    """
    if not state.get("ticket_volume_spike", False):
        return None

    today = state.get("ticket_volume_today", 0)
    avg = state.get("ticket_volume_avg", 0)
    ratio = today / avg if avg > 0 else 0

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="ticket_volume_spike",
        severity="warning",
        category="ticket_volume",
        title="Ticket Volume Spike Detected",
        message=f"Today's ticket volume ({today}) is {ratio:.1f}x the 7-day average ({avg:.0f}).",
        details_json=json.dumps({
            "ticket_volume_today": today,
            "ticket_volume_avg": avg,
            "spike_ratio": round(ratio, 2),
            "spike_multiplier_threshold": SPIKE_MULTIPLIER,
        }),
        action_required=True,
        action_url="/dashboard/tickets?filter=today",
        related_snapshot_id=snapshot_id,
        dedup_key="ticket_volume_spike",
    )


def _check_agent_pool(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 3: Agent Pool Utilization.

    Alerts when utilization exceeds warning (80%) or critical (95%) thresholds.
    """
    utilization = state.get("agent_pool_utilization", 0)
    if utilization is None:
        return None

    try:
        util_float = float(utilization)
    except (ValueError, TypeError):
        return None

    if util_float < UTILIZATION_WARN_THRESHOLD:
        return None

    severity = "critical" if util_float >= UTILIZATION_CRITICAL_THRESHOLD else "warning"
    active = state.get("active_agents", 0)
    capacity = state.get("agent_pool_capacity", 0)

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="agent_pool_utilization_high",
        severity=severity,
        category="agent_pool",
        title=f"Agent Pool Utilization: {util_float:.0f}%",
        message=(
            f"Agent pool is at {util_float:.0f}% utilization "
            f"({active}/{capacity} agents active). "
            + ("Consider upgrading your plan for more capacity." if severity == "critical"
               else "Monitor for potential capacity issues.")
        ),
        details_json=json.dumps({
            "utilization": util_float,
            "active_agents": active,
            "capacity": capacity,
            "warn_threshold": UTILIZATION_WARN_THRESHOLD,
            "critical_threshold": UTILIZATION_CRITICAL_THRESHOLD,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/settings?tab=plan",
        related_snapshot_id=snapshot_id,
        dedup_key="agent_pool_utilization",
    )


def _check_quality(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 4: Quality Score Drop.

    Alerts when quality score drops below warning (0.70) or critical (0.50).
    """
    quality = state.get("quality_score")
    if quality is None:
        return None

    try:
        q_float = float(quality)
    except (ValueError, TypeError):
        return None

    if q_float >= QUALITY_WARN_THRESHOLD:
        return None

    severity = "critical" if q_float < QUALITY_CRITICAL_THRESHOLD else "warning"

    # Check if this is a new drop (delta detection)
    quality_drops = [a for a in delta.get("new_alerts", []) if a.get("field") == "quality_score"]
    is_new_drop = len(quality_drops) > 0

    message = f"Response quality score has dropped to {q_float:.2f}"
    if is_new_drop:
        message += " (new drop detected)"
    message += ". This may affect customer satisfaction."

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="quality_drop",
        severity=severity,
        category="quality",
        title=f"Quality Score: {q_float:.2f}",
        message=message,
        details_json=json.dumps({
            "quality_score": q_float,
            "warn_threshold": QUALITY_WARN_THRESHOLD,
            "critical_threshold": QUALITY_CRITICAL_THRESHOLD,
            "is_new_drop": is_new_drop,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/quality",
        related_snapshot_id=snapshot_id,
        dedup_key="quality_score_drop",
    )


def _check_drift(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 5: Model Drift.

    Alerts when drift score exceeds warning (0.30) or critical (0.60).
    """
    drift_score = state.get("drift_score")
    drift_status = state.get("drift_status", "none")

    if drift_score is None:
        return None

    try:
        d_float = float(drift_score)
    except (ValueError, TypeError):
        return None

    if d_float < DRIFT_WARN_THRESHOLD:
        return None

    severity = "critical" if d_float >= DRIFT_CRITICAL_THRESHOLD else "warning"

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="drift_detected",
        severity=severity,
        category="drift",
        title=f"Model Drift: {drift_status.title()} ({d_float:.2f})",
        message=(
            f"Model drift has been detected (score: {d_float:.2f}, status: {drift_status}). "
            "Consider triggering Agent Lightning training to correct the drift."
        ),
        details_json=json.dumps({
            "drift_score": d_float,
            "drift_status": drift_status,
            "warn_threshold": DRIFT_WARN_THRESHOLD,
            "critical_threshold": DRIFT_CRITICAL_THRESHOLD,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/training",
        related_snapshot_id=snapshot_id,
        dedup_key="drift_detected",
    )


def _check_plan_usage(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 6: Plan Usage.

    Alerts when plan usage exceeds warning (80%) or critical (95%).
    """
    usage = state.get("plan_usage_today")
    if usage is None:
        return None

    try:
        u_float = float(usage)
    except (ValueError, TypeError):
        return None

    if u_float < PLAN_USAGE_WARN_THRESHOLD:
        return None

    severity = "critical" if u_float >= PLAN_USAGE_CRITICAL_THRESHOLD else "warning"
    plan = state.get("current_plan", "unknown")

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="plan_usage_high",
        severity=severity,
        category="billing",
        title=f"Plan Usage: {u_float:.0f}%",
        message=(
            f"Your {plan} plan usage is at {u_float:.0f}% today. "
            + ("You may hit your daily limit soon." if severity == "warning"
               else "You are about to hit your daily limit. Consider upgrading.")
        ),
        details_json=json.dumps({
            "plan_usage_today": u_float,
            "current_plan": plan,
            "warn_threshold": PLAN_USAGE_WARN_THRESHOLD,
            "critical_threshold": PLAN_USAGE_CRITICAL_THRESHOLD,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key="plan_usage_high",
    )


def _check_subscription(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 7: Subscription Status.

    Alerts when subscription status changes to past_due or cancelled.
    """
    sub_status = state.get("subscription_status", "active")
    if sub_status == "active" or sub_status == "trial":
        return None

    # Only alert on delta (status change) to avoid spam
    sub_changes = [a for a in delta.get("new_alerts", []) if a.get("field") == "subscription_status"]
    if not sub_changes and delta.get("is_first_tick") is not True:
        # If not first tick and no delta change, don't re-alert
        return None

    severity = "critical" if sub_status == "past_due" else "warning"

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="subscription_status_change",
        severity=severity,
        category="billing",
        title=f"Subscription: {sub_status.title()}",
        message=f"Your subscription status has changed to '{sub_status}'. Please update your payment method.",
        details_json=json.dumps({
            "subscription_status": sub_status,
            "plan": state.get("current_plan", "unknown"),
        }),
        action_required=True,
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key=f"subscription_{sub_status}",
    )


def _check_renewal(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 8: Renewal Warning.

    Alerts when renewal is approaching (7 days = info, 3 days = warning).
    """
    days = state.get("days_until_renewal")
    if days is None:
        return None

    try:
        days_int = int(days)
    except (ValueError, TypeError):
        return None

    if days_int > RENEWAL_INFO_THRESHOLD:
        return None

    if days_int <= RENEWAL_WARN_THRESHOLD:
        severity = "warning"
    else:
        severity = "info"

    plan = state.get("current_plan", "unknown")

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="renewal_approaching",
        severity=severity,
        category="billing",
        title=f"Renewal in {days_int} Days",
        message=f"Your {plan} plan renews in {days_int} days. Please ensure your payment method is up to date.",
        details_json=json.dumps({
            "days_until_renewal": days_int,
            "current_plan": plan,
        }),
        action_required=days_int <= RENEWAL_WARN_THRESHOLD,
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key="renewal_approaching",
    )


def _check_error_rate(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 9: Error Rate.

    Alerts when there are 3+ recent errors.
    """
    errors = state.get("last_5_errors", [])
    if not isinstance(errors, list) or len(errors) < 3:
        return None

    severity = "critical" if len(errors) >= 5 else "warning"

    error_summaries = [e.get("error", "Unknown")[:50] for e in errors]

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="error_rate_high",
        severity=severity,
        category="system_health",
        title=f"{len(errors)} Recent Errors Detected",
        message=(
            f"{len(errors)} errors have been detected in the last hour. "
            "This may indicate a system issue that needs attention."
        ),
        details_json=json.dumps({
            "error_count": len(errors),
            "error_summaries": error_summaries,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/logs",
        related_snapshot_id=snapshot_id,
        dedup_key="error_rate_high",
    )


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: Optional[str]) -> Dict[str, Any]:
    """Safely parse JSON string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
