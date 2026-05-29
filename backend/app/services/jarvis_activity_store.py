"""
PARWA Jarvis Activity Store Service

The central service for recording and querying EVERY action that happens
in the system. This is the "memory" for non-agentic parts.

Two awareness paths for Jarvis:
  1. AGENTIC PARTS:  Jarvis ASKS variant agents directly via variant_bridge
  2. NON-AGENTIC:    Events written here, Jarvis READS them

This service handles path #2.

Key Functions:
  - record_event():    Write any event into the activity store
  - query_events():    Read events with powerful filtering
  - get_recent():      Get recent activity for a tenant
  - get_summary():     Get activity summary by source/category
  - get_unread_count(): How many events Jarvis hasn't seen yet
  - mark_jarvis_seen(): Mark events as processed by Jarvis

Event Sources (who writes here):
  - API middleware (user_action events)
  - Billing service (payment_failed, subscription_changed)
  - Channel services (email_bounced, sms_failed, call_dropped)
  - Admin actions (upgrade, downgrade, config_change)
  - System cron (scheduled_tasks, alerts)
  - Integration service (webhook_received, api_key_rotated)

Tenant Scoping:
  - All queries filter by company_id (BC-001)
  - variant_scope limits visibility to tenant's active variants
  - Admin/Owner sees everything across all tenants

BC-001: company_id first parameter on all public methods.
BC-008: Every public method wrapped in try/except - never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("jarvis_activity_store")


# ── Constants ──────────────────────────────────────────────────────

# Maximum events to return in a single query
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

# Control boundaries — what Jarvis can do about an event
CONTROL_NOTIFY_ONLY = "notify_only"
CONTROL_AGENT_CONTROLLED = "agent_controlled"
CONTROL_JARVIS_CAN_ACT = "jarvis_can_act"
CONTROL_HUMAN_REQUIRED = "human_required"

# Event sources
SOURCE_USER_ACTION = "user_action"
SOURCE_BILLING = "billing"
SOURCE_CHANNEL = "channel"
SOURCE_ADMIN = "admin"
SOURCE_SYSTEM = "system"
SOURCE_INTEGRATION = "integration"
SOURCE_AGENT_ACTION = "agent_action"

# Event categories
CATEGORY_UI = "ui"
CATEGORY_SUBSCRIPTION = "subscription"
CATEGORY_PAYMENT = "payment"
CATEGORY_REFUND = "refund"
CATEGORY_CHANNEL_EMAIL = "channel_email"
CATEGORY_CHANNEL_SMS = "channel_sms"
CATEGORY_CHANNEL_VOICE = "channel_voice"
CATEGORY_CHANNEL_CHAT = "channel_chat"
CATEGORY_CHANNEL_WEBHOOK = "channel_webhook"
CATEGORY_CONFIG = "config"
CATEGORY_SECURITY = "security"
CATEGORY_INTEGRATION = "integration"
CATEGORY_CRON = "cron"
CATEGORY_AGENT = "agent"
CATEGORY_SLA = "sla"
CATEGORY_ESCALATION = "escalation"
CATEGORY_QUALITY = "quality"
CATEGORY_TRAINING = "training"
# New categories for full Jarvis awareness
CATEGORY_SHADOW_MODE = "shadow_mode"
CATEGORY_DASHBOARD = "dashboard"
CATEGORY_VARIANT_OPS = "variant_ops"
CATEGORY_KNOWLEDGE_OPS = "knowledge_ops"
CATEGORY_ONBOARDING = "onboarding"
CATEGORY_NOTIFICATION = "notification"
CATEGORY_APPROVAL_FLOW = "approval_flow"


# ── Helper ──────────────────────────────────────────────────────

def _safe_json_parse(raw: Optional[str]) -> Dict[str, Any]:
    """Safely parse JSON string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


# ══════════════════════════════════════════════════════════════════
# RECORD EVENTS
# ══════════════════════════════════════════════════════════════════


def record_event(
    db: Session,
    company_id: str,
    event_source: str,
    event_category: str,
    action: str,
    severity: str = "info",
    actor_id: Optional[str] = None,
    actor_type: str = "system",
    variant_scope: Optional[str] = None,
    instance_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    jarvis_relevant: bool = True,
    jarvis_control_boundary: str = CONTROL_NOTIFY_ONLY,
    session_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> Optional[Any]:
    """Record an event in the Activity Store.

    This is the main entry point for writing events. Any part of the
    system can call this to record what happened.

    BC-008: Never crashes. Returns None on failure, logs the error.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        event_source: Where the event came from (user_action, billing, etc.)
        event_category: What domain (payment, channel_email, etc.)
        action: What happened (e.g., "payment_failed")
        severity: info, warning, critical, emergency
        actor_id: Who performed the action
        actor_type: user, admin, system, agent, api_key, cron
        variant_scope: Which variant this relates to (mini_parwa, parwa, etc.)
        instance_id: Specific variant instance ID
        description: Human-readable description
        context: Structured context data dict
        old_value: Previous value (for change events)
        new_value: New value (for change events)
        resource_type: Type of affected resource
        resource_id: ID of affected resource
        jarvis_relevant: Should Jarvis pay attention?
        jarvis_control_boundary: What Jarvis can do about this
        session_id: Related Jarvis CC session
        occurred_at: When the event actually happened (defaults to now)

    Returns:
        JarvisActivityEvent ORM instance, or None on failure.
    """
    try:
        from database.models.jarvis_activity import JarvisActivityEvent

        now = datetime.now(timezone.utc)

        event = JarvisActivityEvent(
            id=str(uuid.uuid4()),
            company_id=company_id,
            event_source=event_source,
            event_category=event_category,
            action=action,
            severity=severity,
            actor_id=actor_id,
            actor_type=actor_type,
            variant_scope=variant_scope,
            instance_id=instance_id,
            description=description,
            context_json=json.dumps(context or {}, default=str),
            old_value=old_value,
            new_value=new_value,
            resource_type=resource_type,
            resource_id=resource_id,
            jarvis_relevant=jarvis_relevant,
            jarvis_control_boundary=jarvis_control_boundary,
            session_id=session_id,
            occurred_at=occurred_at or now,
            created_at=now,
        )

        db.add(event)
        db.flush()

        logger.info(
            "activity_event_recorded: company=%s, source=%s, "
            "category=%s, action=%s, severity=%s, actor=%s",
            company_id, event_source, event_category,
            action, severity, actor_type,
        )

        return event

    except Exception as e:
        logger.error(
            "activity_event_record_failed: company=%s, "
            "source=%s, action=%s, error=%s",
            company_id, event_source, action, str(e)[:200],
        )
        return None


# ── Convenience recorders for common event types ──────────────────


def record_user_action(
    db: Session,
    company_id: str,
    action: str,
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    variant_scope: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_NOTIFY_ONLY,
    session_id: Optional[str] = None,
) -> Optional[Any]:
    """Record a user action event (button click, page view, etc.).

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What the user did (e.g., "upgrade_clicked", "page_view").
        actor_id: User ID.
        description: Human-readable description.
        context: Additional context (page, button, etc.).
        variant_scope: Which variant this relates to.
        jarvis_control_boundary: What Jarvis can do about this.
        session_id: Related CC session.

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_USER_ACTION,
        event_category=CATEGORY_UI,
        action=action,
        severity="info",
        actor_id=actor_id,
        actor_type="user",
        variant_scope=variant_scope,
        description=description,
        context=context,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
        session_id=session_id,
    )


def record_billing_event(
    db: Session,
    company_id: str,
    action: str,
    severity: str = "info",
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resource_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_NOTIFY_ONLY,
) -> Optional[Any]:
    """Record a billing event (payment failed, subscription changed, etc.).

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What happened (e.g., "payment_failed", "subscription_created").
        severity: How important.
        actor_id: Who triggered it (user_id or "system").
        description: Human-readable description.
        context: Additional context (amount, currency, error_code, etc.).
        resource_id: Related payment/subscription ID.
        jarvis_control_boundary: What Jarvis can do (usually notify_only for billing).

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_BILLING,
        event_category=CATEGORY_SUBSCRIPTION if "subscription" in action else CATEGORY_PAYMENT,
        action=action,
        severity=severity,
        actor_id=actor_id,
        actor_type="system",
        description=description,
        context=context,
        resource_type="subscription" if "subscription" in action else "payment",
        resource_id=resource_id,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_channel_event(
    db: Session,
    company_id: str,
    channel_type: str,
    action: str,
    severity: str = "info",
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resource_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_NOTIFY_ONLY,
) -> Optional[Any]:
    """Record a channel event (email bounced, SMS failed, etc.).

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        channel_type: email, sms, voice, chat, webhook.
        action: What happened (e.g., "email_bounced", "sms_failed").
        severity: How important.
        description: Human-readable description.
        context: Additional context.
        resource_id: Related channel resource ID.
        jarvis_control_boundary: What Jarvis can do.

    Returns:
        JarvisActivityEvent or None.
    """
    category_map = {
        "email": CATEGORY_CHANNEL_EMAIL,
        "sms": CATEGORY_CHANNEL_SMS,
        "voice": CATEGORY_CHANNEL_VOICE,
        "chat": CATEGORY_CHANNEL_CHAT,
        "webhook": CATEGORY_CHANNEL_WEBHOOK,
    }

    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_CHANNEL,
        event_category=category_map.get(channel_type, CATEGORY_CHANNEL_EMAIL),
        action=action,
        severity=severity,
        actor_type="system",
        description=description,
        context=context,
        resource_type="channel",
        resource_id=resource_id,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_admin_action(
    db: Session,
    company_id: str,
    action: str,
    actor_id: Optional[str] = None,
    severity: str = "info",
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_HUMAN_REQUIRED,
) -> Optional[Any]:
    """Record an admin action (upgrade, downgrade, config change, etc.).

    Admin actions are typically human_required for Jarvis control —
    Jarvis can see them but not override them.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What the admin did.
        actor_id: Admin user ID.
        severity: How important.
        description: Human-readable description.
        context: Additional context.
        old_value: Previous value.
        new_value: New value.
        jarvis_control_boundary: What Jarvis can do (usually human_required).

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_ADMIN,
        event_category=CATEGORY_CONFIG,
        action=action,
        severity=severity,
        actor_id=actor_id,
        actor_type="admin",
        description=description,
        context=context,
        old_value=old_value,
        new_value=new_value,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_agent_action(
    db: Session,
    company_id: str,
    action: str,
    actor_id: Optional[str] = None,
    variant_scope: Optional[str] = None,
    instance_id: Optional[str] = None,
    severity: str = "info",
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_AGENT_CONTROLLED,
) -> Optional[Any]:
    """Record a variant agent action (refund issued, ticket escalated, etc.).

    Agent actions are typically agent_controlled — Jarvis knows about
    them but the variant agent is the authority.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What the agent did.
        actor_id: Agent instance ID.
        variant_scope: Which variant (mini_parwa, parwa, parwa_high).
        instance_id: Specific instance ID.
        severity: How important.
        description: Human-readable description.
        context: Additional context.
        resource_type: Type of affected resource.
        resource_id: ID of affected resource.
        jarvis_control_boundary: What Jarvis can do.

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_AGENT_ACTION,
        event_category=CATEGORY_AGENT,
        action=action,
        severity=severity,
        actor_id=actor_id,
        actor_type="agent",
        variant_scope=variant_scope,
        instance_id=instance_id,
        description=description,
        context=context,
        resource_type=resource_type,
        resource_id=resource_id,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_shadow_mode_event(
    db: Session,
    company_id: str,
    action: str,
    severity: str = "info",
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_JARVIS_CAN_ACT,
) -> Optional[Any]:
    """Record a shadow mode event (enabled, disabled, promoted, graduated).

    Shadow mode events are jarvis_can_act — Jarvis can control shadow mode.
    This is critical for Jarvis awareness because shadow mode changes
    directly affect which variant handles customer messages.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What happened (e.g., "shadow_mode_enabled", "shadow_mode_promoted").
        severity: How important.
        actor_id: User ID who triggered the change.
        description: Human-readable description.
        context: Additional context (live_variant, shadow_variant, phase, etc.).
        old_value: Previous state (e.g., "off", "shadow", "supervised").
        new_value: New state (e.g., "shadow", "supervised", "graduated").
        jarvis_control_boundary: What Jarvis can do (default: jarvis_can_act).

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_ADMIN,
        event_category=CATEGORY_SHADOW_MODE,
        action=action,
        severity=severity,
        actor_id=actor_id,
        actor_type="admin",
        description=description,
        context=context,
        old_value=old_value,
        new_value=new_value,
        resource_type="shadow_mode",
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_dashboard_event(
    db: Session,
    company_id: str,
    action: str,
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_NOTIFY_ONLY,
) -> Optional[Any]:
    """Record a dashboard event (page view, button click, ticket action).

    Dashboard events are notify_only by default — Jarvis sees them but
    doesn't control the dashboard. This gives Jarvis awareness of what
    the user is doing in the UI: which pages they visit, which tickets
    they interact with, which settings they change.

    This is CRITICAL for Jarvis to have context-aware conversations.
    If a user is on the billing page and says "I need help", Jarvis
    should know they're looking at billing.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What happened (e.g., "page_view", "ticket_created", "ticket_resolved").
        actor_id: User ID.
        description: Human-readable description.
        context: Additional context (page, ticket_id, etc.).
        resource_type: Type of resource (ticket, subscription, etc.).
        resource_id: ID of the resource.
        jarvis_control_boundary: What Jarvis can do.

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_USER_ACTION,
        event_category=CATEGORY_DASHBOARD,
        action=action,
        severity="info",
        actor_id=actor_id,
        actor_type="user",
        description=description,
        context=context,
        resource_type=resource_type,
        resource_id=resource_id,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_variant_ops_event(
    db: Session,
    company_id: str,
    action: str,
    severity: str = "info",
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    variant_scope: Optional[str] = None,
    instance_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_JARVIS_CAN_ACT,
) -> Optional[Any]:
    """Record a variant operation event (rebalance, escalate, status change).

    Variant ops events are jarvis_can_act — Jarvis can control variant
    operations like rebalancing and escalation.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What happened (e.g., "variant_rebalanced", "variant_escalated").
        severity: How important.
        actor_id: User or system that triggered it.
        description: Human-readable description.
        context: Additional context.
        variant_scope: Which variant (mini_parwa, parwa, parwa_high).
        instance_id: Specific instance ID.
        jarvis_control_boundary: What Jarvis can do.

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_ADMIN,
        event_category=CATEGORY_VARIANT_OPS,
        action=action,
        severity=severity,
        actor_id=actor_id,
        actor_type="admin",
        variant_scope=variant_scope,
        instance_id=instance_id,
        description=description,
        context=context,
        resource_type="variant_instance",
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


def record_knowledge_ops_event(
    db: Session,
    company_id: str,
    action: str,
    actor_id: Optional[str] = None,
    description: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resource_id: Optional[str] = None,
    jarvis_control_boundary: str = CONTROL_JARVIS_CAN_ACT,
) -> Optional[Any]:
    """Record a knowledge base operation event (upload, delete, search).

    Knowledge ops events are jarvis_can_act — Jarvis can control knowledge
    base operations. When a user uploads a doc, Jarvis should know about it
    so it can reference the new knowledge in conversations.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID.
        action: What happened (e.g., "document_uploaded", "document_deleted").
        actor_id: User ID.
        description: Human-readable description.
        context: Additional context (filename, doc_id, etc.).
        resource_id: Document ID.
        jarvis_control_boundary: What Jarvis can do.

    Returns:
        JarvisActivityEvent or None.
    """
    return record_event(
        db=db,
        company_id=company_id,
        event_source=SOURCE_USER_ACTION,
        event_category=CATEGORY_KNOWLEDGE_OPS,
        action=action,
        severity="info",
        actor_id=actor_id,
        actor_type="user",
        description=description,
        context=context,
        resource_type="knowledge_document",
        resource_id=resource_id,
        jarvis_relevant=True,
        jarvis_control_boundary=jarvis_control_boundary,
    )


# ══════════════════════════════════════════════════════════════════
# QUERY EVENTS
# ══════════════════════════════════════════════════════════════════


def query_events(
    db: Session,
    company_id: str,
    event_source: Optional[str] = None,
    event_category: Optional[str] = None,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    variant_scope: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    jarvis_relevant_only: bool = True,
    jarvis_control_boundary: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], int]:
    """Query activity events with powerful filtering.

    All results are scoped to company_id (BC-001).
    Optionally filter by variant_scope for tenant-scoped visibility.

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        event_source: Filter by event source.
        event_category: Filter by category.
        action: Filter by action.
        severity: Filter by severity.
        variant_scope: Filter by variant (mini_parwa, parwa, parwa_high).
        actor_id: Filter by actor.
        actor_type: Filter by actor type.
        resource_type: Filter by resource type.
        resource_id: Filter by resource ID.
        jarvis_relevant_only: Only return Jarvis-relevant events.
        jarvis_control_boundary: Filter by control boundary.
        date_from: Include events at or after this datetime.
        date_to: Include events at or before this datetime.
        page: Page number (1-based).
        page_size: Items per page.

    Returns:
        Tuple of (event_dicts, total_count).
    """
    try:
        from database.models.jarvis_activity import JarvisActivityEvent

        query = db.query(JarvisActivityEvent).filter(
            JarvisActivityEvent.company_id == company_id,
        )

        # Apply filters
        if event_source:
            query = query.filter(JarvisActivityEvent.event_source == event_source)
        if event_category:
            query = query.filter(JarvisActivityEvent.event_category == event_category)
        if action:
            query = query.filter(JarvisActivityEvent.action == action)
        if severity:
            query = query.filter(JarvisActivityEvent.severity == severity)
        if variant_scope:
            query = query.filter(
                or_(
                    JarvisActivityEvent.variant_scope == variant_scope,
                    JarvisActivityEvent.variant_scope.is_(None),
                )
            )
        if actor_id:
            query = query.filter(JarvisActivityEvent.actor_id == actor_id)
        if actor_type:
            query = query.filter(JarvisActivityEvent.actor_type == actor_type)
        if resource_type:
            query = query.filter(JarvisActivityEvent.resource_type == resource_type)
        if resource_id:
            query = query.filter(JarvisActivityEvent.resource_id == resource_id)
        if jarvis_relevant_only:
            query = query.filter(JarvisActivityEvent.jarvis_relevant == True)  # noqa: E712
        if jarvis_control_boundary:
            query = query.filter(
                JarvisActivityEvent.jarvis_control_boundary == jarvis_control_boundary,
            )
        if date_from:
            query = query.filter(JarvisActivityEvent.created_at >= date_from)
        if date_to:
            query = query.filter(JarvisActivityEvent.created_at <= date_to)

        # Count
        total = query.count()

        # Sort newest first
        query = query.order_by(JarvisActivityEvent.created_at.desc())

        # Paginate
        offset = (page - 1) * page_size
        page_size = min(page_size, MAX_PAGE_SIZE)
        events = query.offset(offset).limit(page_size).all()

        # Convert to dicts
        result = [_event_to_dict(e) for e in events]

        return result, total

    except Exception as e:
        logger.error(
            "query_events_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return [], 0


def get_recent(
    db: Session,
    company_id: str,
    minutes: int = 60,
    variant_scope: Optional[str] = None,
    jarvis_relevant_only: bool = True,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get recent activity events for a tenant.

    Convenience function for the most common query pattern:
    "What happened in the last N minutes that Jarvis should know about?"

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        minutes: How far back to look (default 60 minutes).
        variant_scope: Filter by variant.
        jarvis_relevant_only: Only Jarvis-relevant events.
        limit: Max events to return.

    Returns:
        List of event dicts, newest first.
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    events, _ = query_events(
        db=db,
        company_id=company_id,
        variant_scope=variant_scope,
        jarvis_relevant_only=jarvis_relevant_only,
        date_from=since,
        page_size=limit,
    )
    return events


def get_summary(
    db: Session,
    company_id: str,
    hours: int = 24,
    variant_scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Get activity summary for a tenant.

    Returns counts by source, category, severity, and control boundary.
    Useful for Jarvis to quickly understand "what's been happening."

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        hours: Look-back window in hours (default 24).
        variant_scope: Filter by variant.

    Returns:
        Dict with by_source, by_category, by_severity, by_control_boundary,
        critical_events, recent_notable.
    """
    try:
        from database.models.jarvis_activity import JarvisActivityEvent

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        base_query = db.query(JarvisActivityEvent).filter(
            JarvisActivityEvent.company_id == company_id,
            JarvisActivityEvent.created_at >= since,
            JarvisActivityEvent.jarvis_relevant == True,  # noqa: E712
        )

        if variant_scope:
            base_query = base_query.filter(
                or_(
                    JarvisActivityEvent.variant_scope == variant_scope,
                    JarvisActivityEvent.variant_scope.is_(None),
                )
            )

        events = base_query.order_by(
            JarvisActivityEvent.created_at.desc()
        ).limit(1000).all()

        # Count by source
        by_source: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_control: Dict[str, int] = {}
        critical_events: List[Dict[str, Any]] = []

        for event in events:
            by_source[event.event_source] = by_source.get(event.event_source, 0) + 1
            by_category[event.event_category] = by_category.get(event.event_category, 0) + 1
            by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
            by_control[event.jarvis_control_boundary or "unknown"] = by_control.get(
                event.jarvis_control_boundary or "unknown", 0
            ) + 1

            if event.severity in ("critical", "emergency"):
                critical_events.append(_event_to_dict(event))

        # Recent notable events (last 10 non-info)
        notable = [
            _event_to_dict(e) for e in events
            if e.severity != "info"
        ][:10]

        return {
            "company_id": company_id,
            "period_hours": hours,
            "variant_scope": variant_scope,
            "total_events": len(events),
            "by_source": by_source,
            "by_category": by_category,
            "by_severity": by_severity,
            "by_control_boundary": by_control,
            "critical_count": len(critical_events),
            "critical_events": critical_events[:5],
            "recent_notable": notable,
        }

    except Exception as e:
        logger.error(
            "get_summary_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {
            "company_id": company_id,
            "error": str(e)[:200],
            "total_events": 0,
        }


def get_unread_count(
    db: Session,
    company_id: str,
    variant_scope: Optional[str] = None,
    since: Optional[datetime] = None,
) -> int:
    """Count Jarvis-relevant events that haven't been processed yet.

    "Unread" means events created after the last awareness tick
    (i.e., the `since` timestamp).

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        variant_scope: Filter by variant.
        since: Timestamp of last read (defaults to 30 minutes ago).

    Returns:
        Count of unread events.
    """
    try:
        from database.models.jarvis_activity import JarvisActivityEvent

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(minutes=30)

        query = db.query(func.count(JarvisActivityEvent.id)).filter(
            JarvisActivityEvent.company_id == company_id,
            JarvisActivityEvent.jarvis_relevant == True,  # noqa: E712
            JarvisActivityEvent.created_at >= since,
        )

        if variant_scope:
            query = query.filter(
                or_(
                    JarvisActivityEvent.variant_scope == variant_scope,
                    JarvisActivityEvent.variant_scope.is_(None),
                )
            )

        return query.scalar() or 0

    except Exception as e:
        logger.error(
            "get_unread_count_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return 0


def get_control_boundary_summary(
    db: Session,
    company_id: str,
    hours: int = 24,
) -> Dict[str, Any]:
    """Get a summary of events by control boundary.

    This tells Jarvis: "What can I control, what can't I control,
    and what needs human attention?"

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        hours: Look-back window.

    Returns:
        Dict grouping events by control boundary.
    """
    try:
        summary = get_summary(db, company_id, hours=hours)
        by_control = summary.get("by_control_boundary", {})

        return {
            "company_id": company_id,
            "period_hours": hours,
            "jarvis_can_act": by_control.get(CONTROL_JARVIS_CAN_ACT, 0),
            "agent_controlled": by_control.get(CONTROL_AGENT_CONTROLLED, 0),
            "notify_only": by_control.get(CONTROL_NOTIFY_ONLY, 0),
            "human_required": by_control.get(CONTROL_HUMAN_REQUIRED, 0),
            "interpretation": {
                CONTROL_JARVIS_CAN_ACT: "Jarvis can take action on these",
                CONTROL_AGENT_CONTROLLED: "Variant agents handle these - ask them",
                CONTROL_NOTIFY_ONLY: "Jarvis sees these but can't control them",
                CONTROL_HUMAN_REQUIRED: "Only humans can handle these - alert admin",
            },
        }

    except Exception as e:
        logger.error(
            "get_control_boundary_summary_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {"company_id": company_id, "error": str(e)[:200]}


# ══════════════════════════════════════════════════════════════════
# AWARENESS INTEGRATION
# ══════════════════════════════════════════════════════════════════


def collect_activity_awareness(
    db: Session,
    company_id: str,
    variant_scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect activity awareness data for the awareness engine tick.

    This is called by jarvis_awareness_engine.py during a tick to
    merge Activity Store data into the awareness snapshot.

    Returns a dict with:
      - recent_activity: Last 20 events
      - summary: Counts by source/category/severity
      - critical_events: Events needing immediate attention
      - control_boundary_summary: What Jarvis can/cannot control
      - unread_count: Events since last tick

    Args:
        db: SQLAlchemy session.
        company_id: Tenant ID (BC-001).
        variant_scope: Filter by variant.

    Returns:
        Dict with activity awareness data.
    """
    try:
        recent = get_recent(
            db, company_id,
            minutes=60,
            variant_scope=variant_scope,
            limit=20,
        )

        summary = get_summary(
            db, company_id,
            hours=24,
            variant_scope=variant_scope,
        )

        control_summary = get_control_boundary_summary(
            db, company_id,
            hours=24,
        )

        unread = get_unread_count(
            db, company_id,
            variant_scope=variant_scope,
        )

        return {
            "activity_store_connected": True,
            "recent_activity": recent,
            "activity_summary": summary,
            "control_boundary_summary": control_summary,
            "unread_activity_count": unread,
            "critical_activity_count": summary.get("critical_count", 0),
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(
            "collect_activity_awareness_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {
            "activity_store_connected": False,
            "error": str(e)[:200],
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════


def _event_to_dict(event: Any) -> Dict[str, Any]:
    """Convert a JarvisActivityEvent ORM instance to a dict.

    Args:
        event: JarvisActivityEvent instance.

    Returns:
        Dict with all event fields.
    """
    return {
        "id": event.id,
        "company_id": event.company_id,
        "variant_scope": event.variant_scope,
        "instance_id": event.instance_id,
        "event_source": event.event_source,
        "event_category": event.event_category,
        "action": event.action,
        "severity": event.severity,
        "actor_id": event.actor_id,
        "actor_type": event.actor_type,
        "description": event.description,
        "context": _safe_json_parse(event.context_json),
        "old_value": event.old_value,
        "new_value": event.new_value,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "jarvis_relevant": event.jarvis_relevant,
        "jarvis_control_boundary": event.jarvis_control_boundary,
        "session_id": event.session_id,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


__all__ = [
    # Record events
    "record_event",
    "record_user_action",
    "record_billing_event",
    "record_channel_event",
    "record_admin_action",
    "record_agent_action",
    # New recorders for full awareness
    "record_shadow_mode_event",
    "record_dashboard_event",
    "record_variant_ops_event",
    "record_knowledge_ops_event",
    # Query events
    "query_events",
    "get_recent",
    "get_summary",
    "get_unread_count",
    "get_control_boundary_summary",
    # Awareness integration
    "collect_activity_awareness",
    # Constants
    "CONTROL_NOTIFY_ONLY",
    "CONTROL_AGENT_CONTROLLED",
    "CONTROL_JARVIS_CAN_ACT",
    "CONTROL_HUMAN_REQUIRED",
]
