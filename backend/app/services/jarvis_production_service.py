"""
PARWA Jarvis Production Service

The AI control center for post-onboarding users. Jarvis has:
- Full system awareness (every click, action, event)
- Control capabilities (send SMS/email, pause AI, manage users)
- Memory system (today's tasks, conversation history)
- Proactive alerts (speaks up when important things happen)
- Direct vs Draft action logic (simple = direct, complex = draft first)

Based on: JARVIS_Production_Documentation.md
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.exceptions import ValidationError
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from database.models.jarvis_production import (
    JarvisActionLog,
    JarvisActivityEvent,
    JarvisAlert,
    JarvisDraft,
    JarvisMemory,
    JarvisProductionSession,
)

logger = logging.getLogger(__name__)


# ── Enums ───────────────────────────────────────────────────────────


class VariantTier(str, Enum):
    STARTER = "starter"  # $999 - Basic awareness
    GROWTH = "growth"  # $2,499 - Full awareness + SMS/Email control
    HIGH = "high"  # $3,999 - Deep insights + pattern detection


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    # Communication
    SEND_SMS = "send_sms"
    SEND_EMAIL = "send_email"
    BULK_SMS = "bulk_sms"
    BULK_EMAIL = "bulk_email"
    # AI Control
    PAUSE_AI = "pause_ai"
    RESUME_AI = "resume_ai"
    UNDO_ACTION = "undo_action"
    SWITCH_MODE = "switch_mode"
    # User Management
    INVITE_TEAM = "invite_team"
    CHANGE_ROLE = "change_role"
    RESET_PASSWORD = "reset_password"
    # Integration
    CONNECT_INTEGRATION = "connect_integration"
    TEST_CONNECTION = "test_connection"
    SYNC_DATA = "sync_data"
    # Knowledge
    UPLOAD_DOCUMENT = "upload_document"
    SEARCH_DOCUMENTS = "search_documents"
    # Settings
    UPDATE_SETTINGS = "update_settings"
    SET_THRESHOLD = "set_threshold"


# ── Tier Feature Flags ───────────────────────────────────────────────

TIER_FEATURES = {
    VariantTier.STARTER: {
        "awareness_level": "basic",
        "sms_email_control": False,
        "team_management": False,
        "bulk_actions": False,
        "pattern_detection": False,
        "predictive_analytics": False,
        "priority_response": False,
        "memory_retention_days": 1,
        "alert_types": ["error_spike", "integration_down"],
    },
    VariantTier.GROWTH: {
        "awareness_level": "full",
        "sms_email_control": True,
        "team_management": True,
        "bulk_actions": True,
        "pattern_detection": False,
        "predictive_analytics": False,
        "priority_response": False,
        "memory_retention_days": 7,
        "alert_types": [
            "error_spike",
            "integration_down",
            "queue_overflow",
            "ticket_limit_warning",
            "vip_customer_issue",
        ],
    },
    VariantTier.HIGH: {
        "awareness_level": "deep",
        "sms_email_control": True,
        "team_management": True,
        "bulk_actions": True,
        "pattern_detection": True,
        "predictive_analytics": True,
        "priority_response": True,
        "memory_retention_days": 30,
        "alert_types": ["all"],  # All alert types
    },
}


# ── Actions that require draft-then-approve ──────────────────────────

DRAFT_REQUIRED_ACTIONS = {
    ActionType.BULK_SMS,
    ActionType.BULK_EMAIL,
    ActionType.INVITE_TEAM,
    ActionType.CONNECT_INTEGRATION,
    ActionType.UPDATE_SETTINGS,
}


# ── Session Management ───────────────────────────────────────────────


def get_or_create_session(
    db: Session,
    user_id: str,
    company_id: str,
    variant_tier: str = "starter",
) -> JarvisProductionSession:
    """Get existing session or create new Production Jarvis session."""

    # Try to find active session
    session = (
        db.query(JarvisProductionSession)
        .filter(
            JarvisProductionSession.user_id == user_id,
            JarvisProductionSession.company_id == company_id,
            JarvisProductionSession.is_active,
        )
        .first()
    )

    if session:
        # Update last interaction
        session.last_interaction_at = datetime.now(timezone.utc)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()
        return session

    # Create new session
    features = TIER_FEATURES.get(
        VariantTier(variant_tier), TIER_FEATURES[VariantTier.STARTER]
    )

    session = JarvisProductionSession(
        user_id=user_id,
        company_id=company_id,
        variant_tier=variant_tier,
        features_enabled_json=json.dumps(features),
        context_json=json.dumps({}),
        today_tasks_json=json.dumps([]),
    )
    db.add(session)
    db.flush()

    # Log session creation
    track_activity(
        db=db,
        session_id=str(session.id),
        company_id=company_id,
        user_id=user_id,
        event_type="session",
        event_category="system",
        event_name="jarvis_session_created",
        description="Production Jarvis session started",
    )

    return session


# ── Activity Tracking (Awareness System) ─────────────────────────────


def track_activity(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    event_type: str,
    event_category: str,
    event_name: str,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
    page_url: Optional[str] = None,
    page_name: Optional[str] = None,
    related_ticket_id: Optional[str] = None,
    related_user_id: Optional[str] = None,
    related_integration: Optional[str] = None,
) -> JarvisActivityEvent:
    """Track an activity event for Jarvis awareness."""

    event = JarvisActivityEvent(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        event_type=event_type,
        event_category=event_category,
        event_name=event_name,
        description=description,
        metadata_json=json.dumps(metadata or {}),
        page_url=page_url,
        page_name=page_name,
        related_ticket_id=related_ticket_id,
        related_user_id=related_user_id,
        related_integration=related_integration,
    )
    db.add(event)
    db.flush()

    # Update today's tasks
    _update_today_tasks(db, session_id, event_name, description)

    return event


def _update_today_tasks(
    db: Session,
    session_id: str,
    event_name: str,
    description: Optional[str],
) -> None:
    """Update today's task list in session."""
    session = (
        db.query(JarvisProductionSession)
        .filter(JarvisProductionSession.id == session_id)
        .first()
    )
    if not session:
        return

    try:
        tasks = json.loads(session.today_tasks_json or "[]")
        tasks.append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": event_name,
                "description": description,
            }
        )
        # Keep only last 100 tasks
        session.today_tasks_json = json.dumps(tasks[-100:])
        db.flush()
    except Exception:
        pass


def get_recent_activities(
    db: Session,
    company_id: str,
    user_id: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    hours: int = 24,
    limit: int = 100,
) -> List[JarvisActivityEvent]:
    """Get recent activities for awareness queries."""

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = db.query(JarvisActivityEvent).filter(
        JarvisActivityEvent.company_id == company_id,
        JarvisActivityEvent.created_at >= since,
    )

    if user_id:
        query = query.filter(JarvisActivityEvent.user_id == user_id)

    if event_types:
        query = query.filter(JarvisActivityEvent.event_type.in_(event_types))

    return query.order_by(desc(JarvisActivityEvent.created_at)).limit(limit).all()


def get_user_activity_summary(
    db: Session,
    company_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get a summary of user's activity today."""

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    activities = (
        db.query(JarvisActivityEvent)
        .filter(
            JarvisActivityEvent.company_id == company_id,
            JarvisActivityEvent.user_id == user_id,
            JarvisActivityEvent.created_at >= today_start,
        )
        .all()
    )

    # Group by category
    by_category = {}
    for act in activities:
        cat = act.event_category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(
            {
                "event": act.event_name,
                "description": act.description,
                "time": act.created_at.isoformat() if act.created_at else None,
            }
        )

    return {
        "user_id": user_id,
        "total_activities": len(activities),
        "by_category": by_category,
        "first_activity": activities[0].created_at.isoformat() if activities else None,
        "last_activity": activities[-1].created_at.isoformat() if activities else None,
    }


# ── Memory System ────────────────────────────────────────────────────


def store_memory(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    category: str,
    key: str,
    value: Any,
    importance: int = 5,
    expires_at: Optional[datetime] = None,
) -> JarvisMemory:
    """Store a memory for later recall."""

    # Check if memory already exists
    existing = (
        db.query(JarvisMemory)
        .filter(
            JarvisMemory.company_id == company_id,
            JarvisMemory.user_id == user_id,
            JarvisMemory.category == category,
            JarvisMemory.memory_key == key,
        )
        .first()
    )

    if existing:
        existing.memory_value = (
            json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        )
        existing.importance = importance
        existing.expires_at = expires_at
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    memory = JarvisMemory(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        category=category,
        memory_key=key,
        memory_value=(
            json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        ),
        importance=importance,
        expires_at=expires_at,
    )
    db.add(memory)
    db.flush()
    return memory


def recall_memory(
    db: Session,
    company_id: str,
    user_id: str,
    category: Optional[str] = None,
    key: Optional[str] = None,
    limit: int = 10,
) -> List[JarvisMemory]:
    """Recall memories, optionally filtered by category/key."""

    query = db.query(JarvisMemory).filter(
        JarvisMemory.company_id == company_id,
        JarvisMemory.user_id == user_id,
        or_(
            JarvisMemory.expires_at.is_(None),
            JarvisMemory.expires_at > datetime.now(timezone.utc),
        ),
    )

    if category:
        query = query.filter(JarvisMemory.category == category)
    if key:
        query = query.filter(JarvisMemory.memory_key == key)

    memories = (
        query.order_by(
            desc(JarvisMemory.importance),
            desc(JarvisMemory.updated_at),
        )
        .limit(limit)
        .all()
    )

    # Update access count
    for mem in memories:
        mem.access_count += 1
        mem.last_accessed_at = datetime.now(timezone.utc)
    db.flush()

    return memories


def get_memory_value(
    db: Session,
    company_id: str,
    user_id: str,
    category: str,
    key: str,
    default: Any = None,
) -> Any:
    """Get a specific memory value."""

    memory = (
        db.query(JarvisMemory)
        .filter(
            JarvisMemory.company_id == company_id,
            JarvisMemory.user_id == user_id,
            JarvisMemory.category == category,
            JarvisMemory.memory_key == key,
            or_(
                JarvisMemory.expires_at.is_(None),
                JarvisMemory.expires_at > datetime.now(timezone.utc),
            ),
        )
        .first()
    )

    if not memory:
        return default

    memory.access_count += 1
    memory.last_accessed_at = datetime.now(timezone.utc)
    db.flush()

    try:
        return json.loads(memory.memory_value)
    except BaseException:
        return memory.memory_value


# ── Action Executor (Direct vs Draft) ────────────────────────────────


def should_use_draft(
    action_type: str,
    params: Dict[str, Any],
    user_confidence: str = "high",
) -> bool:
    """Determine if action should use draft-then-approve workflow.

    Rules:
    - Bulk actions = draft
    - Financial operations = draft
    - Irreversible actions = draft
    - User uncertain = draft
    - Everything else = direct
    """

    # Check if action type requires draft
    try:
        if ActionType(action_type) in DRAFT_REQUIRED_ACTIONS:
            return True
    except ValueError:
        pass  # Unknown action type, default to draft for safety
        return True

    # Check for bulk indicators in params
    if params.get("bulk", False) or params.get("recipient_count", 0) > 1:
        return True

    # Check for financial indicators
    if params.get("amount") or params.get("financial", False):
        return True

    # Check for irreversible indicators
    if params.get("irreversible", False) or action_type in ["delete", "remove"]:
        return True

    # Check user confidence
    if user_confidence == "low" or user_confidence == "uncertain":
        return True

    return False


def execute_direct_action(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    action_type: str,
    params: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Execute a direct action immediately.

    Returns: (success, result, error_message)
    """

    # Create action log
    action_log = JarvisActionLog(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        action_type=action_type,
        action_category=_get_action_category(action_type),
        execution_mode="direct",
        input_json=json.dumps(params),
        status="pending",
    )
    db.add(action_log)
    db.flush()

    try:
        # Route to appropriate handler
        result = asyncio.run(
            _execute_action_internal(
                db=db,
                company_id=company_id,
                user_id=user_id,
                action_type=action_type,
                params=params,
            )
        )

        action_log.status = "success"
        action_log.output_json = json.dumps(result)
        action_log.completed_at = datetime.now(timezone.utc)
        action_log.can_undo = _can_undo_action(action_type)
        db.flush()

        return True, result, None

    except Exception as e:
        action_log.status = "failed"
        action_log.error_message = str(e)
        action_log.completed_at = datetime.now(timezone.utc)
        db.flush()

        return False, {}, str(e)


def create_draft(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    draft_type: str,
    content: Dict[str, Any],
    recipients: Optional[List[Dict]] = None,
    subject: Optional[str] = None,
    expires_in_hours: int = 24,
) -> JarvisDraft:
    """Create a draft for user approval."""

    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    draft = JarvisDraft(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        draft_type=draft_type,
        subject=subject,
        content_json=json.dumps(content),
        recipient_count=len(recipients) if recipients else 0,
        recipients_json=json.dumps(recipients or []),
        expires_at=expires_at,
    )
    db.add(draft)
    db.flush()

    # Track activity
    track_activity(
        db=db,
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        event_type="draft",
        event_category="action",
        event_name="draft_created",
        description=f"Created {draft_type} draft for review",
        metadata={"draft_id": str(draft.id)},
    )

    return draft


def approve_and_execute_draft(
    db: Session,
    draft_id: str,
    user_id: str,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Approve and execute a pending draft."""

    draft = (
        db.query(JarvisDraft)
        .filter(
            JarvisDraft.id == draft_id,
            JarvisDraft.status == "pending",
        )
        .first()
    )

    if not draft:
        return False, {}, "Draft not found or already processed"

    if draft.expires_at and datetime.now(timezone.utc) > draft.expires_at:
        draft.status = "expired"
        db.flush()
        return False, {}, "Draft has expired"

    # Mark as approved
    draft.status = "approved"
    draft.approved_by = user_id
    draft.approved_at = datetime.now(timezone.utc)
    db.flush()

    # Execute the draft
    try:
        content = json.loads(draft.content_json)
        recipients = json.loads(draft.recipients_json) if draft.recipients_json else []

        result = asyncio.run(
            _execute_action_internal(
                db=db,
                company_id=draft.company_id,
                user_id=draft.user_id,
                action_type=draft.draft_type,
                params={**content, "recipients": recipients},
            )
        )

        draft.status = "completed"
        draft.executed_at = datetime.now(timezone.utc)
        draft.execution_result_json = json.dumps(result)
        db.flush()

        # Create action log
        action_log = JarvisActionLog(
            session_id=draft.session_id,
            company_id=draft.company_id,
            user_id=draft.user_id,
            action_type=draft.draft_type,
            action_category=_get_action_category(draft.draft_type),
            execution_mode="draft_approved",
            draft_id=str(draft.id),
            input_json=draft.content_json,
            output_json=draft.execution_result_json,
            status="success",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(action_log)
        db.flush()

        return True, result, None

    except Exception as e:
        draft.status = "failed"
        draft.execution_result_json = json.dumps({"error": str(e)})
        db.flush()
        return False, {}, str(e)


def cancel_draft(
    db: Session,
    draft_id: str,
    user_id: str,
) -> bool:
    """Cancel a pending draft."""

    draft = (
        db.query(JarvisDraft)
        .filter(
            JarvisDraft.id == draft_id,
            JarvisDraft.status == "pending",
        )
        .first()
    )

    if not draft:
        return False

    draft.status = "cancelled"
    db.flush()
    return True


# ── Proactive Alert System ───────────────────────────────────────────


def create_alert(
    db: Session,
    company_id: str,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    suggested_action: Optional[Dict] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
) -> JarvisAlert:
    """Create a proactive alert."""

    alert = JarvisAlert(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        suggested_action_json=(
            json.dumps(suggested_action) if suggested_action else None
        ),
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    db.add(alert)
    db.flush()
    return alert


def get_active_alerts(
    db: Session,
    company_id: str,
    user_id: Optional[str] = None,
    min_severity: Optional[str] = None,
) -> List[JarvisAlert]:
    """Get active alerts for a company/user."""

    query = db.query(JarvisAlert).filter(
        JarvisAlert.company_id == company_id,
        JarvisAlert.status == "active",
    )

    if user_id:
        query = query.filter(
            or_(
                JarvisAlert.user_id == user_id,
                JarvisAlert.user_id.is_(None),  # Company-wide alerts
            )
        )

    if min_severity:
        severity_order = ["low", "medium", "high", "critical"]
        severity_idx = (
            severity_order.index(min_severity) if min_severity in severity_order else 0
        )
        allowed_severities = severity_order[severity_idx:]
        query = query.filter(JarvisAlert.severity.in_(allowed_severities))

    return query.order_by(
        # Sort by severity first (critical = highest)
        JarvisAlert.severity.desc(),
        JarvisAlert.created_at.desc(),
    ).all()


def acknowledge_alert(
    db: Session,
    alert_id: str,
    user_id: str,
) -> Optional[JarvisAlert]:
    """Acknowledge an alert."""

    alert = (
        db.query(JarvisAlert)
        .filter(
            JarvisAlert.id == alert_id,
        )
        .first()
    )

    if not alert:
        return None

    alert.status = "acknowledged"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.flush()
    return alert


def dismiss_alert(
    db: Session,
    alert_id: str,
    user_id: str,
) -> Optional[JarvisAlert]:
    """Dismiss an alert."""

    alert = (
        db.query(JarvisAlert)
        .filter(
            JarvisAlert.id == alert_id,
        )
        .first()
    )

    if not alert:
        return None

    alert.status = "dismissed"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.flush()
    return alert


# ── System Status Awareness ──────────────────────────────────────────


def get_system_overview(
    db: Session,
    company_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get comprehensive system overview for Jarvis context."""

    # Get today's activities
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    activities_today = (
        db.query(JarvisActivityEvent)
        .filter(
            JarvisActivityEvent.company_id == company_id,
            JarvisActivityEvent.created_at >= today_start,
        )
        .count()
    )

    # Get active alerts
    active_alerts = get_active_alerts(db, company_id, user_id)

    # Get pending drafts
    pending_drafts = (
        db.query(JarvisDraft)
        .filter(
            JarvisDraft.company_id == company_id,
            JarvisDraft.user_id == user_id,
            JarvisDraft.status == "pending",
        )
        .count()
    )

    # Get recent errors
    recent_errors = (
        db.query(JarvisActivityEvent)
        .filter(
            JarvisActivityEvent.company_id == company_id,
            JarvisActivityEvent.event_type == "error",
            JarvisActivityEvent.created_at >= today_start,
        )
        .count()
    )

    return {
        "company_id": company_id,
        "activities_today": activities_today,
        "active_alerts": len(active_alerts),
        "alerts_by_severity": {
            "critical": len([a for a in active_alerts if a.severity == "critical"]),
            "high": len([a for a in active_alerts if a.severity == "high"]),
            "medium": len([a for a in active_alerts if a.severity == "medium"]),
            "low": len([a for a in active_alerts if a.severity == "low"]),
        },
        "pending_drafts": pending_drafts,
        "recent_errors": recent_errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Helper Functions ──────────────────────────────────────────────────


async def _execute_action_internal(
    db: Session,
    company_id: str,
    user_id: str,
    action_type: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Internal action execution router."""

    # Communication actions
    if action_type in [ActionType.SEND_SMS.value, "send_sms"]:
        return await _execute_send_sms(db, company_id, user_id, params)

    if action_type in [ActionType.SEND_EMAIL.value, "send_email"]:
        return await _execute_send_email(db, company_id, user_id, params)

    if action_type in [ActionType.BULK_SMS.value, "bulk_sms"]:
        return await _execute_bulk_sms(db, company_id, user_id, params)

    if action_type in [ActionType.BULK_EMAIL.value, "bulk_email"]:
        return await _execute_bulk_email(db, company_id, user_id, params)

    # AI Control actions
    if action_type in [ActionType.PAUSE_AI.value, "pause_ai"]:
        return await _execute_pause_ai(db, company_id, user_id, params)

    if action_type in [ActionType.RESUME_AI.value, "resume_ai"]:
        return await _execute_resume_ai(db, company_id, user_id, params)

    if action_type in [ActionType.UNDO_ACTION.value, "undo_action"]:
        return await _execute_undo(db, company_id, user_id, params)

    # Default: acknowledge but no action
    return {"acknowledged": True, "action_type": action_type}


async def _execute_send_sms(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Send SMS via Twilio."""

    to = params.get("to") or params.get("phone")
    message = params.get("message") or params.get("body")

    if not to or not message:
        raise ValidationError(message="Missing 'to' or 'message' parameter")

    try:
        from app.services.sms_channel_service import SMSChannelService

        sms_service = SMSChannelService(db, company_id)
        result = await sms_service.send_sms(to=to, message=message)
        return {"success": True, "message_sid": result.get("sid"), "to": to}
    except Exception as e:
        # Try Twilio directly
        try:
            from app.core.config import get_settings
            from app.providers.sms.twilio import TwilioSMSProvider

            settings = get_settings()
            provider = TwilioSMSProvider(
                account_sid=settings.TWILIO_ACCOUNT_SID,
                auth_token=settings.TWILIO_AUTH_TOKEN,
                from_number=settings.TWILIO_PHONE_NUMBER,
            )
            result = provider.send(to=to, message=message)
            return {"success": True, "message_sid": result.get("sid"), "to": to}
        except Exception as e2:
            return {"success": False, "error": str(e2)}


async def _execute_send_email(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Send email via Brevo."""

    to = params.get("to") or params.get("email")
    subject = params.get("subject", "Message from PARWA")
    body = params.get("body") or params.get("message") or params.get("html_content")

    if not to or not body:
        raise ValidationError(message="Missing 'to' or 'body' parameter")

    try:
        from app.services.email_service import send_email

        send_email(to=to, subject=subject, html_content=body)
        return {"success": True, "to": to, "subject": subject}
    except Exception as e:
        # Try Brevo directly
        try:
            from app.core.config import get_settings
            from app.providers.email.brevo import BrevoEmailProvider

            settings = get_settings()
            provider = BrevoEmailProvider(
                api_key=settings.BREVO_API_KEY,
                from_email=settings.BREVO_FROM_EMAIL,
            )
            result = provider.send(to=to, subject=subject, html_content=body)
            return {"success": True, "message_id": result.get("messageId"), "to": to}
        except Exception as e2:
            return {"success": False, "error": str(e2)}


async def _execute_bulk_sms(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Send bulk SMS (approved from draft)."""

    recipients = params.get("recipients", [])
    message = params.get("message") or params.get("body")

    if not recipients or not message:
        raise ValidationError(message="Missing 'recipients' or 'message'")

    results = []
    for recipient in recipients:
        phone = recipient.get("phone") or recipient.get("to")
        if phone:
            try:
                result = await _execute_send_sms(
                    db,
                    company_id,
                    user_id,
                    {
                        "to": phone,
                        "message": message,
                    },
                )
                results.append(
                    {"phone": phone, "success": result.get("success", False)}
                )
            except Exception as e:
                results.append({"phone": phone, "success": False, "error": str(e)})

    success_count = len([r for r in results if r.get("success")])
    return {
        "total": len(recipients),
        "successful": success_count,
        "failed": len(recipients) - success_count,
        "results": results,
    }


async def _execute_bulk_email(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Send bulk email (approved from draft)."""

    recipients = params.get("recipients", [])
    subject = params.get("subject", "Message from PARWA")
    body = params.get("body") or params.get("html_content")

    if not recipients or not body:
        raise ValidationError(message="Missing 'recipients' or 'body'")

    results = []
    for recipient in recipients:
        email = recipient.get("email") or recipient.get("to")
        if email:
            try:
                result = await _execute_send_email(
                    db,
                    company_id,
                    user_id,
                    {
                        "to": email,
                        "subject": subject,
                        "body": body,
                    },
                )
                results.append(
                    {"email": email, "success": result.get("success", False)}
                )
            except Exception as e:
                results.append({"email": email, "success": False, "error": str(e)})

    success_count = len([r for r in results if r.get("success")])
    return {
        "total": len(recipients),
        "successful": success_count,
        "failed": len(recipients) - success_count,
        "results": results,
    }


async def _execute_pause_ai(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Pause AI operations."""

    reason = params.get("reason", "User requested pause")
    scope = params.get("scope", "all")  # 'all', 'sms', 'email', 'chat'

    try:
        from app.services.pause_service import PauseService

        pause_service = PauseService(db, company_id)
        await pause_service.pause(scope=scope, reason=reason, paused_by=user_id)
        return {"success": True, "scope": scope, "reason": reason}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _execute_resume_ai(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Resume AI operations."""

    scope = params.get("scope", "all")

    try:
        from app.services.pause_service import PauseService

        pause_service = PauseService(db, company_id)
        await pause_service.resume(scope=scope)
        return {"success": True, "scope": scope}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _execute_undo(
    db: Session,
    company_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Undo the last action."""

    action_id = params.get("action_id")

    if action_id:
        action = (
            db.query(JarvisActionLog)
            .filter(
                JarvisActionLog.id == action_id,
                JarvisActionLog.company_id == company_id,
            )
            .first()
        )
    else:
        # Get last undoable action
        action = (
            db.query(JarvisActionLog)
            .filter(
                JarvisActionLog.company_id == company_id,
                JarvisActionLog.can_undo,
                JarvisActionLog.status == "success",
                JarvisActionLog.undone_at.is_(None),
            )
            .order_by(desc(JarvisActionLog.created_at))
            .first()
        )

    if not action:
        return {"success": False, "error": "No undoable action found"}

    # Mark as undone
    action.status = "undone"
    action.undone_at = datetime.now(timezone.utc)
    action.undone_by = user_id
    db.flush()

    return {
        "success": True,
        "undone_action_id": str(action.id),
        "action_type": action.action_type,
    }


def _get_action_category(action_type: str) -> str:
    """Get category for an action type."""

    communication = {"send_sms", "send_email", "bulk_sms", "bulk_email"}
    ai_control = {"pause_ai", "resume_ai", "undo_action", "switch_mode"}
    user_mgmt = {"invite_team", "change_role", "reset_password"}
    integration = {"connect_integration", "test_connection", "sync_data"}
    knowledge = {"upload_document", "search_documents"}
    settings = {"update_settings", "set_threshold"}

    if action_type in communication:
        return "communication"
    if action_type in ai_control:
        return "ai_control"
    if action_type in user_mgmt:
        return "user_management"
    if action_type in integration:
        return "integration"
    if action_type in knowledge:
        return "knowledge"
    if action_type in settings:
        return "settings"
    return "other"


def _can_undo_action(action_type: str) -> bool:
    """Check if an action can be undone."""

    # Undoable actions
    undoable = {
        "pause_ai",
        "resume_ai",
        "update_settings",
        "send_sms",
        "send_email",  # Can mark for review
    }

    # Not undoable
    not_undoable = {
        "bulk_sms",
        "bulk_email",  # Already sent
        "delete",
        "remove",
    }

    return action_type in undoable


# ── Export All ────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "VariantTier",
    "AlertSeverity",
    "ActionType",
    # Constants
    "TIER_FEATURES",
    "DRAFT_REQUIRED_ACTIONS",
    # Session
    "get_or_create_session",
    # Activity Tracking
    "track_activity",
    "get_recent_activities",
    "get_user_activity_summary",
    # Memory
    "store_memory",
    "recall_memory",
    "get_memory_value",
    # Action Executor
    "should_use_draft",
    "execute_direct_action",
    "create_draft",
    "approve_and_execute_draft",
    "cancel_draft",
    # Alerts
    "create_alert",
    "get_active_alerts",
    "acknowledge_alert",
    "dismiss_alert",
    # System
    "get_system_overview",
]
