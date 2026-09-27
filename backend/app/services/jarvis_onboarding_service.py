"""
PARWA Jarvis Onboarding Service — The Pre-Purchase Interview Engine

This is the backend brain for the onboarding Jarvis experience. While the
frontend handles the chat UI and AI routing, this service handles:

  1. SESSION MANAGEMENT — Create/persist/resume onboarding sessions in DB
  2. ACTIVITY LOGGING — Log every onboarding action to the Activity Store
     so the awareness engine gains visibility into the onboarding funnel
  3. STAGE TRACKING — Track the user's progress through the onboarding
     stages (welcome → discovery → variant → demo → verification → payment → handoff)
  4. CONTEXT BRIDGE — Pass onboarding context to the CC Jarvis after
     handoff, so CC Jarvis KNOWS what happened during onboarding
  5. AWARENESS FEED — Feed onboarding-specific data into the awareness
     engine as Domain 11, so CC Jarvis can see:
       - How the user came in (entry_source, referral)
       - What variant they tried (demo mode)
       - What concerns they raised
       - Whether they completed payment
       - What stage they dropped off at

Architecture:
  Frontend (Next.js)                    Backend (FastAPI)
  ┌──────────────────┐                 ┌──────────────────────┐
  │ /jarvis page     │──── POST ──────→│ onboarding service   │
  │ useJarvisChat    │                 │   create_session()   │
  │                  │                 │   log_action()       │
  │ Chat messages    │──── PATCH ─────→│   update_context()   │
  │ Stage changes    │                 │   advance_stage()    │
  │                  │                 │                      │
  │ Payment complete │──── POST ──────→│   complete_payment() │
  │ Handoff trigger  │──── POST ──────→│   execute_handoff()  │
  └──────────────────┘                 │                      │
                                       │   → Activity Store   │
                                       │   → Awareness Engine │
                                       │   → CC Session       │
                                       └──────────────────────┘

Why This Exists:
  Previously, onboarding was 100% frontend (in-memory sessions, no DB).
  This meant:
    - CC Jarvis had ZERO awareness of what happened during onboarding
    - Activity Store had no onboarding events
    - Awareness Engine couldn't track onboarding funnel metrics
    - If the user refreshed, session was lost
    - After handoff, CC Jarvis started from scratch

  Now, the onboarding service bridges this gap. Every onboarding action
  is logged to the Activity Store, and the awareness engine can see it
  as Domain 11 data. When the user completes onboarding and enters the
  CC dashboard, CC Jarvis ALREADY KNOWS their history.

Control vs Awareness Boundary:
  - Onboarding Jarvis CAN: guide, recommend, demo, verify email, process payment
  - Onboarding Jarvis CANNOT: manage production tickets, change billing, pause AI
  - Onboarding Jarvis SHOULD: log everything to Activity Store for CC awareness

BC-001: company_id first parameter on all public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.jarvis import JarvisSession, JarvisMessage

logger = get_logger("jarvis_onboarding_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Onboarding stages (matches frontend useJarvisChat stages)
ONBOARDING_STAGES = [
    "welcome",
    "discovery",
    "onboarding_questions",
    "variant_selection",
    "objection_handling",
    "pricing",
    "demo",
    "verification",
    "payment",
    "bill_review",
    "handoff",
]

# Stage advancement rules — which stages can advance to which
STAGE_TRANSITIONS = {
    "welcome": ["discovery", "onboarding_questions"],
    "discovery": ["onboarding_questions", "variant_selection"],
    "onboarding_questions": ["variant_selection", "pricing"],
    "variant_selection": ["objection_handling", "pricing", "demo"],
    "objection_handling": ["variant_selection", "pricing", "demo"],
    "pricing": ["verification", "payment", "demo"],
    "demo": ["verification", "pricing", "variant_selection"],
    "verification": ["payment", "bill_review"],
    "payment": ["bill_review", "handoff"],
    "bill_review": ["payment", "handoff"],
    "handoff": [],  # Terminal stage
}

# Entry sources that map to awareness categories
ENTRY_SOURCE_CATEGORIES = {
    "direct": "organic",
    "pricing": "high_intent",
    "roi": "high_intent",
    "demo": "high_intent",
    "features": "medium_intent",
    "models_page": "high_intent",
    "industry_e-commerce": "vertical",
    "industry_saas": "vertical",
    "industry_logistics": "vertical",
    "industry_healthcare": "vertical",
    "referral": "referral",
}

# Free message limit for onboarding sessions
FREE_MESSAGE_LIMIT = 20
DEMO_PACK_MESSAGE_LIMIT = 500
DEMO_PACK_CALL_SECONDS = 180  # 3 minutes

__all__ = [
    # Session management
    "create_onboarding_session",
    "get_onboarding_session",
    "resume_onboarding_session",
    "deactivate_session",
    # Context management
    "update_onboarding_context",
    "advance_stage",
    "get_current_stage",
    # Activity logging
    "log_onboarding_action",
    "log_onboarding_message",
    # Stage-specific actions
    "record_email_verification",
    "record_payment",
    "record_demo_call",
    "execute_handoff",
    # Analytics & awareness
    "get_onboarding_funnel_metrics",
    "get_onboarding_awareness",
    "build_cc_context_from_onboarding",
]


# ══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_onboarding_session(
    db: Session,
    company_id: str,
    user_id: Optional[str] = None,
    entry_source: str = "direct",
    entry_params: Optional[Dict[str, Any]] = None,
    referral_source: Optional[str] = None,
    industry: Optional[str] = None,
    preselected_variant: Optional[str] = None,
    preselected_plan: Optional[str] = None,
) -> JarvisSession:
    """Create a new onboarding session in the database.

    This is the first thing that happens when a user lands on /jarvis.
    The session is persisted so it survives page refreshes and so the
    awareness engine can track onboarding progress.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001 tenant scoping.
        user_id: Optional user ID (may not exist yet for prospects).
        entry_source: Where the user came from (direct, pricing, roi, etc.).
        entry_params: URL params from the entry point.
        referral_source: Referral UTM source.
        industry: Pre-detected industry.
        preselected_variant: Variant the user pre-selected.
        preselected_plan: Plan the user pre-selected.

    Returns:
        JarvisSession ORM instance for the onboarding session.
    """
    try:
        now = datetime.now(timezone.utc)

        # Build initial context
        context = {
            "session_type": "onboarding",
            "entry_source": entry_source,
            "entry_params": entry_params or {},
            "referral_source": referral_source or "",
            "industry": industry,
            "preselected_variant": preselected_variant,
            "preselected_plan": preselected_plan,
            "selected_variants": [preselected_variant] if preselected_variant else [],
            "detected_stage": "welcome",
            "stage_history": ["welcome"],
            "pages_visited": [],
            "roi_result": None,
            "demo_topics": [],
            "concerns_raised": [],
            "business_email": None,
            "email_verified": False,
            "payment_data": None,
            "bill_summary": None,
            "handoff_completed": False,
            "message_count": 0,
            "remaining_messages": FREE_MESSAGE_LIMIT,
            "pack_type": "free",
            "awareness_enabled": False,  # Will be enabled after handoff
            "onboarding_created_at": now.isoformat(),
        }

        # Determine intent category for awareness
        intent_category = ENTRY_SOURCE_CATEGORIES.get(entry_source, "organic")
        context["intent_category"] = intent_category

        session = JarvisSession(
            company_id=company_id,
            user_id=user_id,
            session_type="onboarding",
            pack_type="free",
            is_active=True,
            context_json=json.dumps(context),
        )
        db.add(session)
        db.flush()

        # Log to Activity Store — this is KEY for awareness
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=str(session.id),
            action="session_created",
            category="onboarding",
            details={
                "entry_source": entry_source,
                "intent_category": intent_category,
                "industry": industry,
                "preselected_variant": preselected_variant,
                "preselected_plan": preselected_plan,
                "referral_source": referral_source,
            },
            importance="medium",
        )

        logger.info(
            "onboarding_session_created: id=%s, company=%s, entry=%s, "
            "industry=%s, variant=%s, intent=%s",
            session.id, company_id, entry_source,
            industry, preselected_variant, intent_category,
        )

        return session

    except Exception:
        logger.exception(
            "create_onboarding_session_failed: company=%s, entry=%s",
            company_id, entry_source,
        )
        raise


def get_onboarding_session(
    db: Session,
    session_id: str,
    company_id: str,
) -> Optional[JarvisSession]:
    """Get an onboarding session by ID.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.

    Returns:
        JarvisSession or None.
    """
    try:
        return (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
                JarvisSession.session_type == "onboarding",
            )
            .first()
        )
    except Exception:
        logger.exception(
            "get_onboarding_session_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return None


def resume_onboarding_session(
    db: Session,
    session_id: str,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Resume an existing onboarding session.

    Called when a user returns to /jarvis after leaving. Returns the
    session context so the frontend can restore the conversation state.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.

    Returns:
        Dict with session context, messages, and stage info, or None.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return None

        if not session.is_active:
            logger.info(
                "onboarding_session_inactive: session=%s, company=%s",
                session_id, company_id,
            )
            return None

        ctx = _safe_parse_json(session.context_json)

        # Get recent messages
        messages = (
            db.query(JarvisMessage)
            .filter(JarvisMessage.session_id == session_id)
            .order_by(JarvisMessage.created_at.desc())
            .limit(20)
            .all()
        )
        messages = list(reversed(messages))

        # Log resume action
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="session_resumed",
            category="onboarding",
            details={
                "stage": ctx.get("detected_stage", "welcome"),
                "message_count": ctx.get("message_count", 0),
            },
            importance="low",
        )

        return {
            "session_id": str(session.id),
            "context": ctx,
            "stage": ctx.get("detected_stage", "welcome"),
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "message_type": m.message_type,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
            "is_active": session.is_active,
            "pack_type": session.pack_type,
            "message_count": ctx.get("message_count", 0),
            "remaining_messages": ctx.get("remaining_messages", FREE_MESSAGE_LIMIT),
        }

    except Exception:
        logger.exception(
            "resume_onboarding_session_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return None


def deactivate_session(
    db: Session,
    session_id: str,
    company_id: str,
    reason: str = "user_left",
) -> bool:
    """Deactivate an onboarding session.

    Called when the user closes the chat, navigates away, or the session
    times out. Logs the deactivation to the Activity Store so the awareness
    engine can track drop-off points.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        reason: Why the session was deactivated.

    Returns:
        True if deactivated successfully.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return False

        ctx = _safe_parse_json(session.context_json)

        session.is_active = False
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log drop-off for funnel analysis
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="session_deactivated",
            category="onboarding",
            details={
                "reason": reason,
                "stage_at_deactivation": ctx.get("detected_stage", "welcome"),
                "message_count": ctx.get("message_count", 0),
                "email_verified": ctx.get("email_verified", False),
                "payment_completed": ctx.get("payment_data") is not None,
                "handoff_completed": ctx.get("handoff_completed", False),
            },
            importance="high",
        )

        logger.info(
            "onboarding_session_deactivated: session=%s, company=%s, "
            "reason=%s, stage=%s",
            session_id, company_id, reason,
            ctx.get("detected_stage", "welcome"),
        )

        return True

    except Exception:
        logger.exception(
            "deactivate_session_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return False


# ══════════════════════════════════════════════════════════════════
# CONTEXT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def update_onboarding_context(
    db: Session,
    session_id: str,
    company_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update the onboarding session context.

    This is called whenever the frontend detects a context change —
    like the user selecting a variant, calculating ROI, raising a
    concern, etc. Every update is also logged to the Activity Store.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        updates: Dict of context fields to update.

    Returns:
        Updated context dict, or None on failure.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return None

        ctx = _safe_parse_json(session.context_json)

        # Track what changed for activity logging
        changes = {}
        for key, value in updates.items():
            old_value = ctx.get(key)
            if old_value != value:
                changes[key] = {
                    "from": old_value,
                    "to": value,
                }
                ctx[key] = value

        # Update stage history if stage changed
        if "detected_stage" in updates:
            new_stage = updates["detected_stage"]
            if new_stage != ctx.get("detected_stage"):
                stage_history = ctx.get("stage_history", [])
                if not isinstance(stage_history, list):
                    stage_history = []
                stage_history.append(new_stage)
                ctx["stage_history"] = stage_history

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log significant context changes to Activity Store
        if changes:
            significant_keys = {
                "industry", "selected_variants", "selected_plan",
                "concerns_raised", "business_email", "email_verified",
                "payment_data", "detected_stage", "roi_result",
            }
            for key, change in changes.items():
                if key in significant_keys:
                    log_onboarding_action(
                        db=db,
                        company_id=company_id,
                        session_id=session_id,
                        action=f"context_{key}_changed",
                        category="onboarding",
                        details={
                            "field": key,
                            "old_value": change["from"],
                            "new_value": change["to"],
                        },
                        importance="medium" if key in (
                            "detected_stage", "email_verified", "payment_data"
                        ) else "low",
                    )

        return ctx

    except Exception:
        logger.exception(
            "update_onboarding_context_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return None


def advance_stage(
    db: Session,
    session_id: str,
    company_id: str,
    new_stage: str,
    reason: Optional[str] = None,
) -> Optional[str]:
    """Advance the onboarding session to a new stage.

    Validates that the transition is allowed based on STAGE_TRANSITIONS.
    Logs the stage change to the Activity Store for funnel tracking.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        new_stage: The stage to advance to.
        reason: Why the stage is advancing.

    Returns:
        The new stage if advanced, or the current stage if not allowed.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return None

        ctx = _safe_parse_json(session.context_json)
        current_stage = ctx.get("detected_stage", "welcome")

        # Validate stage transition
        allowed_next = STAGE_TRANSITIONS.get(current_stage, [])
        if new_stage not in allowed_next and new_stage != current_stage:
            # Allow any forward movement for flexibility
            # (frontend may detect stages out of order)
            current_idx = ONBOARDING_STAGES.index(current_stage) if current_stage in ONBOARDING_STAGES else 0
            new_idx = ONBOARDING_STAGES.index(new_stage) if new_stage in ONBOARDING_STAGES else 0
            if new_idx < current_idx:
                logger.warning(
                    "stage_regression_blocked: session=%s, from=%s, to=%s",
                    session_id, current_stage, new_stage,
                )
                return current_stage

        # Update context
        ctx["detected_stage"] = new_stage
        stage_history = ctx.get("stage_history", [])
        if isinstance(stage_history, list):
            stage_history.append(new_stage)
            ctx["stage_history"] = stage_history

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log stage advancement
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="stage_advanced",
            category="onboarding",
            details={
                "from_stage": current_stage,
                "to_stage": new_stage,
                "reason": reason or "auto_detected",
            },
            importance="medium",
        )

        logger.info(
            "onboarding_stage_advanced: session=%s, company=%s, "
            "%s → %s, reason=%s",
            session_id, company_id, current_stage, new_stage, reason,
        )

        return new_stage

    except Exception:
        logger.exception(
            "advance_stage_failed: session=%s, company=%s, stage=%s",
            session_id, company_id, new_stage,
        )
        return None


def get_current_stage(
    db: Session,
    session_id: str,
    company_id: str,
) -> str:
    """Get the current onboarding stage for a session.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.

    Returns:
        Current stage string, defaults to "welcome".
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return "welcome"
        ctx = _safe_parse_json(session.context_json)
        return ctx.get("detected_stage", "welcome")
    except Exception:
        return "welcome"


# ══════════════════════════════════════════════════════════════════
# ACTIVITY LOGGING — Bridge to Activity Store
# ══════════════════════════════════════════════════════════════════


def log_onboarding_action(
    db: Session,
    company_id: str,
    session_id: str,
    action: str,
    category: str = "onboarding",
    details: Optional[Dict[str, Any]] = None,
    importance: str = "low",
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> Optional[Any]:
    """Log an onboarding action to the Activity Store.

    This is the KEY bridge between onboarding and awareness. Every
    onboarding action is logged here, and the awareness engine reads
    it through the Activity Store (Domain 8).

    This means CC Jarvis can "see" what happened during onboarding,
    even though onboarding and CC are separate systems.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        action: What happened (e.g., "session_created", "stage_advanced").
        category: Activity category (defaults to "onboarding").
        details: Structured details dict.
        importance: How important this event is.
        actor_type: Who caused the action.
        actor_id: Actor ID.
        entity_type: Type of entity affected.
        entity_id: ID of entity affected.

    Returns:
        ActivityLog instance or None on failure (BC-008).
    """
    try:
        from app.services.activity_store import log_activity

        # Enrich details with onboarding context
        enriched_details = details or {}
        enriched_details["_source"] = "jarvis_onboarding_service"
        enriched_details["session_id"] = session_id

        return log_activity(
            db=db,
            company_id=company_id,
            category=category,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            label=f"Onboarding: {action}",
            entity_type=entity_type or "onboarding_session",
            entity_id=entity_id or session_id,
            session_id=session_id,
            details=enriched_details,
            importance=importance,
        )

    except Exception:
        logger.debug(
            "log_onboarding_action_failed: session=%s, action=%s",
            session_id, action,
            exc_info=True,
        )
        return None


def log_onboarding_message(
    db: Session,
    session_id: str,
    company_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisMessage]:
    """Log a chat message during onboarding to the DB.

    This persists messages so they survive page refreshes and so the
    awareness engine can read conversation context.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        role: Message role (user, jarvis, system).
        content: Message content.
        message_type: Message type (text, proactive_alert, etc.).
        metadata: Optional metadata dict.

    Returns:
        JarvisMessage instance or None on failure.
    """
    try:
        msg = JarvisMessage(
            session_id=session_id,
            role=role,
            content=content[:5000],  # Safety truncate
            message_type=message_type,
            metadata_json=json.dumps(metadata or {}),
        )
        db.add(msg)

        # Update message count in session context
        session = get_onboarding_session(db, session_id, company_id)
        if session:
            ctx = _safe_parse_json(session.context_json)
            ctx["message_count"] = ctx.get("message_count", 0) + 1
            # Decrement remaining for user messages
            if role == "user":
                remaining = ctx.get("remaining_messages", FREE_MESSAGE_LIMIT)
                ctx["remaining_messages"] = max(0, remaining - 1)
            session.context_json = json.dumps(ctx)
            session.updated_at = datetime.now(timezone.utc)

        db.flush()

        # Log to Activity Store (only user messages — jarvis messages are too noisy)
        if role == "user":
            log_onboarding_action(
                db=db,
                company_id=company_id,
                session_id=session_id,
                action="user_message_sent",
                category="onboarding",
                details={
                    "message_length": len(content),
                    "message_type": message_type,
                },
                importance="low",
                actor_type="user",
            )

        return msg

    except Exception:
        logger.exception(
            "log_onboarding_message_failed: session=%s, role=%s",
            session_id, role,
        )
        return None


# ══════════════════════════════════════════════════════════════════
# STAGE-SPECIFIC ACTIONS
# ══════════════════════════════════════════════════════════════════


def record_email_verification(
    db: Session,
    session_id: str,
    company_id: str,
    email: str,
    verified: bool,
    otp_method: str = "email",
) -> bool:
    """Record email verification during onboarding.

    This is a HIGH-INTENT signal — the user has given their business
    email and verified it. Log to Activity Store so awareness engine
    can track verification rates.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        email: The verified email.
        verified: Whether verification succeeded.
        otp_method: How OTP was sent (email, sms).

    Returns:
        True if recorded successfully.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return False

        ctx = _safe_parse_json(session.context_json)
        ctx["business_email"] = email
        ctx["email_verified"] = verified
        ctx["otp_method"] = otp_method

        # Auto-advance stage to verification if not already past it
        current_stage = ctx.get("detected_stage", "welcome")
        if current_stage in ("welcome", "discovery", "onboarding_questions",
                             "variant_selection", "objection_handling", "pricing", "demo"):
            ctx["detected_stage"] = "verification"

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log to Activity Store — this is a HIGH-INTENT signal
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="email_verified" if verified else "email_verification_failed",
            category="onboarding",
            details={
                "email_domain": email.split("@")[-1] if "@" in email else "unknown",
                "verified": verified,
                "otp_method": otp_method,
            },
            importance="high" if verified else "medium",
        )

        logger.info(
            "onboarding_email_verification: session=%s, email=%s, "
            "verified=%s, company=%s",
            session_id, email[:3] + "***" + email.split("@")[-1] if "@" in email else "***",
            verified, company_id,
        )

        return True

    except Exception:
        logger.exception(
            "record_email_verification_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return False


def record_payment(
    db: Session,
    session_id: str,
    company_id: str,
    payment_data: Dict[str, Any],
) -> bool:
    """Record a completed payment during onboarding.

    This is the HIGHEST-INTENT signal — the user has paid. This triggers:
      1. Update session context with payment data
      2. Log to Activity Store (critical importance)
      3. Advance stage to bill_review or handoff
      4. Enable awareness for the session

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        payment_data: Payment details (amount, plan, variants, etc.).

    Returns:
        True if recorded successfully.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return False

        ctx = _safe_parse_json(session.context_json)

        # Update payment context
        ctx["payment_data"] = payment_data
        ctx["payment_status"] = "completed"
        ctx["pack_type"] = payment_data.get("pack_type", "paid")

        # If demo pack, update message limits
        if payment_data.get("pack_type") == "demo_pack":
            ctx["remaining_messages"] = DEMO_PACK_MESSAGE_LIMIT
            ctx["pack_type"] = "demo_pack"
        else:
            ctx["remaining_messages"] = 999999  # Unlimited for paid
            ctx["pack_type"] = "paid"

        # Enable awareness after payment
        ctx["awareness_enabled"] = True

        # Advance stage
        ctx["detected_stage"] = "bill_review"

        session.context_json = json.dumps(ctx)
        session.pack_type = ctx["pack_type"]
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log to Activity Store — CRITICAL importance
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="payment_completed",
            category="billing",
            details={
                "amount": payment_data.get("amount"),
                "currency": payment_data.get("currency", "USD"),
                "plan": payment_data.get("plan"),
                "pack_type": payment_data.get("pack_type"),
                "variants": payment_data.get("variants", []),
            },
            importance="critical",
            entity_type="payment",
        )

        logger.info(
            "onboarding_payment_completed: session=%s, company=%s, "
            "amount=%s, plan=%s",
            session_id, company_id,
            payment_data.get("amount"), payment_data.get("plan"),
        )

        return True

    except Exception:
        logger.exception(
            "record_payment_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return False


def record_demo_call(
    db: Session,
    session_id: str,
    company_id: str,
    call_data: Dict[str, Any],
) -> bool:
    """Record a demo call initiation during onboarding.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        company_id: Company ID for BC-001.
        call_data: Call details (phone, duration, etc.).

    Returns:
        True if recorded successfully.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return False

        ctx = _safe_parse_json(session.context_json)

        # Store demo call data
        demo_calls = ctx.get("demo_calls", [])
        demo_calls.append({
            "initiated_at": datetime.now(timezone.utc).isoformat(),
            "phone": call_data.get("phone", ""),
            "duration_seconds": call_data.get("duration_seconds", DEMO_PACK_CALL_SECONDS),
            "status": call_data.get("status", "initiated"),
        })
        ctx["demo_calls"] = demo_calls

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Log to Activity Store
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="demo_call_initiated",
            category="channel_voice",
            details={
                "call_duration": call_data.get("duration_seconds", DEMO_PACK_CALL_SECONDS),
                "call_status": call_data.get("status", "initiated"),
            },
            importance="high",
            entity_type="demo_call",
        )

        logger.info(
            "onboarding_demo_call: session=%s, company=%s, duration=%s",
            session_id, company_id,
            call_data.get("duration_seconds", DEMO_PACK_CALL_SECONDS),
        )

        return True

    except Exception:
        logger.exception(
            "record_demo_call_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return False


def execute_handoff(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    handoff_data: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Execute the handoff from onboarding to CC (Customer Care) Jarvis.

    This is the final step of onboarding. It:
      1. Marks the onboarding session as complete
      2. Creates a new CC session with context from onboarding
      3. Logs the handoff to Activity Store
      4. Feeds onboarding awareness data into the CC session

    The CC session starts with FULL KNOWLEDGE of what happened during
    onboarding — the user's industry, variant selection, concerns,
    payment info, etc. This is the power of the awareness bridge.

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.
        company_id: Company ID for BC-001.
        user_id: User ID for the CC session.
        handoff_data: Additional handoff context.

    Returns:
        Dict with CC session info, or None on failure.
    """
    try:
        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            return None

        ctx = _safe_parse_json(session.context_json)

        # ── Step 1: Mark onboarding as complete ──
        ctx["detected_stage"] = "handoff"
        ctx["handoff_completed"] = True
        ctx["handoff_at"] = datetime.now(timezone.utc).isoformat()
        ctx["awareness_enabled"] = True
        session.context_json = json.dumps(ctx)
        session.is_active = False
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # ── Step 2: Build CC context from onboarding ──
        cc_context = build_cc_context_from_onboarding(ctx, handoff_data)

        # ── Step 3: Create CC session ──
        from app.services.jarvis_cc_service import create_cc_session

        cc_session = create_cc_session(
            db=db,
            company_id=company_id,
            user_id=user_id,
            variant_tier=cc_context.get("variant_tier", "mini_parwa"),
            context=cc_context,
        )

        # ── Step 4: Log handoff to Activity Store ──
        log_onboarding_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action="handoff_completed",
            category="onboarding",
            details={
                "onboarding_stages_completed": ctx.get("stage_history", []),
                "industry": ctx.get("industry"),
                "selected_plan": ctx.get("selected_plan"),
                "email_verified": ctx.get("email_verified", False),
                "payment_completed": ctx.get("payment_data") is not None,
                "cc_session_id": str(cc_session.id),
            },
            importance="critical",
        )

        # ── Step 5: Run initial awareness tick for CC session ──
        try:
            from app.services.jarvis_awareness_engine import run_awareness_tick

            # Force an on_change tick to populate initial awareness
            run_awareness_tick(
                db=db,
                company_id=company_id,
                session_id=str(cc_session.id),
                user_id=user_id,
                tick_type="on_change",
            )
        except Exception:
            logger.debug(
                "cc_initial_awareness_tick_failed: cc_session=%s",
                str(cc_session.id),
                exc_info=True,
            )

        logger.info(
            "onboarding_handoff_complete: session=%s, company=%s, "
            "cc_session=%s, industry=%s, plan=%s",
            session_id, company_id, str(cc_session.id),
            ctx.get("industry"), ctx.get("selected_plan"),
        )

        return {
            "onboarding_session_id": session_id,
            "cc_session_id": str(cc_session.id),
            "context": cc_context,
            "variant_tier": cc_context.get("variant_tier", "mini_parwa"),
        }

    except Exception:
        logger.exception(
            "execute_handoff_failed: session=%s, company=%s",
            session_id, company_id,
        )
        return None


# ══════════════════════════════════════════════════════════════════
# ANALYTICS & AWARENESS
# ══════════════════════════════════════════════════════════════════


def get_onboarding_funnel_metrics(
    db: Session,
    company_id: str,
    hours: int = 24,
) -> Dict[str, Any]:
    """Get onboarding funnel metrics for a tenant.

    This is what the awareness engine uses to understand the onboarding
    pipeline health:
      - How many sessions started?
      - What's the stage distribution?
      - Where do users drop off?
      - Verification rate?
      - Payment conversion rate?

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        hours: How many hours of history to analyze.

    Returns:
        Dict with funnel metrics.
    """
    try:
        from datetime import timedelta

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get all onboarding sessions in the time range
        sessions = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.company_id == company_id,
                JarvisSession.session_type == "onboarding",
                JarvisSession.created_at >= since,
            )
            .all()
        )

        total_sessions = len(sessions)
        if total_sessions == 0:
            return {
                "company_id": company_id,
                "hours": hours,
                "total_sessions": 0,
                "message": "No onboarding sessions in this time range.",
            }

        # Calculate stage distribution
        stage_counts = {}
        entry_source_counts = {}
        verified_count = 0
        paid_count = 0
        handed_off_count = 0
        active_count = 0

        for session in sessions:
            ctx = _safe_parse_json(session.context_json)
            stage = ctx.get("detected_stage", "welcome")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

            entry = ctx.get("entry_source", "direct")
            entry_source_counts[entry] = entry_source_counts.get(entry, 0) + 1

            if ctx.get("email_verified"):
                verified_count += 1
            if ctx.get("payment_data"):
                paid_count += 1
            if ctx.get("handoff_completed"):
                handed_off_count += 1
            if session.is_active:
                active_count += 1

        # Calculate drop-off points
        stage_order = ONBOARDING_STAGES
        funnel = []
        cumulative = total_sessions
        for stage in stage_order:
            reached = sum(
                1 for s in sessions
                if stage in _safe_parse_json(s.context_json).get("stage_history", [])
            )
            funnel.append({
                "stage": stage,
                "reached": reached,
                "conversion_rate": round(reached / total_sessions * 100, 1) if total_sessions > 0 else 0,
            })

        return {
            "company_id": company_id,
            "hours": hours,
            "total_sessions": total_sessions,
            "active_sessions": active_count,
            "stage_distribution": stage_counts,
            "entry_source_distribution": entry_source_counts,
            "email_verification_rate": round(verified_count / total_sessions * 100, 1),
            "payment_conversion_rate": round(paid_count / total_sessions * 100, 1),
            "handoff_rate": round(handed_off_count / total_sessions * 100, 1),
            "funnel": funnel,
        }

    except Exception:
        logger.exception(
            "get_onboarding_funnel_metrics_failed: company=%s",
            company_id,
        )
        return {"company_id": company_id, "total_sessions": 0, "error": "metrics_failed"}


def get_onboarding_awareness(
    db: Session,
    company_id: str,
    hours: int = 1,
) -> Dict[str, Any]:
    """Get onboarding-specific awareness data for the awareness engine.

    This is Domain 11 of the awareness engine — onboarding funnel awareness.
    It reads from the Activity Store (which was populated by log_onboarding_action)
    and provides a structured summary that the awareness engine can use.

    Called by the awareness engine's collect_awareness_state() method.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        hours: How many hours of history.

    Returns:
        Dict with onboarding awareness data.
    """
    try:
        from app.services.activity_store import query_activities

        defaults: Dict[str, Any] = {
            "onboarding_sessions_last_hour": 0,
            "onboarding_active_sessions": 0,
            "onboarding_stage_distribution": {},
            "onboarding_verification_rate": 0.0,
            "onboarding_payment_rate": 0.0,
            "onboarding_handoff_rate": 0.0,
            "onboarding_top_entry_sources": [],
            "onboarding_flags": [],
        }

        # Get onboarding-specific activities
        activities, total = query_activities(
            db=db,
            company_id=company_id,
            category="onboarding",
            limit=100,
        )

        defaults["onboarding_sessions_last_hour"] = total

        # Analyze activities
        session_stages = {}
        entry_sources = {}
        verified_sessions = set()
        paid_sessions = set()
        handed_off_sessions = set()
        active_session_ids = set()

        for act in activities:
            details = _safe_parse_json(act.details_json)
            sid = details.get("session_id", "")

            if act.action == "session_created":
                entry = details.get("entry_source", "direct")
                entry_sources[entry] = entry_sources.get(entry, 0) + 1
                active_session_ids.add(sid)

            elif act.action == "stage_advanced":
                stage = details.get("to_stage", "unknown")
                session_stages[stage] = session_stages.get(stage, 0) + 1

            elif act.action == "email_verified":
                verified_sessions.add(sid)

            elif act.action == "payment_completed":
                paid_sessions.add(sid)

            elif act.action == "handoff_completed":
                handed_off_sessions.add(sid)

            elif act.action == "session_deactivated":
                active_session_ids.discard(sid)

        # Calculate rates
        total_sessions = len(active_session_ids) + len(handed_off_sessions)
        if total_sessions > 0:
            defaults["onboarding_verification_rate"] = round(
                len(verified_sessions) / total_sessions * 100, 1
            )
            defaults["onboarding_payment_rate"] = round(
                len(paid_sessions) / total_sessions * 100, 1
            )
            defaults["onboarding_handoff_rate"] = round(
                len(handed_off_sessions) / total_sessions * 100, 1
            )

        defaults["onboarding_active_sessions"] = len(active_session_ids)
        defaults["onboarding_stage_distribution"] = session_stages

        # Sort entry sources
        defaults["onboarding_top_entry_sources"] = sorted(
            entry_sources.items(), key=lambda x: x[1], reverse=True
        )[:5]

        # Auto-detect flags
        flags = []
        if total > 10 and len(verified_sessions) / max(total_sessions, 1) < 0.2:
            flags.append({
                "flag": "low_verification_rate",
                "description": "Many onboarding sessions but low email verification rate",
                "severity": "medium",
            })
        if total > 5 and len(paid_sessions) / max(total_sessions, 1) < 0.1:
            flags.append({
                "flag": "low_payment_conversion",
                "description": "Onboarding sessions not converting to payment",
                "severity": "high",
            })
        if len(active_session_ids) > 5:
            flags.append({
                "flag": "many_active_onboarding_sessions",
                "description": f"{len(active_session_ids)} active onboarding sessions in progress",
                "severity": "low",
            })

        defaults["onboarding_flags"] = flags

        return defaults

    except Exception:
        logger.exception(
            "get_onboarding_awareness_failed: company=%s",
            company_id,
        )
        return {
            "onboarding_sessions_last_hour": 0,
            "onboarding_flags": [],
        }


def build_cc_context_from_onboarding(
    onboarding_context: Dict[str, Any],
    handoff_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build CC session context from onboarding session context.

    This is the BRIDGE between onboarding and CC. When the user
    completes onboarding and enters the CC dashboard, this function
    maps onboarding context fields to CC context fields so CC Jarvis
    ALREADY KNOWS:
      - The user's industry
      - Which variant they selected (and tried in demo)
      - What concerns they raised during onboarding
      - Their business email (verified)
      - Their plan and payment info
      - Their ROI calculation results

    CC Jarvis uses this context to provide personalized, aware
    responses from the very first message — no cold start.

    Args:
        onboarding_context: The onboarding session context dict.
        handoff_data: Additional handoff context.

    Returns:
        Dict with CC session context.
    """
    try:
        # Determine variant tier from plan
        selected_plan = onboarding_context.get("selected_plan") or onboarding_context.get("preselected_plan")
        variant_tier = "mini_parwa"  # Default
        if selected_plan:
            plan_lower = str(selected_plan).lower()
            if "high" in plan_lower or "enterprise" in plan_lower:
                variant_tier = "parwa_high"
            elif "growth" in plan_lower or "pro" in plan_lower:
                variant_tier = "parwa"
            elif "starter" in plan_lower or "basic" in plan_lower:
                variant_tier = "mini_parwa"

        cc_context = {
            # Core identity
            "session_type": "customer_care",
            "mode": "customer_care",
            "variant_tier": variant_tier,

            # From onboarding
            "industry": onboarding_context.get("industry"),
            "business_email": onboarding_context.get("business_email"),
            "email_verified": onboarding_context.get("email_verified", False),
            "selected_plan": selected_plan,
            "selected_variants": onboarding_context.get("selected_variants", []),
            "concerns_raised": onboarding_context.get("concerns_raised", []),
            "demo_topics": onboarding_context.get("demo_topics", []),
            "roi_result": onboarding_context.get("roi_result"),

            # Entry info
            "entry_source": onboarding_context.get("entry_source", "onboarding"),
            "referral_source": onboarding_context.get("referral_source"),
            "intent_category": onboarding_context.get("intent_category", "medium_intent"),

            # Payment info
            "payment_data": onboarding_context.get("payment_data"),
            "payment_status": "completed" if onboarding_context.get("payment_data") else "none",

            # Awareness
            "awareness_enabled": True,
            "onboarding_completed_at": onboarding_context.get("handoff_at", datetime.now(timezone.utc).isoformat()),
            "onboarding_stages_completed": onboarding_context.get("stage_history", []),

            # Demo calls
            "demo_calls": onboarding_context.get("demo_calls", []),

            # Merge handoff data
            **(handoff_data or {}),
        }

        return cc_context

    except Exception:
        logger.exception("build_cc_context_from_onboarding_failed")
        return {
            "session_type": "customer_care",
            "variant_tier": "mini_parwa",
            "awareness_enabled": True,
        }


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: str) -> Dict[str, Any]:
    """Safely parse JSON string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
