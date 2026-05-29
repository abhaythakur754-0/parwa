"""
PARWA Activity Store Service — Jarvis Awareness for Non-Agentic Parts

This is the service layer for the ActivityLog model. It provides:
  - log_activity():    Record any action in the system
  - query_activities(): Structured querying with filters
  - get_recent():      Get recent N activities for a tenant
  - get_summary():     Aggregated activity summary for a time range
  - get_trends():      Activity trends over time (for Jarvis reasoning)
  - prune_expired():   TTL-based cleanup of old entries

This is what Jarvis reads to gain awareness of non-agentic parts.
For agentic parts, Jarvis asks variant agents directly via variant_bridge.

Design Principle:
  The Activity Store is NOT a chatbot API. It does NOT answer questions.
  It STORES actions and lets Jarvis READ them. Jarvis then REASONS about
  what it read, using the ZAI LLM. This is the key differentiator —
  Jarvis thinks about what happened, it doesn't just query a database.

Usage from other services:
  from app.services.activity_store import log_activity

  # User clicked upgrade button
  log_activity(
      company_id="comp_123",
      actor_type="user",
      actor_id="user_456",
      actor_name="admin@company.com",
      category="billing",
      action="upgrade_button_clicked",
      label="User clicked 'Upgrade to PARWA' on billing page",
      entity_type="subscription",
      entity_id="sub_789",
      importance="high",
      details={
          "from_plan": "mini_parwa",
          "to_plan": "parwa",
          "button_location": "billing_page_upgrade_cta",
      },
  )

BC-001: company_id first parameter on all public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("activity_store")

__all__ = [
    # Write
    "log_activity",
    "log_batch",
    # Read
    "query_activities",
    "get_recent",
    "get_summary",
    "get_trends",
    "get_user_activity",
    "get_entity_history",
    # Awareness helpers (used by Jarvis awareness engine)
    "get_awareness_context",
    "get_billing_awareness",
    "get_user_action_awareness",
    "get_system_event_awareness",
    # Pruning
    "prune_expired",
]


# ══════════════════════════════════════════════════════════════════
# WRITE: Log any action in the system
# ══════════════════════════════════════════════════════════════════


def log_activity(
    db: Session,
    company_id: str,
    category: str,
    action: str,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    label: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    session_id: Optional[str] = None,
    route: Optional[str] = None,
    method: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    importance: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> Optional[Any]:
    """Record an activity in the Activity Store.

    This is the primary write method. Every non-agentic action in the
    system should call this to record what happened.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001 tenant scoping.
        category: Event category (billing, user_action, system, etc.).
        action: Specific action that occurred.
        actor_type: Who caused the action (user, system, agent, jarvis, etc.).
        actor_id: ID of the actor.
        actor_name: Human-readable name of the actor.
        label: Human-readable description of what happened.
        entity_type: Type of entity affected (ticket, subscription, etc.).
        entity_id: ID of the entity affected.
        session_id: CC session ID if action happened during a session.
        route: API route or page URL.
        method: HTTP method for API calls.
        details: Flexible JSON details dict.
        importance: How important this event is (auto-set if not provided).
        occurred_at: When the action happened (defaults to now).

    Returns:
        ActivityLog instance or None on failure (BC-008: never crash).
    """
    try:
        from database.models.activity_log import (
            ActivityLog,
            IMPORTANCE_TTL_DAYS,
            CATEGORY_IMPORTANCE_DEFAULTS,
        )

        # Auto-set importance from category if not provided
        effective_importance = importance or CATEGORY_IMPORTANCE_DEFAULTS.get(
            category, "info"
        )

        # Calculate expires_at based on importance
        expires_at = None
        ttl_days = IMPORTANCE_TTL_DAYS.get(effective_importance)
        if ttl_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        # Serialize details
        details_json = json.dumps(details or {}, default=str)

        entry = ActivityLog(
            company_id=company_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            category=category,
            action=action,
            label=label,
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id,
            route=route,
            method=method,
            details_json=details_json,
            importance=effective_importance,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        db.add(entry)
        db.flush()

        logger.debug(
            "activity_logged: company=%s, category=%s, action=%s, "
            "actor=%s/%s, importance=%s",
            company_id, category, action, actor_type, actor_id,
            effective_importance,
        )

        return entry

    except Exception as e:
        logger.warning(
            "activity_log_failed: company=%s, category=%s, action=%s, error=%s",
            company_id, category, action, str(e)[:200],
        )
        return None


def log_batch(
    db: Session,
    activities: List[Dict[str, Any]],
) -> int:
    """Log multiple activities in a single transaction.

    Args:
        db: SQLAlchemy session.
        activities: List of activity dicts with same keys as log_activity().

    Returns:
        Number of activities successfully logged.
    """
    count = 0
    for act in activities:
        result = log_activity(db=db, **act)
        if result is not None:
            count += 1
    return count


# ══════════════════════════════════════════════════════════════════
# READ: Query activities for awareness
# ══════════════════════════════════════════════════════════════════


def query_activities(
    db: Session,
    company_id: str,
    category: Optional[str] = None,
    action: Optional[str] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    session_id: Optional[str] = None,
    importance: Optional[str] = None,
    importance_min: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "desc",
) -> Tuple[List[Any], int]:
    """Query activities with structured filters.

    All queries are tenant-scoped by company_id (BC-001).

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for tenant scoping.
        category: Filter by category.
        action: Filter by action (supports LIKE pattern).
        actor_type: Filter by actor type.
        actor_id: Filter by actor ID.
        entity_type: Filter by entity type.
        entity_id: Filter by entity ID.
        session_id: Filter by CC session ID.
        importance: Filter by exact importance.
        importance_min: Filter by minimum importance level.
        since: Only activities after this timestamp.
        until: Only activities before this timestamp.
        limit: Max results to return.
        offset: Pagination offset.
        order: Sort order (desc = newest first, asc = oldest first).

    Returns:
        Tuple of (activities_list, total_count).
    """
    try:
        from database.models.activity_log import ActivityLog

        # Importance hierarchy for filtering
        importance_order = ["info", "low", "medium", "high", "critical"]

        query = db.query(ActivityLog).filter(
            ActivityLog.company_id == company_id,
        )

        # Apply filters
        if category:
            query = query.filter(ActivityLog.category == category)
        if action:
            if "%" in action or "_" in action:
                query = query.filter(ActivityLog.action.like(action))
            else:
                query = query.filter(ActivityLog.action == action)
        if actor_type:
            query = query.filter(ActivityLog.actor_type == actor_type)
        if actor_id:
            query = query.filter(ActivityLog.actor_id == actor_id)
        if entity_type:
            query = query.filter(ActivityLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(ActivityLog.entity_id == entity_id)
        if session_id:
            query = query.filter(ActivityLog.session_id == session_id)
        if importance:
            query = query.filter(ActivityLog.importance == importance)
        if importance_min:
            min_idx = importance_order.index(importance_min) if importance_min in importance_order else 0
            allowed = importance_order[min_idx:]
            query = query.filter(ActivityLog.importance.in_(allowed))
        if since:
            query = query.filter(ActivityLog.occurred_at >= since)
        if until:
            query = query.filter(ActivityLog.occurred_at <= until)

        # Count before pagination
        total = query.count()

        # Sort
        sort_col = ActivityLog.occurred_at
        if order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # Paginate
        activities = query.offset(offset).limit(limit).all()

        return activities, total

    except Exception as e:
        logger.warning(
            "query_activities_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return [], 0


def get_recent(
    db: Session,
    company_id: str,
    limit: int = 20,
    importance_min: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Any]:
    """Get recent activities for a tenant.

    Convenience method for Jarvis to quickly see "what happened recently".

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        limit: Max activities to return.
        importance_min: Minimum importance level.
        category: Filter by category.

    Returns:
        List of ActivityLog instances, newest first.
    """
    activities, _ = query_activities(
        db=db,
        company_id=company_id,
        importance_min=importance_min,
        category=category,
        limit=limit,
    )
    return activities


def get_summary(
    db: Session,
    company_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get aggregated activity summary for a time range.

    This is what Jarvis uses to get a high-level picture of activity
    in the tenant's world without reading individual events.

    Returns a dict with:
      - total_count: Total activities in the time range
      - by_category: {category: count}
      - by_importance: {importance: count}
      - by_actor_type: {actor_type: count}
      - recent_critical: Last 5 critical events
      - recent_high: Last 5 high-importance events

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        since: Start of time range.
        until: End of time range.

    Returns:
        Dict with aggregated summary.
    """
    try:
        from database.models.activity_log import ActivityLog

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
        if until is None:
            until = datetime.now(timezone.utc)

        base_filter = and_(
            ActivityLog.company_id == company_id,
            ActivityLog.occurred_at >= since,
            ActivityLog.occurred_at <= until,
        )

        # Total count
        total_count = db.query(func.count(ActivityLog.id)).filter(base_filter).scalar() or 0

        # By category
        by_category = dict(
            db.query(ActivityLog.category, func.count(ActivityLog.id))
            .filter(base_filter)
            .group_by(ActivityLog.category)
            .all()
        )

        # By importance
        by_importance = dict(
            db.query(ActivityLog.importance, func.count(ActivityLog.id))
            .filter(base_filter)
            .group_by(ActivityLog.importance)
            .all()
        )

        # By actor type
        by_actor_type = dict(
            db.query(ActivityLog.actor_type, func.count(ActivityLog.id))
            .filter(base_filter)
            .group_by(ActivityLog.actor_type)
            .all()
        )

        # Recent critical events
        recent_critical = [
            _entry_to_dict(e)
            for e in db.query(ActivityLog)
            .filter(base_filter, ActivityLog.importance == "critical")
            .order_by(ActivityLog.occurred_at.desc())
            .limit(5)
            .all()
        ]

        # Recent high-importance events
        recent_high = [
            _entry_to_dict(e)
            for e in db.query(ActivityLog)
            .filter(base_filter, ActivityLog.importance == "high")
            .order_by(ActivityLog.occurred_at.desc())
            .limit(5)
            .all()
        ]

        return {
            "company_id": company_id,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "total_count": total_count,
            "by_category": by_category,
            "by_importance": by_importance,
            "by_actor_type": by_actor_type,
            "recent_critical": recent_critical,
            "recent_high": recent_high,
        }

    except Exception as e:
        logger.warning(
            "get_summary_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {
            "company_id": company_id,
            "total_count": 0,
            "error": str(e)[:200],
        }


def get_trends(
    db: Session,
    company_id: str,
    category: Optional[str] = None,
    hours: int = 24,
    bucket_minutes: int = 60,
) -> List[Dict[str, Any]]:
    """Get activity trends over time (hourly/daily buckets).

    Jarvis uses this to detect patterns:
      - "Billing events spiked at 2pm" → maybe renewal batch
      - "User actions dropped to zero" → maybe site issue
      - "Security events increasing" → maybe attack

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        category: Filter by category (optional).
        hours: How many hours of history.
        bucket_minutes: Size of each time bucket.

    Returns:
        List of dicts: [{bucket_start, count, category}]
    """
    try:
        from database.models.activity_log import ActivityLog

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Use raw SQL for bucketing (more efficient than Python)
        # SQLite-compatible: use strftime for bucketing
        if db.bind.dialect.name == "sqlite":
            bucket_expr = func.strftime(
                f"%Y-%m-%d %H:%M",
                func.strftime("%Y-%m-%d %H:%M", ActivityLog.occurred_at),
            )
        else:
            # PostgreSQL: use date_trunc
            interval = f"{bucket_minutes} minutes"
            bucket_expr = func.date_trunc(interval, ActivityLog.occurred_at)

        query = db.query(
            bucket_expr.label("bucket"),
            func.count(ActivityLog.id).label("count"),
        ).filter(
            ActivityLog.company_id == company_id,
            ActivityLog.occurred_at >= since,
        )

        if category:
            query = query.filter(ActivityLog.category == category)

        results = query.group_by("bucket").order_by("bucket").all()

        return [
            {
                "bucket_start": str(r[0]),
                "count": r[1],
            }
            for r in results
        ]

    except Exception as e:
        logger.warning(
            "get_trends_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return []


def get_user_activity(
    db: Session,
    company_id: str,
    user_id: str,
    limit: int = 50,
) -> List[Any]:
    """Get all activities by a specific user.

    Jarvis uses this to understand user behavior:
      - "What has this user been doing?" → page views, clicks, changes
      - "Is this user exploring upgrade?" → billing page visits

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        user_id: User ID.
        limit: Max results.

    Returns:
        List of ActivityLog instances.
    """
    activities, _ = query_activities(
        db=db,
        company_id=company_id,
        actor_type="user",
        actor_id=user_id,
        limit=limit,
    )
    return activities


def get_entity_history(
    db: Session,
    company_id: str,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> List[Any]:
    """Get all activities affecting a specific entity.

    Jarvis uses this to understand entity context:
      - "What happened to this subscription?" → changes, payments, refunds
      - "Who touched this ticket?" → assignments, status changes, messages

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        entity_type: Type of entity.
        entity_id: ID of entity.
        limit: Max results.

    Returns:
        List of ActivityLog instances.
    """
    activities, _ = query_activities(
        db=db,
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return activities


# ══════════════════════════════════════════════════════════════════
# AWARENESS HELPERS: Used by Jarvis Awareness Engine (Domain 8)
# ══════════════════════════════════════════════════════════════════


def get_awareness_context(
    db: Session,
    company_id: str,
    hours: int = 1,
) -> Dict[str, Any]:
    """Get a comprehensive awareness context from the Activity Store.

    This is the primary method called by the Jarvis Awareness Engine
    on every tick (Domain 8: Activity Store). It returns a structured
    dict that Jarvis can use to reason about non-agentic parts.

    Returns:
      - recent_actions: Last 20 actions (for quick scan)
      - summary: Aggregated counts by category/importance
      - billing_awareness: Billing-specific events
      - user_action_awareness: User behavior patterns
      - system_awareness: System events and errors
      - flags: Auto-detected flags that Jarvis should know about

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        hours: How many hours of history to analyze.

    Returns:
        Dict with awareness context for Jarvis.
    """
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Recent actions (quick scan)
        recent_actions = [
            _entry_to_dict(e)
            for e in get_recent(db, company_id, limit=20)
            if e.occurred_at >= since
        ]

        # Full summary
        summary = get_summary(db, company_id, since=since)

        # Category-specific awareness
        billing = get_billing_awareness(db, company_id, since=since)
        user_actions = get_user_action_awareness(db, company_id, since=since)
        system = get_system_event_awareness(db, company_id, since=since)

        # Auto-detected flags
        flags = _detect_awareness_flags(summary, billing, user_actions, system)

        return {
            "company_id": company_id,
            "since": since.isoformat(),
            "hours": hours,
            "recent_actions": recent_actions,
            "summary": summary,
            "billing_awareness": billing,
            "user_action_awareness": user_actions,
            "system_awareness": system,
            "flags": flags,
        }

    except Exception as e:
        logger.warning(
            "get_awareness_context_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {
            "company_id": company_id,
            "error": str(e)[:200],
            "recent_actions": [],
            "flags": [],
        }


def get_billing_awareness(
    db: Session,
    company_id: str,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get billing-specific awareness for Jarvis.

    Jarvis uses this to understand billing state:
      - "Did the user try to upgrade?" → YES, clicked upgrade button 3 times
      - "Any payment failures?" → YES, 2 failures in last hour
      - "Is the subscription at risk?" → YES, payment method expiring

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        since: Start of time range.

    Returns:
        Dict with billing awareness data.
    """
    try:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        billing_events, count = query_activities(
            db=db,
            company_id=company_id,
            category="billing",
            since=since,
            limit=50,
        )

        # Categorize billing events
        payment_attempts = []
        payment_failures = []
        subscription_changes = []
        invoice_events = []
        upgrade_signals = []

        for event in billing_events:
            details = _safe_parse_json(event.details_json)
            action = event.action

            if "payment" in action and "fail" not in action:
                payment_attempts.append(_entry_to_dict(event))
            elif "payment" in action and "fail" in action:
                payment_failures.append(_entry_to_dict(event))
            elif "subscription" in action or "plan" in action:
                subscription_changes.append(_entry_to_dict(event))
            elif "invoice" in action:
                invoice_events.append(_entry_to_dict(event))

            # Detect upgrade intent signals
            if action in (
                "upgrade_button_clicked",
                "pricing_page_viewed",
                "plan_comparison_viewed",
                "upgrade_modal_opened",
            ):
                upgrade_signals.append(_entry_to_dict(event))

        return {
            "total_billing_events": count,
            "payment_attempts": payment_attempts[:10],
            "payment_failures": payment_failures[:10],
            "subscription_changes": subscription_changes[:10],
            "invoice_events": invoice_events[:10],
            "upgrade_signals": upgrade_signals[:10],
            "has_payment_failures": len(payment_failures) > 0,
            "has_upgrade_intent": len(upgrade_signals) > 0,
        }

    except Exception as e:
        logger.warning(
            "get_billing_awareness_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {"total_billing_events": 0, "error": str(e)[:200]}


def get_user_action_awareness(
    db: Session,
    company_id: str,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get user behavior awareness for Jarvis.

    Jarvis uses this to understand user intent:
      - "What is the user doing right now?" → Looking at billing page
      - "Is the user confused?" → YES, visited help center 3 times
      - "Is the user about to churn?" → YES, visited cancellation page

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        since: Start of time range.

    Returns:
        Dict with user action awareness.
    """
    try:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        user_events, count = query_activities(
            db=db,
            company_id=company_id,
            category="user_action",
            since=since,
            limit=100,
        )

        # Track active users
        active_users = set()
        page_views = []
        button_clicks = []
        help_signals = []
        churn_signals = []

        for event in user_events:
            if event.actor_id:
                active_users.add(event.actor_id)

            action = event.action

            if "page_view" in action:
                page_views.append(_entry_to_dict(event))
            elif "button_click" in action or "click" in action:
                button_clicks.append(_entry_to_dict(event))

            # Detect help-seeking behavior
            if action in (
                "help_page_viewed",
                "docs_page_viewed",
                "support_contacted",
                "faq_viewed",
            ):
                help_signals.append(_entry_to_dict(event))

            # Detect churn signals
            if action in (
                "cancellation_page_viewed",
                "downgrade_button_clicked",
                "export_data_clicked",
                "account_deletion_requested",
            ):
                churn_signals.append(_entry_to_dict(event))

        return {
            "total_user_actions": count,
            "active_users_count": len(active_users),
            "page_views": page_views[:20],
            "button_clicks": button_clicks[:20],
            "help_signals": help_signals[:10],
            "churn_signals": churn_signals[:10],
            "has_help_seeking": len(help_signals) > 0,
            "has_churn_risk": len(churn_signals) > 0,
        }

    except Exception as e:
        logger.warning(
            "get_user_action_awareness_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {"total_user_actions": 0, "error": str(e)[:200]}


def get_system_event_awareness(
    db: Session,
    company_id: str,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get system event awareness for Jarvis.

    Jarvis uses this to understand system health:
      - "Any API errors?" → YES, 5 errors in last hour
      - "Webhook failures?" → YES, Paddle webhook delivery failed
      - "Cron jobs running?" → YES, SLA check ran at 14:30

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        since: Start of time range.

    Returns:
        Dict with system awareness.
    """
    try:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        system_events, count = query_activities(
            db=db,
            company_id=company_id,
            category="system",
            since=since,
            limit=50,
        )

        # Categorize system events
        errors = []
        webhook_events = []
        cron_events = []
        config_changes = []

        for event in system_events:
            action = event.action

            if "error" in action or "fail" in action:
                errors.append(_entry_to_dict(event))
            elif "webhook" in action:
                webhook_events.append(_entry_to_dict(event))
            elif "cron" in action or "scheduled" in action:
                cron_events.append(_entry_to_dict(event))
            elif "config" in action or "setting" in action:
                config_changes.append(_entry_to_dict(event))

        # Also check integration events
        integration_events, int_count = query_activities(
            db=db,
            company_id=company_id,
            category="integration",
            since=since,
            limit=20,
        )

        return {
            "total_system_events": count,
            "errors": errors[:10],
            "webhook_events": webhook_events[:10],
            "cron_events": cron_events[:10],
            "config_changes": config_changes[:10],
            "integration_events": [_entry_to_dict(e) for e in integration_events[:10]],
            "has_errors": len(errors) > 0,
            "has_webhook_failures": any(
                "fail" in e.get("action", "") for e in webhook_events
            ),
        }

    except Exception as e:
        logger.warning(
            "get_system_awareness_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {"total_system_events": 0, "error": str(e)[:200]}


# ══════════════════════════════════════════════════════════════════
# PRUNING: TTL-based cleanup
# ══════════════════════════════════════════════════════════════════


def prune_expired(
    db: Session,
    company_id: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Delete expired activity log entries.

    Entries are expired when their expires_at timestamp has passed.
    Critical entries (expires_at = NULL) are never deleted.

    Args:
        db: SQLAlchemy session.
        company_id: If provided, only prune for this company.
        batch_size: Number of entries to delete per batch.

    Returns:
        Number of entries deleted.
    """
    try:
        from database.models.activity_log import ActivityLog

        now = datetime.now(timezone.utc)

        query = db.query(ActivityLog).filter(
            ActivityLog.expires_at.isnot(None),
            ActivityLog.expires_at <= now,
        )

        if company_id:
            query = query.filter(ActivityLog.company_id == company_id)

        # Fetch IDs first (SQLite compatibility)
        to_delete = query.limit(batch_size).all()
        delete_ids = [e.id for e in to_delete]

        if delete_ids:
            deleted = (
                db.query(ActivityLog)
                .filter(ActivityLog.id.in_(delete_ids))
                .delete(synchronize_session=False)
            )
            db.flush()

            logger.info(
                "activity_log_pruned: company=%s, deleted=%d",
                company_id or "all", deleted,
            )
            return deleted

        return 0

    except Exception as e:
        logger.warning(
            "prune_expired_failed: company=%s, error=%s",
            company_id or "all", str(e)[:200],
        )
        return 0


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════


def _entry_to_dict(entry: Any) -> Dict[str, Any]:
    """Convert an ActivityLog instance to a dict for serialization."""
    try:
        return {
            "id": str(entry.id),
            "company_id": entry.company_id,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "actor_name": entry.actor_name,
            "category": entry.category,
            "action": entry.action,
            "label": entry.label,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "session_id": entry.session_id,
            "route": entry.route,
            "method": entry.method,
            "details": _safe_parse_json(entry.details_json),
            "importance": entry.importance,
            "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
    except Exception:
        return {"id": str(getattr(entry, "id", "unknown")), "error": "serialization_failed"}


def _safe_parse_json(raw: str) -> Dict[str, Any]:
    """Safely parse JSON string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _detect_awareness_flags(
    summary: Dict[str, Any],
    billing: Dict[str, Any],
    user_actions: Dict[str, Any],
    system: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Auto-detect flags that Jarvis should know about.

    These are NOT alerts (those come from the Awareness Engine rule checks).
    These are contextual hints that help Jarvis reason better.

    Returns:
        List of flag dicts: [{flag, description, severity}]
    """
    flags = []

    # Payment failures
    if billing.get("has_payment_failures"):
        flags.append({
            "flag": "payment_failures_detected",
            "description": "Payment failures detected in recent billing events",
            "severity": "high",
        })

    # Upgrade intent
    if billing.get("has_upgrade_intent"):
        flags.append({
            "flag": "upgrade_intent_detected",
            "description": "User has shown intent to upgrade (pricing page visits, upgrade button clicks)",
            "severity": "medium",
        })

    # Help-seeking behavior
    if user_actions.get("has_help_seeking"):
        flags.append({
            "flag": "user_help_seeking",
            "description": "User is seeking help (help pages, docs, support contact)",
            "severity": "medium",
        })

    # Churn risk
    if user_actions.get("has_churn_risk"):
        flags.append({
            "flag": "churn_risk_detected",
            "description": "User showing churn signals (cancellation page, data export)",
            "severity": "high",
        })

    # System errors
    if system.get("has_errors"):
        flags.append({
            "flag": "system_errors_detected",
            "description": "System errors detected in recent events",
            "severity": "high",
        })

    # Webhook failures
    if system.get("has_webhook_failures"):
        flags.append({
            "flag": "webhook_failures_detected",
            "description": "Webhook delivery failures detected",
            "severity": "high",
        })

    # High activity volume
    total = summary.get("total_count", 0)
    if total > 500:
        flags.append({
            "flag": "high_activity_volume",
            "description": f"Very high activity volume: {total} events in time range",
            "severity": "low",
        })

    # No user activity (possible site issue)
    if total > 0 and user_actions.get("total_user_actions", 0) == 0:
        flags.append({
            "flag": "no_user_activity",
            "description": "No user actions recorded — possible site issue or off-hours",
            "severity": "low",
        })

    return flags
