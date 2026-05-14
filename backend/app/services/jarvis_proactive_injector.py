"""
PARWA Jarvis Proactive Alert Injector (Phase 2.4)

The bridge that makes Jarvis PROACTIVE. When the awareness engine detects
a critical or emergency issue, this injector pushes the alert into the
CC chat session as a proactive message — so the user sees it in their
chat stream, not just via API polling.

Architecture:
  Awareness Engine tick → creates alert
      → ProactiveInjector.should_inject(alert) → True/False
      → ProactiveInjector.inject(alert, session) → creates proactive message
      → EventDispatcher.dispatch("jarvis:activity", payload) → WebSocket push

Injection Rules:
  - Only inject alerts with severity >= warning
  - Only inject into active customer_care sessions
  - Rate-limit: max 1 proactive message per session per 60 seconds
  - Dedup: don't inject the same alert_type twice within cooldown
  - Emergency alerts bypass rate-limit

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models.jarvis import JarvisSession, JarvisMessage
from database.models.jarvis_cc import JarvisProactiveAlert
from app.logger import get_logger

logger = get_logger("jarvis_proactive_injector")


# ── Constants ──────────────────────────────────────────────────────

# Minimum severity to inject into chat (info alerts are NOT injected)
INJECT_MIN_SEVERITY = "warning"

# Severity ordering for comparison
SEVERITY_ORDER = {
    "info": 0,
    "warning": 1,
    "critical": 2,
    "emergency": 3,
}

# Rate limit: max proactive messages per session per N seconds
RATE_LIMIT_SECONDS = 60

# Max proactive_alerts stored in session context
MAX_PROACTIVE_ALERTS_CONTEXT = 10

# Alert types that bypass rate limiting
RATE_LIMIT_BYPASS_TYPES = {"emergency_state_change", "system_down"}

__all__ = [
    "should_inject_alert",
    "inject_proactive_alert",
    "inject_tick_summary",
    "get_proactive_message_content",
    "rate_limit_check",
]


# ══════════════════════════════════════════════════════════════════
# INJECTION DECISION
# ══════════════════════════════════════════════════════════════════


def should_inject_alert(
    alert: JarvisProactiveAlert,
    session_context: Dict[str, Any],
) -> bool:
    """Determine whether an alert should be injected into the CC chat.

    Injection rules:
      1. Severity must be >= warning
      2. Session must be active
      3. Rate limit must not be exceeded (unless bypass)
      4. Alert must not be a duplicate within cooldown

    Args:
        alert: The proactive alert to evaluate.
        session_context: The current CC session context dict.

    Returns:
        True if the alert should be injected into chat.
    """
    # Rule 1: Severity check
    alert_sev = SEVERITY_ORDER.get(alert.severity, 0)
    min_sev = SEVERITY_ORDER.get(INJECT_MIN_SEVERITY, 1)
    if alert_sev < min_sev:
        return False

    # Rule 2: Session active check
    if not session_context.get("awareness_enabled", False):
        return False

    # Rule 3: Rate limit check (emergency bypasses)
    if alert.alert_type not in RATE_LIMIT_BYPASS_TYPES:
        last_inject = session_context.get("last_proactive_injection_at")
        if last_inject:
            try:
                last_time = datetime.fromisoformat(last_inject)
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
                if elapsed < RATE_LIMIT_SECONDS:
                    logger.debug(
                        "proactive_rate_limited: session=%s, alert=%s, "
                        "elapsed=%.0fs, limit=%ds",
                        alert.session_id, alert.alert_type,
                        elapsed, RATE_LIMIT_SECONDS,
                    )
                    return False
            except (ValueError, TypeError):
                pass  # Invalid timestamp — allow injection

    # Rule 4: Dedup within cooldown
    recent_alerts = session_context.get("proactive_alerts", [])
    if isinstance(recent_alerts, list):
        for prev in recent_alerts[-5:]:  # Check last 5
            if isinstance(prev, dict):
                if prev.get("alert_type") == alert.alert_type:
                    # Same type injected recently — skip
                    prev_at = prev.get("injected_at")
                    if prev_at:
                        try:
                            prev_time = datetime.fromisoformat(prev_at)
                            if prev_time.tzinfo is None:
                                prev_time = prev_time.replace(tzinfo=timezone.utc)
                            elapsed = (datetime.now(timezone.utc) - prev_time).total_seconds()
                            if elapsed < RATE_LIMIT_SECONDS * 2:
                                logger.debug(
                                    "proactive_dedup: session=%s, type=%s",
                                    alert.session_id, alert.alert_type,
                                )
                                return False
                        except (ValueError, TypeError):
                            pass

    return True


# ══════════════════════════════════════════════════════════════════
# PROACTIVE MESSAGE INJECTION
# ══════════════════════════════════════════════════════════════════


def inject_proactive_alert(
    db: Session,
    alert: JarvisProactiveAlert,
    session_id: str,
    company_id: str,
    user_id: str,
) -> Optional[JarvisMessage]:
    """Inject a proactive alert as a message into the CC chat session.

    This is the key function that bridges awareness → chat. When the
    awareness engine creates a critical/emergency alert, this function
    creates a JarvisMessage in the session so the user sees it in
    their chat stream.

    Flow:
      1. Check if alert should be injected (severity, rate limit)
      2. Build proactive message content
      3. Create JarvisMessage with type "proactive_alert"
      4. Update session context (last injection time, alert list)
      5. Return the created message

    Args:
        db: SQLAlchemy session.
        alert: The proactive alert to inject.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        user_id: User ID for security.

    Returns:
        JarvisMessage if injected, None if skipped.
    """
    try:
        # Get session and context
        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
                JarvisSession.is_active.is_(True),
            )
            .first()
        )
        if not session:
            logger.warning(
                "proactive_inject_no_session: session=%s, company=%s",
                session_id, company_id,
            )
            return None

        ctx = _safe_parse_json(session.context_json)

        # Check injection rules
        if not should_inject_alert(alert, ctx):
            return None

        # Build proactive message content
        content = get_proactive_message_content(alert)

        # Create JarvisMessage with proactive_alert type
        msg_metadata = {
            "alert_id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "category": alert.category,
            "action_required": alert.action_required,
            "action_url": alert.action_url,
            "injected_by": "jarvis_proactive_injector",
            "injected_at": datetime.now(timezone.utc).isoformat(),
        }

        proactive_msg = JarvisMessage(
            session_id=session_id,
            role="jarvis",
            content=content,
            message_type="proactive_alert",
            metadata_json=json.dumps(msg_metadata),
        )
        db.add(proactive_msg)

        # Update session context
        ctx["last_proactive_injection_at"] = datetime.now(timezone.utc).isoformat()
        ctx["awareness_enabled"] = True  # Flip the flag

        # Add to proactive_alerts list (keep last N)
        proactive_alerts = ctx.get("proactive_alerts", [])
        if not isinstance(proactive_alerts, list):
            proactive_alerts = []
        proactive_alerts.append({
            "alert_id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "injected_at": datetime.now(timezone.utc).isoformat(),
        })
        # Keep only last N entries
        ctx["proactive_alerts"] = proactive_alerts[-MAX_PROACTIVE_ALERTS_CONTEXT:]

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "proactive_injected: session=%s, alert=%s, type=%s, severity=%s",
            session_id, str(alert.id), alert.alert_type, alert.severity,
        )

        return proactive_msg

    except Exception:
        logger.exception(
            "proactive_inject_failed: session=%s, alert=%s",
            session_id, str(alert.id),
        )
        return None


def inject_tick_summary(
    db: Session,
    session_id: str,
    company_id: str,
    tick_result: Dict[str, Any],
    alerts_created: List[JarvisProactiveAlert],
) -> List[JarvisMessage]:
    """Inject all eligible alerts from a tick into the CC chat.

    Called after run_awareness_tick completes. Iterates through
    created alerts and injects each eligible one.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        tick_result: The result dict from run_awareness_tick.
        alerts_created: List of alerts created during the tick.

    Returns:
        List of JarvisMessage objects that were injected.
    """
    injected_messages = []

    if not alerts_created:
        return injected_messages

    # Get user_id from session
    try:
        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return injected_messages
        user_id = str(session.user_id)
    except Exception:
        return injected_messages

    # Sort alerts by severity (emergency first)
    sorted_alerts = sorted(
        alerts_created,
        key=lambda a: SEVERITY_ORDER.get(a.severity, 0),
        reverse=True,
    )

    for alert in sorted_alerts:
        msg = inject_proactive_alert(
            db=db,
            alert=alert,
            session_id=session_id,
            company_id=company_id,
            user_id=user_id,
        )
        if msg:
            injected_messages.append(msg)

    if injected_messages:
        logger.info(
            "tick_summary_injected: session=%s, total_alerts=%d, injected=%d",
            session_id, len(alerts_created), len(injected_messages),
        )

    return injected_messages


# ══════════════════════════════════════════════════════════════════
# RATE LIMIT CHECK
# ══════════════════════════════════════════════════════════════════


def rate_limit_check(
    session_context: Dict[str, Any],
    alert_type: str,
) -> bool:
    """Check if a proactive injection is rate-limited.

    Args:
        session_context: The current CC session context dict.
        alert_type: The type of alert being injected.

    Returns:
        True if injection is allowed (not rate-limited).
    """
    if alert_type in RATE_LIMIT_BYPASS_TYPES:
        return True

    last_inject = session_context.get("last_proactive_injection_at")
    if not last_inject:
        return True

    try:
        last_time = datetime.fromisoformat(last_inject)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        return elapsed >= RATE_LIMIT_SECONDS
    except (ValueError, TypeError):
        return True


# ══════════════════════════════════════════════════════════════════
# MESSAGE CONTENT BUILDER
# ══════════════════════════════════════════════════════════════════


# Template map: severity → prefix + style
_SEVERITY_TEMPLATES = {
    "warning": {
        "prefix": "⚠️",
        "tone": "Heads up",
    },
    "critical": {
        "prefix": "🔴",
        "tone": "Attention needed",
    },
    "emergency": {
        "prefix": "🚨",
        "tone": "URGENT",
    },
}


def get_proactive_message_content(alert: JarvisProactiveAlert) -> str:
    """Build human-readable proactive message content from an alert.

    The message reads like a human employee telling their manager about
    an issue — not a system notification.

    Args:
        alert: The proactive alert to format.

    Returns:
        Formatted message string.
    """
    template = _SEVERITY_TEMPLATES.get(
        alert.severity,
        {"prefix": "📢", "tone": "Note"},
    )

    parts = [
        f"{template['prefix']} **{template['tone']}** — {alert.title}",
        "",
        alert.message,
    ]

    # Add action items
    if alert.action_required:
        parts.append("")
        action_text = "Action required"
        if alert.action_url:
            action_text += f" — [View details]({alert.action_url})"
        parts.append(f"👉 {action_text}")

    # Add category context
    category_labels = {
        "system_health": "System Health",
        "ticket_volume": "Ticket Volume",
        "quality": "Response Quality",
        "sla_compliance": "SLA Compliance",
        "agent_pool": "Agent Pool",
        "drift": "Model Drift",
        "training": "Training",
        "billing": "Billing",
        "errors": "Error Rate",
        "subscription": "Subscription",
    }
    category_label = category_labels.get(alert.category, alert.category)
    parts.append(f"_Category: {category_label} | Severity: {alert.severity}_")

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: str) -> dict:
    """Safely parse JSON string to dict."""
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}
