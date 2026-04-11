"""
PARWA Jarvis Service (Week 6+ — Complete Service Integration)

Core business logic for Jarvis onboarding & customer care system.

All API handlers in jarvis.py call functions here. This service:
- Manages sessions (create, resume, context)
- Handles message send/receive with AI providers
- Enforces message limits (20/day free, 500/day demo)
- Manages OTP verification flow
- Creates Paddle payment sessions
- Handles Paddle webhooks
- Manages demo voice calls (Twilio)
- Executes handoff to Customer Care Jarvis
- Tracks action tickets with status/result
- Builds dynamic system prompts with context + knowledge
- Detects conversation stage from context

Week 8-11 Integrated Services:
- AI/Message Processing: ai_service, pii_scan, brand_voice, response_template,
  sentiment_technique_mapper, conversation_service, token_budget, embedding
- Analytics & Tracking: analytics_service, lead_service
- Ticket Management: ticket_service, ticket_lifecycle, ticket_state_machine,
  ticket_analytics, ticket_search, ticket_merge, stale_ticket, classification,
  spam_detection
- Billing & Usage: usage_tracking, usage_burst_protection, cost_protection,
  overage_service, invoice_service
- Security & Compliance: rate_limit_service, audit_service, audit_log_service
- Onboarding Support: onboarding_service, pricing_service
- Notifications: notification_service, email_service, webhook_service
- Supporting: tag, category, priority, assignment, sla, trigger, internal_note,
  message_service, attachment_service, company_service, customer_service,
  channel_service, bulk_action_service

AI Providers: Google AI Studio, Cerebras, Groq (all free)
Entry Routing: URL params → context-aware welcome message

Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    ValidationError,
    RateLimitError,
    InternalError,
)
from database.models.jarvis import (
    JarvisSession,
    JarvisMessage,
    JarvisKnowledgeUsed,
    JarvisActionTicket,
)


# ── Lazy Service Loading Infrastructure ────────────────────────────

_service_cache: Dict[str, Any] = {}


def _get_service(
    service_name: str,
    import_path: str,
    attr_name: Optional[str] = None,
) -> Any:
    """Lazy-load and cache a service class or module.

    Args:
        service_name: Unique cache key for this service.
        import_path: Python import path (e.g. 'app.services.pii_scan_service').
        attr_name: Specific class/function to import. Falls back to service_name.

    Returns:
        The imported class/function, or None if import fails.
    """
    if service_name in _service_cache:
        return _service_cache[service_name]
    try:
        module = __import__(import_path, fromlist=[attr_name or service_name])
        svc = getattr(module, attr_name or service_name, None)
        if svc is not None:
            _service_cache[service_name] = svc
        return svc
    except (ImportError, AttributeError):
        return None


def _get_service_module(module_path: str) -> Any:
    """Lazy-load a service module (for module-level functions).

    Args:
        module_path: Python module path (e.g. 'app.services.analytics_service').

    Returns:
        The imported module, or None if import fails.
    """
    return _get_service(module_path, module_path)


def _clear_service_cache() -> None:
    """Clear all cached services (useful for testing)."""
    _service_cache.clear()


# ── Constants ──────────────────────────────────────────────────────

FREE_DAILY_LIMIT = 20
DEMO_DAILY_LIMIT = 500
DEMO_PACK_HOURS = 24
DEMO_CALL_DURATION_SECONDS = 180  # 3 minutes
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3
MAX_CONTEXT_HISTORY_MESSAGES = 20  # Last N messages for AI context

__all__ = [
    # Constants
    "FREE_DAILY_LIMIT",
    "DEMO_DAILY_LIMIT",
    "DEMO_PACK_HOURS",
    "DEMO_CALL_DURATION_SECONDS",
    "OTP_LENGTH",
    "OTP_EXPIRY_MINUTES",
    "MAX_OTP_ATTEMPTS",
    # Infrastructure
    "_get_service",
    "_get_service_module",
    "_clear_service_cache",
    # Session
    "create_or_resume_session",
    "get_session",
    "get_session_context",
    "update_context",
    "set_entry_context",
    # Messages
    "send_message",
    "get_history",
    "check_message_limit",
    # OTP
    "send_business_otp",
    "verify_business_otp",
    # Demo Pack
    "purchase_demo_pack",
    "get_demo_pack_status",
    # Payment
    "create_payment_session",
    "handle_payment_webhook",
    "get_payment_status",
    # Demo Call
    "initiate_demo_call",
    "get_call_summary",
    # Handoff
    "execute_handoff",
    "get_handoff_status",
    # Tickets (original)
    "create_action_ticket",
    "get_tickets",
    "get_ticket",
    "update_ticket_status",
    "complete_ticket",
    # AI
    "build_system_prompt",
    "detect_stage",
    # Entry
    "get_entry_context",
    "build_context_aware_welcome",
    # Error
    "handle_error",
    # --- Week 8-11: Ticket Operations ---
    "jarvis_create_ticket",
    "jarvis_get_tickets",
    "jarvis_get_ticket",
    "jarvis_update_ticket",
    "jarvis_delete_ticket",
    "jarvis_assign_ticket",
    "jarvis_transition_ticket",
    "jarvis_classify_ticket",
    "jarvis_search_tickets",
    "jarvis_merge_tickets",
    "jarvis_check_ticket_lifecycle",
    "jarvis_get_ticket_analytics",
    "jarvis_detect_stale_tickets",
    "jarvis_analyze_spam",
    # --- Week 8-11: Analytics ---
    "jarvis_get_analytics",
    "jarvis_get_funnel_metrics",
    "jarvis_get_sentiment_metrics",
    "jarvis_track_event",
    # --- Week 8-11: Lead Management ---
    "jarvis_capture_lead",
    "jarvis_get_lead",
    "jarvis_get_leads",
    "jarvis_get_lead_stats",
    # --- Week 8-11: Billing & Usage ---
    "jarvis_get_usage",
    "jarvis_check_usage_limit",
    "jarvis_get_invoices",
    "jarvis_get_invoice",
    "jarvis_get_monthly_cost_report",
    # --- Week 8-11: Audit & Security ---
    "jarvis_get_audit_trail",
    "jarvis_get_audit_stats",
    "jarvis_get_audit_log_events",
    "jarvis_get_audit_log_stats",
    "jarvis_check_rate_limit",
    # --- Week 8-11: Onboarding ---
    "jarvis_complete_onboarding_step",
    "jarvis_accept_legal_consents",
    "jarvis_activate_ai",
    "jarvis_get_pricing_variants",
    "jarvis_validate_variant_selection",
    "jarvis_calculate_totals",
    # --- Week 8-11: Notifications ---
    "jarvis_send_notification",
    "jarvis_send_email",
    "jarvis_process_webhook",
    # --- Week 8-11: Customer Management ---
    "jarvis_create_customer",
    "jarvis_get_customer",
    "jarvis_get_company_profile",
    "jarvis_update_company_profile",
    # --- Week 8-11: Supporting Services ---
    "jarvis_auto_tag_ticket",
    "jarvis_detect_category",
    "jarvis_detect_priority",
    "jarvis_auto_assign_ticket",
    "jarvis_get_sla_target",
    "jarvis_evaluate_triggers",
    "jarvis_get_ticket_tags",
    "jarvis_get_ticket_notes",
    "jarvis_get_ticket_messages",
    "jarvis_get_ticket_attachments",
    "jarvis_get_channel_config",
    "jarvis_execute_bulk_action",
    "jarvis_get_channels",
    "jarvis_scan_pii",
    "jarvis_merge_with_brand_voice",
]


# ── Session Management ─────────────────────────────────────────────


def create_or_resume_session(
    db: Session,
    user_id: str,
    company_id: Optional[str] = None,
    entry_source: str = "direct",
    entry_params: Optional[Dict[str, Any]] = None,
) -> JarvisSession:
    """Create a new onboarding session or resume an active one.

    Looks for an active onboarding session for this user.
    If found and from today, resumes it. Otherwise creates new.
    """
    # Try to find active session
    active_session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.user_id == user_id,
            JarvisSession.is_active.is_(True),
            JarvisSession.type == "onboarding",
        )
        .order_by(JarvisSession.created_at.desc())
        .first()
    )

    if active_session:
        # Reset daily counter if new day
        _maybe_reset_daily_counter(db, active_session)
        active_session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Update entry context if provided
        if entry_source and entry_source != "direct":
            ctx = _parse_context(active_session.context_json)
            ctx["entry_source"] = entry_source
            if entry_params:
                ctx["entry_params"] = entry_params
            active_session.context_json = json.dumps(ctx)

        return active_session

    # Create new session
    ctx = {
        "pages_visited": [],
        "industry": None,
        "selected_variants": [],
        "roi_result": None,
        "demo_topics": [],
        "concerns_raised": [],
        "business_email": None,
        "email_verified": False,
        "referral_source": "",
        "entry_source": entry_source,
        "entry_params": entry_params or {},
        "detected_stage": "welcome",
    }

    session = JarvisSession(
        user_id=user_id,
        company_id=company_id,
        type="onboarding",
        context_json=json.dumps(ctx),
        message_count_today=0,
        total_message_count=0,
        pack_type="free",
        is_active=True,
    )
    db.add(session)
    db.flush()
    return session


def get_session(
    db: Session,
    session_id: str,
    user_id: str,
) -> JarvisSession:
    """Get session by ID, scoped to user for security."""
    session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.id == session_id,
            JarvisSession.user_id == user_id,
        )
        .first()
    )
    if not session:
        raise NotFoundError(
            message="Session not found",
            details={"session_id": session_id},
        )
    return session


def get_session_context(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get context_json for AI prompt injection."""
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        raise NotFoundError(message="Session not found")
    return _parse_context(session.context_json)


def update_context(
    db: Session,
    session_id: str,
    user_id: str,
    partial_updates: Dict[str, Any],
) -> JarvisSession:
    """Merge partial updates into session context_json.

    Only provided keys are updated. Existing keys are preserved.
    """
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)

    for key, value in partial_updates.items():
        if value is not None:
            ctx[key] = value

    session.context_json = json.dumps(ctx)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()
    return session


def set_entry_context(
    db: Session,
    user_id: str,
    company_id: Optional[str],
    entry_source: str,
    entry_params: Optional[Dict[str, Any]],
) -> JarvisSession:
    """Set or update entry source from URL params.

    Creates/resumes session and applies entry context for
    context-aware welcome message.
    """
    session = create_or_resume_session(
        db, user_id, company_id, entry_source, entry_params,
    )
    return session


# ── Message Management ─────────────────────────────────────────────


def send_message(
    db: Session,
    session_id: str,
    user_id: str,
    user_message: str,
) -> Tuple[JarvisMessage, JarvisMessage, List[Dict[str, Any]]]:
    """Process a user message and generate AI response.

    Flow:
    1. Save user message
    2. Check message limits
    3. Build system prompt with context
    4. Call AI provider
    5. Save AI response + knowledge used
    6. Detect conversation stage
    7. Return both messages

    Returns:
        Tuple of (user_message_obj, ai_message_obj, knowledge_used_list)

    Raises:
        RateLimitError: If daily limit exceeded
        ValidationError: If content invalid
    """
    session = get_session(db, session_id, user_id)

    # Check limits
    limit, remaining = check_message_limit(db, session)
    if remaining <= 0:
        # Return a limit-reached system message instead of raising
        limit_msg = JarvisMessage(
            session_id=session_id,
            role="system",
            content=_get_limit_message(session),
            message_type="limit_reached",
            metadata_json=json.dumps({"limit": limit}),
        )
        db.add(limit_msg)
        db.flush()
        return limit_msg, limit_msg, []

    # Save user message
    user_msg = JarvisMessage(
        session_id=session_id,
        role="user",
        content=user_message,
        message_type="text",
    )
    db.add(user_msg)
    db.flush()

    # Update counters
    session.message_count_today += 1
    session.total_message_count += 1
    session.last_message_date = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)

    # Track pages visited (heuristic from message content)
    ctx = _parse_context(session.context_json)
    _track_pages_visited(ctx, user_message)

    # ── Week 8-11: PII scan user message ──
    company_id = session.company_id
    try:
        pii_svc_cls = _get_service(
            "pii_scan", "app.services.pii_scan_service", "PIIScanService",
        )
        if pii_svc_cls and company_id:
            pii_scanner = pii_svc_cls(db, company_id)
            pii_result = pii_scanner.scan_text(user_message)
            ctx["pii_scan"] = pii_result
    except Exception:
        pass

    # ── Week 8-11: Conversation context enrichment ──
    try:
        conv_svc = _get_service_module("app.services.conversation_service")
        if conv_svc:
            conv_ctx = conv_svc.get_conversation_context(
                session_id, db, ctx,
            )
            if conv_ctx:
                ctx["conversation_turn_count"] = getattr(
                    conv_ctx, "turn_count", 0,
                )
    except Exception:
        pass

    # ── Week 8-11: Analytics tracking ──
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            stage = ctx.get("detected_stage", "welcome")
            analytics_svc.track_event(
                event_type="message_sent",
                event_category="conversation",
                user_id=user_id,
                company_id=company_id or "",
                session_id=session_id,
                properties={"stage": stage},
                source="jarvis",
            )
    except Exception:
        pass

    # ── Week 8-11: Lead capture (every 5 turns) ──
    turn_count = ctx.get("conversation_turn_count", session.total_message_count)
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc and turn_count % 5 == 0:
            lead_svc.capture_lead(
                session_id=session_id,
                user_id=user_id,
                company_id=company_id,
                session_context=ctx,
                sentiment_data=ctx.get("sentiment"),
            )
    except Exception:
        pass

    # ── Week 8-11: Sentiment technique mapping ──
    try:
        stm_cls = _get_service(
            "sentiment_technique_mapper",
            "app.services.sentiment_technique_mapper",
            "SentimentTechniqueMapper",
        )
        if stm_cls:
            mapper = stm_cls()
            sentiment_map = mapper.map(
                frustration_score=ctx.get("frustration_score", 0),
                sentiment_score=ctx.get("sentiment_score", 0.5),
                urgency_level=ctx.get("urgency_level", "normal"),
                customer_tier=ctx.get("customer_tier", "standard"),
                emotion=ctx.get("emotion"),
                is_vip=ctx.get("is_vip", False),
                variant_type=session.pack_type,
                company_id=company_id or "",
            )
            ctx["technique_mapping"] = sentiment_map.to_dict() if hasattr(sentiment_map, 'to_dict') else {}
    except Exception:
        pass

    # Build AI prompt and call provider
    system_prompt = build_system_prompt(db, session_id)
    history = _get_recent_history(db, session_id)

    try:
        ai_content, ai_message_type, metadata, knowledge = (
            _call_ai_provider(system_prompt, history, user_message, ctx)
        )
    except Exception as exc:
        # Graceful error — return error message card
        ai_content, ai_message_type = (
            _get_friendly_error_message(), "error"
        )
        metadata = {"error_type": type(exc).__name__}
        knowledge = []

    # Save AI response
    ai_msg = JarvisMessage(
        session_id=session_id,
        role="jarvis",
        content=ai_content,
        message_type=ai_message_type,
        metadata_json=json.dumps(metadata),
    )
    db.add(ai_msg)
    db.flush()

    # Save knowledge used
    knowledge_records = []
    for ku in knowledge:
        ku_record = JarvisKnowledgeUsed(
            message_id=ai_msg.id,
            knowledge_file=ku.get("file", ""),
            relevance_score=ku.get("score", 1.0),
        )
        db.add(ku_record)
        knowledge_records.append(ku)

    # Detect and update stage
    detected = detect_stage(db, session_id)
    ctx["detected_stage"] = detected

    # ── Week 8-11: Brand voice validation on AI response ──
    try:
        bv_svc_cls = _get_service(
            "brand_voice", "app.services.brand_voice_service", "BrandVoiceService",
        )
        if bv_svc_cls and company_id:
            bv_svc = bv_svc_cls(db)
            prohibited = bv_svc.check_prohibited_words(ai_content, company_id)
            if prohibited and hasattr(prohibited, 'found') and prohibited.found:
                ctx["brand_voice_warning"] = "prohibited_words_detected"
    except Exception:
        pass

    # ── Week 8-11: Post-response audit logging ──
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            audit_svc.log_audit(
                company_id=company_id or "",
                actor_id=user_id,
                actor_type="user",
                action="message_sent",
                resource_type="session",
                resource_id=session_id,
                old_value=None,
                new_value={"stage": detected, "turn": turn_count},
                ip_address=None,
                user_agent=None,
                db=db,
            )
    except Exception:
        pass

    session.context_json = json.dumps(ctx)

    db.flush()
    return user_msg, ai_msg, knowledge_records


def get_history(
    db: Session,
    session_id: str,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisMessage], int]:
    """Get paginated message history for a session."""
    get_session(db, session_id, user_id)  # Auth check

    query = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.asc())
    )

    total = query.count()
    messages = query.offset(offset).limit(limit).all()

    return messages, total


def check_message_limit(
    db: Session,
    session: JarvisSession,
) -> Tuple[int, int]:
    """Check and enforce message limits.

    Returns:
        Tuple of (limit, remaining)

    Raises:
        RateLimitError: If daily limit exceeded
    """
    _maybe_reset_daily_counter(db, session)

    if session.pack_type == "demo":
        # Check pack expiry
        if session.pack_expiry and datetime.now(timezone.utc) > session.pack_expiry:
            session.pack_type = "free"
            session.pack_expiry = None
            session.message_count_today = 0
            db.flush()
            limit = FREE_DAILY_LIMIT
        else:
            limit = DEMO_DAILY_LIMIT
    else:
        limit = FREE_DAILY_LIMIT

    remaining = max(0, limit - session.message_count_today)
    return limit, remaining


def _maybe_reset_daily_counter(
    db: Session, session: JarvisSession,
) -> None:
    """Reset daily counter if date has changed."""
    today = datetime.now(timezone.utc).date()
    last_date = None
    if session.last_message_date:
        if isinstance(session.last_message_date, datetime):
            last_date = session.last_message_date.date()
        else:
            last_date = session.last_message_date

    if last_date is None or last_date < today:
        session.message_count_today = 0
        session.last_message_date = datetime.now(timezone.utc)
        db.flush()


def _get_limit_message(session: JarvisSession) -> str:
    """Get appropriate limit-reached message."""
    if session.pack_type == "free":
        return (
            "You've used all 20 free messages for today. "
            "Upgrade to the $1 Demo Pack for 500 messages "
            "and a 3-minute AI voice call!"
        )
    return (
        "Your Demo Pack messages have been used. "
        "You can purchase another Demo Pack or come back "
        "tomorrow for your free messages."
    )


# ── OTP Verification ───────────────────────────────────────────────


def send_business_otp(
    db: Session,
    session_id: str,
    user_id: str,
    email: str,
) -> Dict[str, Any]:
    """Generate 6-digit OTP and store in session context.

    In production, this sends an email via the email service.
    Returns OTP metadata for the caller to construct the response.
    """
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)

    # Rate limit OTP attempts
    otp_data = ctx.get("otp", {})
    if otp_data.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
        raise RateLimitError(
            message="Too many OTP attempts. Please try again later.",
            details={"attempts": otp_data.get("attempts", 0)},
        )

    # Generate OTP
    otp_code = secrets.token_hex(OTP_LENGTH // 2)[:OTP_LENGTH].upper()
    if len(otp_code) < OTP_LENGTH:
        otp_code = otp_code.zfill(OTP_LENGTH)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    ).isoformat()

    # Store in context
    otp_data = {
        "code": otp_code,
        "email": email,
        "attempts": 0,
        "expires_at": expires_at,
        "status": "sent",
    }
    ctx["otp"] = otp_data
    ctx["business_email"] = email
    session.context_json = json.dumps(ctx)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Create action ticket
    _create_ticket(db, session_id, "otp_verification", {"email": email})

    # In production: await email_service.send_otp(email, otp_code)
    # For now, OTP is stored in context for verification

    return {
        "message": f"OTP sent to {email}",
        "status": "sent",
        "attempts_remaining": MAX_OTP_ATTEMPTS,
        "expires_at": expires_at,
        # OTP code stored in context only — never returned to client
    }


def verify_business_otp(
    db: Session,
    session_id: str,
    user_id: str,
    code: str,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify OTP code from session context."""
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)
    otp_data = ctx.get("otp", {})

    # Check OTP status
    if otp_data.get("status") == "verified":
        return {
            "message": "Email already verified",
            "status": "verified",
            "attempts_remaining": otp_data.get("attempts_remaining", MAX_OTP_ATTEMPTS),
        }

    # Check expiry
    if otp_data.get("expires_at"):
        expires = datetime.fromisoformat(otp_data["expires_at"])
        if datetime.now(timezone.utc) > expires:
            return {
                "message": "OTP has expired. Please request a new one.",
                "status": "expired",
                "attempts_remaining": 0,
            }

    # Check email match if provided
    if email and otp_data.get("email") and email != otp_data["email"]:
        return {
            "message": "Email does not match the one OTP was sent to",
            "status": "error",
            "attempts_remaining": MAX_OTP_ATTEMPTS - otp_data.get("attempts", 0),
        }

    # Verify code
    attempts = otp_data.get("attempts", 0) + 1
    stored_code = otp_data.get("code", "")

    if code.upper().strip() == stored_code:
        otp_data["status"] = "verified"
        otp_data["verified_at"] = datetime.now(timezone.utc).isoformat()
        otp_data["attempts_remaining"] = MAX_OTP_ATTEMPTS - attempts
        ctx["otp"] = otp_data
        ctx["email_verified"] = True
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Update ticket status
        _complete_latest_ticket(
            db, session_id, "otp_verification",
            {"email": email or otp_data.get("email"), "verified": True},
        )
        # Create verified ticket
        _create_ticket(
            db, session_id, "otp_verified",
            {"email": email or otp_data.get("email")},
        )

        return {
            "message": "Email verified successfully!",
            "status": "verified",
            "attempts_remaining": MAX_OTP_ATTEMPTS - attempts,
        }

    # Wrong code
    otp_data["attempts"] = attempts
    otp_data["attempts_remaining"] = max(0, MAX_OTP_ATTEMPTS - attempts)
    ctx["otp"] = otp_data
    session.context_json = json.dumps(ctx)
    db.flush()

    return {
        "message": f"Invalid OTP. {MAX_OTP_ATTEMPTS - attempts} attempts remaining.",
        "status": "invalid",
        "attempts_remaining": MAX_OTP_ATTEMPTS - attempts,
    }


# ── Demo Pack ──────────────────────────────────────────────────────


def purchase_demo_pack(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Activate $1 demo pack: 500 messages + 3-min AI call for 24 hours.

    In production, this creates a Paddle checkout for $1.
    For now, we simulate the purchase.
    """
    session = get_session(db, session_id, user_id)

    expiry = datetime.now(timezone.utc) + timedelta(hours=DEMO_PACK_HOURS)

    session.pack_type = "demo"
    session.pack_expiry = expiry
    session.message_count_today = 0  # Reset counter
    session.updated_at = datetime.now(timezone.utc)

    # Create action ticket
    _create_ticket(db, session_id, "payment_demo_pack", {
        "pack_type": "demo",
        "expiry": expiry.isoformat(),
        "price_usd": 1.00,
    })

    db.flush()

    return {
        "message": "Demo Pack activated! 500 messages + 3-min AI call for 24 hours.",
        "pack_type": "demo",
        "pack_expiry": expiry.isoformat(),
        "remaining_today": DEMO_DAILY_LIMIT,
        "demo_call_remaining": True,
    }


def get_demo_pack_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get current demo pack status and limits."""
    session = get_session(db, session_id, user_id)
    limit, remaining = check_message_limit(db, session)

    return {
        "pack_type": session.pack_type,
        "remaining_today": remaining,
        "total_allowed": limit,
        "pack_expiry": (
            session.pack_expiry.isoformat() if session.pack_expiry else None
        ),
        "demo_call_remaining": not session.demo_call_used,
    }


# ── Payment ────────────────────────────────────────────────────────


def create_payment_session(
    db: Session,
    session_id: str,
    user_id: str,
    variants: List[Dict[str, Any]],
    industry: str,
) -> Dict[str, Any]:
    """Create Paddle checkout URL for variant purchase.

    In production, this calls Paddle API to create a checkout.
    Returns the checkout URL and transaction details.
    """
    session = get_session(db, session_id, user_id)

    # Calculate total
    # (In production, prices come from Paddle price IDs)
    total_monthly = sum(v.get("price", 0) * v.get("quantity", 1) for v in variants)

    # Create action ticket
    ticket = _create_ticket(db, session_id, "payment_variant", {
        "variants": variants,
        "industry": industry,
        "total_monthly": total_monthly,
    })

    session.payment_status = "pending"
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # In production: paddle_client.create_checkout(...)
    # For now, return a simulated checkout URL
    checkout_url = f"https://checkout.paddle.com/checkout?custom=session_{session_id}"

    return {
        "checkout_url": checkout_url,
        "transaction_id": f"txn_{ticket.id[:12]}",
        "status": "pending",
        "amount": f"${total_monthly:.2f}",
        "currency": "USD",
    }


def handle_payment_webhook(
    db: Session,
    event_type: str,
    event_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Paddle webhook event (success/fail).

    Idempotent: checks event_id to prevent double-processing.
    Paddle may fire the same webhook multiple times.
    """
    # Idempotency: check if event was already processed
    # Use result_json on the payment_variant ticket to track event_id
    event_id = event_data.get("event_id", "")
    if event_id:
        existing_ticket = (
            db.query(JarvisActionTicket)
            .filter(
                JarvisActionTicket.ticket_type == "payment_variant_completed",
            )
            .all()
        )
        for t in existing_ticket:
            result = _parse_context(t.result_json or "{}")
            if result.get("event_id") == event_id:
                return {
                    "status": "already_processed",
                    "session_id": event_data.get("custom", {}).get("session_id"),
                    "event_type": event_type,
                    "event_id": event_id,
                }

    # Extract session info from webhook data
    # In production: parse Paddle webhook signature
    session_id = event_data.get("custom", {}).get("session_id")
    if not session_id:
        raise ValidationError(
            message="Invalid webhook: no session reference",
        )

    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        raise NotFoundError(message="Session not found for webhook")

    if event_type in ("payment.completed", "payment.success"):
        session.payment_status = "completed"
        _complete_latest_ticket(
            db, session_id, "payment_variant",
            {"paddle_event": event_type, "data": event_data},
        )
        _create_ticket(db, session_id, "payment_variant_completed", {
            "paddle_event": event_type,
            "event_id": event_id,
        })
    elif event_type in ("payment.failed", "payment.declined"):
        session.payment_status = "failed"
        _complete_latest_ticket(
            db, session_id, "payment_variant",
            {"paddle_event": event_type, "data": event_data, "success": False},
        )

    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    return {
        "status": session.payment_status,
        "session_id": session_id,
        "event_type": event_type,
    }


def get_payment_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get current payment status for a session."""
    session = get_session(db, session_id, user_id)
    return {
        "status": session.payment_status,
        "paddle_transaction_id": None,  # From Paddle in production
        "amount": None,
        "currency": "USD",
        "paid_at": None,
    }


# ── Demo Call ──────────────────────────────────────────────────────


def initiate_demo_call(
    db: Session,
    session_id: str,
    user_id: str,
    phone: str,
) -> Dict[str, Any]:
    """Initiate a 3-minute AI voice call via Twilio.

    Flow:
    1. Validate demo call availability (pack active, not used)
    2. Create action ticket
    3. Initiate Twilio call
    4. Return call details

    In production, this triggers a Twilio outbound call.
    """
    session = get_session(db, session_id, user_id)

    # Check demo call availability
    if session.pack_type != "demo":
        raise ValidationError(
            message="Demo call requires active Demo Pack ($1)",
        )
    if session.demo_call_used:
        raise ValidationError(
            message="Demo call already used in this session",
        )
    if session.pack_expiry and datetime.now(timezone.utc) > session.pack_expiry:
        raise ValidationError(
            message="Demo Pack has expired",
        )

    # Create action ticket
    ticket = _create_ticket(db, session_id, "demo_call", {
        "phone": phone,
        "duration_limit": DEMO_CALL_DURATION_SECONDS,
    })

    session.demo_call_used = True
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # In production: twilio_client.calls.create(...)
    call_id = f"call_{ticket.id[:12]}"

    return {
        "call_id": call_id,
        "status": "initiating",
        "phone": phone,
        "duration_limit": DEMO_CALL_DURATION_SECONDS,
        "message": "Demo call initiated! Answer your phone.",
    }


def get_call_summary(
    db: Session,
    session_id: str,
    user_id: str,
    call_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get post-call summary with topics discussed.

    In production, this fetches call recording/transcript from Twilio
    and generates summary via AI.
    """
    get_session(db, session_id, user_id)

    # Look for completed call ticket
    ticket = (
        db.query(JarvisActionTicket)
        .filter(
            JarvisActionTicket.session_id == session_id,
            JarvisActionTicket.ticket_type.in_(["demo_call", "demo_call_completed"]),
        )
        .order_by(JarvisActionTicket.created_at.desc())
        .first()
    )

    if not ticket:
        return {
            "call_id": call_id,
            "status": "not_found",
            "duration_seconds": 0,
            "topics_discussed": [],
            "key_moments": [],
            "user_impressions": None,
            "roi_mapping": None,
            "transcript_summary": None,
        }

    result = _parse_context(ticket.result_json or "{}")

    # Create completed ticket if not exists
    if ticket.ticket_type == "demo_call":
        _create_ticket(db, session_id, "demo_call_completed", {
            "call_id": call_id,
            "duration": result.get("duration", 0),
        })

    return {
        "call_id": call_id,
        "status": "completed",
        "duration_seconds": result.get("duration", 0),
        "topics_discussed": result.get("topics", []),
        "key_moments": result.get("moments", []),
        "user_impressions": result.get("impressions"),
        "roi_mapping": result.get("roi_mapping"),
        "transcript_summary": result.get("summary"),
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }


# ── Handoff ────────────────────────────────────────────────────────


def execute_handoff(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Transition from Onboarding Jarvis to Customer Care Jarvis.

    Creates a new customer_care session with selective context transfer.
    The onboarding session is marked with handoff_completed=True.
    Chat memory is NOT transferred (fresh entity).
    """
    session = get_session(db, session_id, user_id)

    if session.handoff_completed:
        return {
            "message": "Handoff already completed",
            "handoff_completed": True,
            "new_session_id": None,
            "handoff_at": None,
        }

    # Selective context transfer (NOT full chat memory)
    ctx = _parse_context(session.context_json)
    care_context = {
        "industry": ctx.get("industry"),
        "selected_variants": ctx.get("selected_variants", []),
        "business_email": ctx.get("business_email"),
        "email_verified": ctx.get("email_verified", False),
        "onboarding_session_id": session_id,
        "onboarding_completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Create customer care session (FRESH — no chat history)
    care_session = JarvisSession(
        user_id=user_id,
        company_id=session.company_id,
        type="customer_care",
        context_json=json.dumps(care_context),
        message_count_today=0,
        total_message_count=0,
        pack_type="free",
        is_active=True,
    )
    db.add(care_session)
    db.flush()

    # Mark onboarding session
    session.handoff_completed = True
    session.is_active = False
    session.updated_at = datetime.now(timezone.utc)

    # Create action tickets
    _complete_latest_ticket(db, session_id, "handoff", {
        "care_session_id": care_session.id,
    })
    _create_ticket(db, session_id, "handoff", {
        "care_session_id": care_session.id,
        "transferred_context_keys": list(care_context.keys()),
    })

    db.flush()

    return {
        "message": "Welcome to Customer Care Jarvis! I'm here to help.",
        "handoff_completed": True,
        "new_session_id": care_session.id,
        "handoff_at": datetime.now(timezone.utc).isoformat(),
    }


def get_handoff_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Check handoff status for a session."""
    session = get_session(db, session_id, user_id)

    # Check if customer care session was created
    care_session = None
    if session.handoff_completed:
        care_session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.user_id == user_id,
                JarvisSession.type == "customer_care",
            )
            .order_by(JarvisSession.created_at.desc())
            .first()
        )

    return {
        "handoff_completed": session.handoff_completed,
        "new_session_id": care_session.id if care_session else None,
        "handoff_at": (
            session.updated_at.isoformat()
            if session.handoff_completed and session.updated_at
            else None
        ),
    }


# ── Action Tickets ─────────────────────────────────────────────────


def create_action_ticket(
    db: Session,
    session_id: str,
    user_id: str,
    ticket_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> JarvisActionTicket:
    """Create an action ticket for a user action."""
    get_session(db, session_id, user_id)  # Auth check

    return _create_ticket(db, session_id, ticket_type, metadata or {})


def _create_ticket(
    db: Session,
    session_id: str,
    ticket_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> JarvisActionTicket:
    """Internal: create ticket without auth check."""
    ticket = JarvisActionTicket(
        session_id=session_id,
        ticket_type=ticket_type,
        status="pending",
        metadata_json=json.dumps(metadata or {}),
        result_json="{}",
    )
    db.add(ticket)
    db.flush()
    return ticket


def get_tickets(
    db: Session,
    session_id: str,
    user_id: str,
) -> List[JarvisActionTicket]:
    """Get all action tickets for a session."""
    get_session(db, session_id, user_id)  # Auth check
    return (
        db.query(JarvisActionTicket)
        .filter(JarvisActionTicket.session_id == session_id)
        .order_by(JarvisActionTicket.created_at.desc())
        .all()
    )


def get_ticket(
    db: Session,
    ticket_id: str,
    user_id: str,
) -> JarvisActionTicket:
    """Get a single action ticket with result."""
    ticket = (
        db.query(JarvisActionTicket)
        .filter(JarvisActionTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise NotFoundError(
            message="Ticket not found",
            details={"ticket_id": ticket_id},
        )
    # Verify user owns the session
    get_session(db, ticket.session_id, user_id)
    return ticket


def update_ticket_status(
    db: Session,
    ticket_id: str,
    user_id: str,
    status: str,
) -> JarvisActionTicket:
    """Update ticket status."""
    ticket = get_ticket(db, ticket_id, user_id)
    ticket.status = status
    ticket.updated_at = datetime.now(timezone.utc)

    if status == "completed":
        ticket.completed_at = datetime.now(timezone.utc)

    db.flush()
    return ticket


def complete_ticket(
    db: Session,
    ticket_id: str,
    user_id: str,
    result_data: Dict[str, Any],
) -> JarvisActionTicket:
    """Mark ticket completed with result data."""
    ticket = get_ticket(db, ticket_id, user_id)
    ticket.status = "completed"
    ticket.result_json = json.dumps(result_data)
    ticket.completed_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    db.flush()
    return ticket


def _complete_latest_ticket(
    db: Session,
    session_id: str,
    ticket_type: str,
    result_data: Dict[str, Any],
) -> Optional[JarvisActionTicket]:
    """Internal: complete the latest pending ticket of a given type."""
    ticket = (
        db.query(JarvisActionTicket)
        .filter(
            JarvisActionTicket.session_id == session_id,
            JarvisActionTicket.ticket_type == ticket_type,
            JarvisActionTicket.status == "pending",
        )
        .order_by(JarvisActionTicket.created_at.desc())
        .first()
    )
    if ticket:
        ticket.status = "completed"
        ticket.result_json = json.dumps(result_data)
        ticket.completed_at = datetime.now(timezone.utc)
        ticket.updated_at = datetime.now(timezone.utc)
        db.flush()
    return ticket


# ── AI Provider Integration ────────────────────────────────────────


def build_system_prompt(
    db: Session,
    session_id: str,
) -> str:
    """Build dynamic system prompt with session context + knowledge.

    Injects:
    - Jarvis personality (professional, helpful, product expert)
    - User context (industry, variants, stage)
    - Conversation guidelines
    - Knowledge base references (Phase 7)
    - Information boundary rules
    """
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return _get_default_system_prompt()

    ctx = _parse_context(session.context_json)
    company_id = ctx.get("company_id")

    prompt = _get_default_system_prompt()

    # Inject context-aware section
    context_section = "\n\n## Current User Context:\n"
    if ctx.get("industry"):
        context_section += f"- Industry: {ctx['industry']}\n"
    if ctx.get("selected_variants"):
        variants = ctx["selected_variants"]
        variant_names = [v.get("name", v.get("id", "unknown")) for v in variants]
        context_section += f"- Selected variants: {', '.join(variant_names)}\n"
    if ctx.get("business_email"):
        context_section += f"- Business email: {ctx['business_email']}\n"
        context_section += f"- Email verified: {ctx.get('email_verified', False)}\n"
    if ctx.get("entry_source") and ctx["entry_source"] != "direct":
        context_section += f"- Entry source: {ctx['entry_source']}\n"

    stage = ctx.get("detected_stage", "welcome")
    context_section += f"- Conversation stage: {stage}\n"

    # Stage-specific instructions
    stage_instructions = {
        "welcome": (
            "The user just arrived. Give a warm, brief welcome. "
            "Ask what they're looking for."
        ),
        "discovery": (
            "Learn about the user's business: industry, size, pain points. "
            "Recommend relevant variants based on their needs."
        ),
        "demo": (
            "The user wants to try PARWA. Explain the demo pack ($1 = "
            "500 messages + 3-min AI call). Guide them to purchase."
        ),
        "pricing": (
            "Discuss pricing. Show bill summary with selected variants. "
            "Address any pricing concerns."
        ),
        "bill_review": (
            "Review the bill summary with the user. Confirm selections "
            "before proceeding to verification."
        ),
        "verification": (
            "Collect and verify the user's business email via OTP. "
            "This is required before payment."
        ),
        "payment": (
            "Guide the user through Paddle checkout. "
            "Be supportive and address any payment concerns."
        ),
        "handoff": (
            "The user has completed onboarding. Congratulate them "
            "and explain the handoff to Customer Care Jarvis."
        ),
    }
    context_section += "\n## Current Stage Instructions:\n"
    context_section += stage_instructions.get(stage, stage_instructions["welcome"])

    # Information boundary
    context_section += (
        "\n\n## Information Boundary (CRITICAL):\n"
        "- CAN discuss: Features, pricing, ROI, integrations, "
        "capabilities, demo scenarios\n"
        "- CANNOT discuss: Internal strategy, technical implementation "
        "details, client data, proprietary algorithms\n"
        "- If asked about restricted topics, politely redirect to "
        "what you CAN help with\n"
    )

    # Phase 7: Inject knowledge base content into prompt
    try:
        from app.services.jarvis_knowledge_service import (
            build_context_knowledge,
        )
        knowledge_section = build_context_knowledge(ctx)
        if knowledge_section:
            prompt += f"\n\n{knowledge_section}"
    except Exception:
        # Knowledge service not available — continue without it
        pass

    # ── Week 8-11: Inject brand voice guidelines ──
    try:
        bv_svc_cls = _get_service(
            "brand_voice", "app.services.brand_voice_service", "BrandVoiceService",
        )
        if bv_svc_cls and company_id:
            bv_svc = bv_svc_cls(db)
            bv_config = bv_svc.get_config(company_id)
            if bv_config:
                prompt += "\n\n## Brand Voice Guidelines:\n"
                tone = getattr(bv_config, "tone", None)
                if tone:
                    prompt += f"- Tone: {tone}\n"
                formality = getattr(bv_config, "formality_level", None)
                if formality:
                    prompt += f"- Formality: {formality}\n"
                personality = getattr(bv_config, "personality_traits", None)
                if personality:
                    prompt += f"- Personality: {', '.join(personality) if isinstance(personality, list) else personality}\n"
    except Exception:
        pass

    # ── Week 8-11: Inject response guidelines based on sentiment ──
    try:
        bv_svc_cls2 = _get_service(
            "brand_voice", "app.services.brand_voice_service", "BrandVoiceService",
        )
        if bv_svc_cls2 and company_id:
            bv_svc2 = bv_svc_cls2(db)
            sentiment_score = ctx.get("sentiment_score", 0.5)
            guidelines = bv_svc2.get_response_guidelines(company_id, sentiment_score)
            if guidelines:
                prompt += "\n\n## Response Guidelines (sentiment-aware):\n"
                if isinstance(guidelines, str):
                    prompt += guidelines
                elif hasattr(guidelines, "guidelines"):
                    for g in guidelines.guidelines[:5]:
                        prompt += f"- {g}\n"
    except Exception:
        pass

    prompt += context_section
    return prompt


def detect_stage(
    db: Session,
    session_id: str,
) -> str:
    """Determine conversation stage from context.

    Heuristic-based detection using context signals:
    - welcome: No industry set
    - discovery: Industry set, no variants selected
    - demo: Pack purchased or demo requested
    - pricing: Variants selected
    - bill_review: Bill summary shown
    - verification: OTP in progress
    - payment: Payment initiated
    - handoff: Payment completed
    """
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return "welcome"

    ctx = _parse_context(session.context_json)
    otp = ctx.get("otp", {})

    # Payment completed → handoff
    if session.payment_status == "completed":
        return "handoff"

    # Payment in progress
    if session.payment_status == "pending":
        return "payment"

    # OTP verification in progress
    if otp.get("status") == "sent" and not ctx.get("email_verified"):
        return "verification"

    # Variants selected + bill shown
    if ctx.get("selected_variants") and ctx.get("bill_shown"):
        return "bill_review"

    # Variants selected
    if ctx.get("selected_variants"):
        return "pricing"

    # Demo pack or demo call
    if session.pack_type == "demo" or session.demo_call_used:
        return "demo"

    # Industry set
    if ctx.get("industry"):
        return "discovery"

    return "welcome"


# ── Entry Context ──────────────────────────────────────────────────


def get_entry_context(
    entry_source: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse URL params into context_json for entry routing."""
    params = params or {}
    ctx = {
        "entry_source": entry_source,
        "entry_params": params,
        "detected_stage": "welcome",
    }

    # Route based on entry source
    if entry_source == "pricing":
        ctx["detected_stage"] = "pricing"
        if params.get("industry"):
            ctx["industry"] = params["industry"]
        if params.get("variants"):
            ctx["selected_variants"] = params["variants"]
    elif entry_source == "roi":
        ctx["detected_stage"] = "discovery"
        if params.get("industry"):
            ctx["industry"] = params["industry"]
    elif entry_source == "demo":
        ctx["detected_stage"] = "demo"
    elif entry_source == "features":
        ctx["detected_stage"] = "discovery"
    elif entry_source == "referral":
        if params.get("ref"):
            ctx["referral_source"] = params["ref"]

    return ctx


def build_context_aware_welcome(
    db: Session,
    session_id: str,
) -> str:
    """Generate welcome message based on entry source."""
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return _get_default_welcome()

    ctx = _parse_context(session.context_json)
    entry = ctx.get("entry_source", "direct")

    welcomes = {
        "direct": (
            "Hey there! 👋 I'm Jarvis from PARWA. Think of me as your personal AI consultant — "
            "I'll help you find the right AI agents for your business. So, what brings you in today?"
        ),
        "pricing": (
            "Hey! 👋 Great, you're already checking out pricing! "
            "I can help you find the best fit for your needs. What's your industry?"
        ),
        "roi": (
            "Hey there! 👋 Interested in PARWA's ROI? Smart thinking! "
            "Let me show you how it can transform your customer support. What industry are you in?"
        ),
        "demo": (
            "Hey! 🚀 Ready to see PARWA in action? "
            "For just $1, you get 500 messages + a 3-min AI voice call. Want to jump in?"
        ),
        "features": (
            "Hi there! ✨ Been exploring our features? Nice! "
            "I can help you find the perfect variants for your business. Tell me about it!"
        ),
        "referral": (
            "Hey! 🎉 A friend sent you? Love that! "
            "I'm Jarvis — let me help you get set up with PARWA. What brings you here?"
        ),
    }

    # Add context for known industry
    industry = ctx.get("industry")
    base = welcomes.get(entry, welcomes["direct"])
    if industry:
        base = f"I see you're in {industry}. " + base

    return base


# ── Error Handling ─────────────────────────────────────────────────


def handle_error(
    db: Session,
    session_id: str,
    error: Exception,
) -> Dict[str, Any]:
    """Graceful error handling — returns user-friendly message."""
    error_map = {
        "RateLimitError": (
            "You're sending messages too fast. "
            "Please wait a moment and try again."
        ),
        "ValidationError": (
            "Something wasn't quite right with that request. "
            "Could you try again?"
        ),
        "NotFoundError": (
            "I couldn't find what you were looking for. "
            "Let me help you with something else."
        ),
        "AuthenticationError": (
            "Your session seems to have expired. "
            "Please refresh the page to continue."
        ),
    }

    error_type = type(error).__name__
    message = error_map.get(error_type, _get_friendly_error_message())

    # Log the error (in production, use proper logger)
    # logger.error("jarvis_error", session_id=session_id, error=str(error))

    return {
        "message": message,
        "error_type": error_type,
        "session_id": session_id,
    }


# ═══════════════════════════════════════════════════════════════════
# Week 8-11: New Public Functions — Complete Service Integration
# ═══════════════════════════════════════════════════════════════════


# ── Ticket Operations ────────────────────────────────────────────


def jarvis_create_ticket(
    db: Session,
    company_id: str,
    subject: str,
    description: str,
    customer_id: Optional[str] = None,
    priority: str = "medium",
    category: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a customer care ticket via ticket_service.

    Args:
        db: Database session.
        company_id: Company owning the ticket.
        subject: Ticket subject/title.
        description: Ticket description/body.
        customer_id: Optional customer identifier.
        priority: Ticket priority (low/medium/high/urgent).
        category: Optional ticket category.

    Returns:
        Created ticket data dict, or None if service unavailable.
    """
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.create_ticket(
                subject=subject,
                description=description,
                customer_id=customer_id,
                priority=priority,
                category=category,
            )
            if hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"id": str(ticket.id), "subject": subject}
    except Exception:
        pass
    return None


def jarvis_get_tickets(
    db: Session,
    company_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Optional[List[Dict[str, Any]]]:
    """List tickets for a company via ticket_service."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            tickets = svc.list_tickets(status=status, limit=limit, offset=offset)
            if isinstance(tickets, list):
                return [
                    t.to_dict() if hasattr(t, "to_dict") else str(t)
                    for t in tickets
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a single ticket by ID."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.get_ticket(ticket_id)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"id": ticket_id} if ticket else None
    except Exception:
        pass
    return None


def jarvis_update_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a ticket's fields."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.update_ticket(ticket_id, **updates)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
    except Exception:
        pass
    return None


def jarvis_delete_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Delete a ticket."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.delete_ticket(ticket_id)
            return {"deleted": True, "ticket_id": ticket_id}
    except Exception:
        pass
    return None


def jarvis_assign_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    assignee_id: str,
) -> Optional[Dict[str, Any]]:
    """Assign a ticket to an agent/user."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.assign_ticket(ticket_id, assignee_id)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
    except Exception:
        pass
    return None


def jarvis_transition_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    target_state: str,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Transition a ticket state via state machine."""
    try:
        sm_cls = _get_service(
            "ticket_state_machine",
            "app.services.ticket_state_machine",
            "TicketStateMachine",
        )
        if sm_cls:
            sm = sm_cls(db, company_id)
            ticket = sm.transition(ticket_id, target_state, reason=reason)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"ticket_id": ticket_id, "new_state": target_state}
    except Exception:
        pass
    return None


def jarvis_classify_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Classify a ticket's intent and urgency."""
    try:
        svc_cls = _get_service(
            "classification_service",
            "app.services.classification_service",
            "ClassificationService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.classify(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "classification": str(result)}
    except Exception:
        pass
    return None


def jarvis_search_tickets(
    db: Session,
    company_id: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
) -> Optional[List[Dict[str, Any]]]:
    """Search tickets via ticket_search_service."""
    try:
        svc_cls = _get_service(
            "ticket_search_service",
            "app.services.ticket_search_service",
            "TicketSearchService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            results = svc.search(query, filters=filters, limit=limit)
            if isinstance(results, list):
                return [
                    r.to_dict() if hasattr(r, "to_dict") else str(r)
                    for r in results
                ]
    except Exception:
        pass
    return None


def jarvis_merge_tickets(
    db: Session,
    company_id: str,
    primary_ticket_id: str,
    secondary_ticket_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Merge multiple tickets into one via ticket_merge_service."""
    try:
        svc_cls = _get_service(
            "ticket_merge_service",
            "app.services.ticket_merge_service",
            "TicketMergeService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.merge_tickets(
                primary_ticket_id, secondary_ticket_ids, company_id,
            )
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"merged": True, "primary": primary_ticket_id}
    except Exception:
        pass
    return None


def jarvis_check_ticket_lifecycle(
    db: Session,
    company_id: str,
    ticket_id: str,
    check_type: str = "duplicate",
) -> Optional[Dict[str, Any]]:
    """Run lifecycle checks (duplicate, out-of-scope, etc.)."""
    try:
        svc_cls = _get_service(
            "ticket_lifecycle_service",
            "app.services.ticket_lifecycle_service",
            "TicketLifecycleService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            if check_type == "duplicate":
                result = svc.check_duplicate(ticket_id)
            elif check_type == "out_of_scope":
                result = svc.check_out_of_plan_scope(ticket_id)
            elif check_type == "ai_cant_solve":
                result = svc.handle_ai_cant_solve(ticket_id)
            elif check_type == "human_request":
                result = svc.handle_human_request(ticket_id)
            else:
                result = svc.check_duplicate(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "check": check_type}
    except Exception:
        pass
    return None


def jarvis_get_ticket_analytics(
    db: Session,
    company_id: str,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """Get ticket analytics summary."""
    try:
        svc_cls = _get_service(
            "ticket_analytics_service",
            "app.services.ticket_analytics_service",
            "TicketAnalyticsService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            summary = svc.get_summary(days=days)
            trends = svc.get_trends(days=days)
            result = {}
            if hasattr(summary, "to_dict"):
                result["summary"] = summary.to_dict()
            if hasattr(trends, "__iter__"):
                result["trends"] = [
                    t.to_dict() if hasattr(t, "to_dict") else str(t)
                    for t in trends
                ]
            return result
    except Exception:
        pass
    return None


def jarvis_detect_stale_tickets(
    db: Session,
    company_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Detect stale tickets that need attention."""
    try:
        svc_cls = _get_service(
            "stale_ticket_service",
            "app.services.stale_ticket_service",
            "StaleTicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            stale = svc.detect_stale_tickets()
            if isinstance(stale, list):
                return [
                    s.to_dict() if hasattr(s, "to_dict") else str(s)
                    for s in stale
                ]
    except Exception:
        pass
    return None


def jarvis_analyze_spam(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Analyze a ticket for spam."""
    try:
        svc_cls = _get_service(
            "spam_detection_service",
            "app.services.spam_detection_service",
            "SpamDetectionService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.analyze_ticket(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "spam_analysis": str(result)}
    except Exception:
        pass
    return None


# ── Analytics ──────────────────────────────────────────────────────


def jarvis_get_analytics(
    db: Session,
    company_id: Optional[str] = None,
    session_id: Optional[str] = None,
    since: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get analytics metrics."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_metrics(
                company_id=company_id,
                session_id=session_id,
                since=since,
            )
    except Exception:
        pass
    return None


def jarvis_get_funnel_metrics() -> Optional[Dict[str, Any]]:
    """Get funnel conversion metrics."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_funnel_metrics()
    except Exception:
        pass
    return None


def jarvis_get_sentiment_metrics(
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get sentiment analysis metrics for a session."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_sentiment_metrics(session_id=session_id)
    except Exception:
        pass
    return None


def jarvis_track_event(
    event_type: str,
    event_category: str,
    user_id: str,
    company_id: str = "",
    session_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    source: str = "jarvis",
) -> Optional[Dict[str, Any]]:
    """Track an analytics event."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.track_event(
                event_type=event_type,
                event_category=event_category,
                user_id=user_id,
                company_id=company_id,
                session_id=session_id,
                properties=properties or {},
                source=source,
            )
    except Exception:
        pass
    return None


# ── Lead Management ───────────────────────────────────────────────


def jarvis_capture_lead(
    session_id: str,
    user_id: str,
    company_id: Optional[str] = None,
    session_context: Optional[Dict[str, Any]] = None,
    sentiment_data: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Capture or update a sales lead."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            return lead_svc.capture_lead(
                session_id=session_id,
                user_id=user_id,
                company_id=company_id,
                session_context=session_context or {},
                sentiment_data=sentiment_data,
            )
    except Exception:
        pass
    return None


def jarvis_get_lead(
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Get lead data for a user."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            lead = lead_svc.get_lead(user_id)
            if lead and hasattr(lead, "to_dict"):
                return lead.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_leads(
    status: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Get all leads, optionally filtered by status."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            if status:
                leads = lead_svc.get_leads_by_status(status)
            else:
                leads = lead_svc.get_all_leads()
            if isinstance(leads, list):
                return [
                    l.to_dict() if hasattr(l, "to_dict") else str(l)
                    for l in leads
                ]
    except Exception:
        pass
    return None


def jarvis_get_lead_stats() -> Optional[Dict[str, Any]]:
    """Get lead statistics."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            return lead_svc.get_lead_stats()
    except Exception:
        pass
    return None


# ── Billing & Usage ───────────────────────────────────────────────


def jarvis_get_usage(
    company_id: str,
    db: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """Get current usage statistics for a company."""
    try:
        svc_cls = _get_service(
            "usage_tracking",
            "app.services.usage_tracking_service",
            "UsageTrackingService",
        )
        if svc_cls:
            svc = svc_cls()
            return svc.get_current_usage(company_id)
    except Exception:
        pass
    return None


def jarvis_check_usage_limit(
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Check if a company is approaching its usage limit."""
    try:
        svc_cls = _get_service(
            "usage_tracking",
            "app.services.usage_tracking_service",
            "UsageTrackingService",
        )
        if svc_cls:
            svc = svc_cls()
            return svc.check_approaching_limit(company_id)
    except Exception:
        pass
    return None


def jarvis_get_invoices(
    company_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> Optional[List[Dict[str, Any]]]:
    """Get invoice list for a company."""
    try:
        svc_fn = _get_service(
            "invoice_service_getter",
            "app.services.invoice_service",
            "get_invoice_service",
        )
        if svc_fn:
            svc = svc_fn()
            invoices = svc.get_invoice_list(company_id, status=status, limit=limit)
            if isinstance(invoices, list):
                return [
                    inv.to_dict() if hasattr(inv, "to_dict") else str(inv)
                    for inv in invoices
                ]
    except Exception:
        pass
    return None


def jarvis_get_invoice(
    company_id: str,
    invoice_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a specific invoice."""
    try:
        svc_fn = _get_service(
            "invoice_service_getter",
            "app.services.invoice_service",
            "get_invoice_service",
        )
        if svc_fn:
            svc = svc_fn()
            invoice = svc.get_invoice(company_id, invoice_id)
            if invoice and hasattr(invoice, "to_dict"):
                return invoice.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_monthly_cost_report(
    db: Session,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get monthly cost/budget report."""
    try:
        svc_cls = _get_service(
            "cost_protection",
            "app.services.cost_protection_service",
            "CostProtectionService",
        )
        if svc_cls:
            svc = svc_cls(db)
            return svc.get_monthly_report(company_id)
    except Exception:
        pass
    return None


# ── Audit & Security ──────────────────────────────────────────────


def jarvis_get_audit_trail(
    db: Session,
    company_id: str,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> Optional[List[Dict[str, Any]]]:
    """Query audit trail entries."""
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            entries = audit_svc.query_audit_trail(
                db=db,
                company_id=company_id,
                actor_type=actor_type,
                action=action,
                offset=offset,
                limit=limit,
            )
            if isinstance(entries, list):
                return [
                    e.to_dict() if hasattr(e, "to_dict") else str(e)
                    for e in entries
                ]
    except Exception:
        pass
    return None


def jarvis_get_audit_stats(
    db: Session,
    company_id: str,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """Get audit statistics."""
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            return audit_svc.get_audit_stats(db=db, company_id=company_id, days=days)
    except Exception:
        pass
    return None


def jarvis_get_audit_log_events(
    company_id: str,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> Optional[List[Dict[str, Any]]]:
    """Query structured audit log events via AuditLogService."""
    try:
        svc_cls = _get_service(
            "audit_log_service",
            "app.services.audit_log_service",
            "AuditLogService",
        )
        if svc_cls:
            svc = svc_cls(config=None)
            events = svc.query_events(
                company_id=company_id,
                category=category,
                severity=severity,
                limit=limit,
            )
            if isinstance(events, list):
                return [
                    e.to_dict() if hasattr(e, "to_dict") else str(e)
                    for e in events
                ]
    except Exception:
        pass
    return None


def jarvis_get_audit_log_stats(
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get audit log statistics."""
    try:
        svc_cls = _get_service(
            "audit_log_service",
            "app.services.audit_log_service",
            "AuditLogService",
        )
        if svc_cls:
            svc = svc_cls(config=None)
            stats = svc.get_statistics(company_id=company_id)
            if hasattr(stats, "to_dict"):
                return stats.to_dict()
            return stats
    except Exception:
        pass
    return None


def jarvis_check_rate_limit(
    redis_client: Any = None,
    key: str = "global",
    category: str = "default",
) -> Optional[Dict[str, Any]]:
    """Check rate limit status."""
    try:
        svc_cls = _get_service(
            "rate_limit_service",
            "app.services.rate_limit_service",
            "RateLimitService",
        )
        if svc_cls:
            svc = svc_cls(redis_client=redis_client)
            result = svc.check_rate_limit(key=key, category=category)
            if hasattr(result, "to_headers"):
                return {
                    "allowed": result.allowed,
                    "remaining": result.remaining,
                    "limit": result.limit,
                    "reset_at": str(result.reset_at) if result.reset_at else None,
                }
            return {"allowed": bool(result)}
    except Exception:
        pass
    return None


# ── Onboarding ────────────────────────────────────────────────────


def jarvis_complete_onboarding_step(
    db: Session,
    user_id: str,
    company_id: str,
    step: str,
) -> Optional[Dict[str, Any]]:
    """Complete an onboarding step."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.complete_step(
                db=db, user_id=user_id, company_id=company_id, step=step,
            )
    except Exception:
        pass
    return None


def jarvis_accept_legal_consents(
    db: Session,
    user_id: str,
    company_id: str,
    accept_terms: bool = True,
    accept_privacy: bool = True,
    accept_ai_data: bool = True,
    client_timestamp: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Accept legal consents during onboarding."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.accept_legal_consents(
                db=db,
                user_id=user_id,
                company_id=company_id,
                accept_terms=accept_terms,
                accept_privacy=accept_privacy,
                accept_ai_data=accept_ai_data,
                client_timestamp=client_timestamp,
                ip_address=ip_address,
                user_agent=user_agent,
            )
    except Exception:
        pass
    return None


def jarvis_activate_ai(
    db: Session,
    user_id: str,
    company_id: str,
    ai_name: str = "Jarvis",
    ai_tone: str = "professional_friendly",
    ai_response_style: str = "concise",
    ai_greeting: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Activate AI for a company during onboarding."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.activate_ai(
                db=db,
                user_id=user_id,
                company_id=company_id,
                ai_name=ai_name,
                ai_tone=ai_tone,
                ai_response_style=ai_response_style,
                ai_greeting=ai_greeting,
            )
    except Exception:
        pass
    return None


def jarvis_get_pricing_variants(
    industry: str,
    variant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get pricing variant details."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            if variant_id:
                return pricing_svc.get_variant_by_id(industry, variant_id)
            return {
                "cheapest": pricing_svc.get_cheapest_variant(industry),
                "popular": pricing_svc.get_popular_variant(industry),
            }
    except Exception:
        pass
    return None


def jarvis_validate_variant_selection(
    industry: str,
    selections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Validate variant selections before purchase."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            return pricing_svc.validate_variant_selection(industry, selections)
    except Exception:
        pass
    return None


def jarvis_calculate_totals(
    validated_selections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Calculate pricing totals for validated selections."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            return pricing_svc.calculate_totals(validated_selections)
    except Exception:
        pass
    return None


# ── Notifications ─────────────────────────────────────────────────


def jarvis_send_notification(
    db: Session,
    company_id: str,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
) -> Optional[Dict[str, Any]]:
    """Send a notification to a user."""
    try:
        svc_cls = _get_service(
            "notification_service",
            "app.services.notification_service",
            "NotificationService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            return svc.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
            )
    except Exception:
        pass
    return None


def jarvis_send_email(
    to: str,
    subject: str,
    html_content: str,
) -> Optional[Dict[str, Any]]:
    """Send an email via email_service."""
    try:
        email_svc = _get_service_module("app.services.email_service")
        if email_svc:
            email_svc.send_email(
                to=to, subject=subject, html_content=html_content,
            )
            return {"sent": True, "to": to}
    except Exception:
        pass
    return {"sent": False, "error": "email_service_unavailable"}


def jarvis_process_webhook(
    company_id: str,
    provider: str,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Process an incoming webhook event."""
    try:
        webhook_svc = _get_service_module("app.services.webhook_service")
        if webhook_svc:
            return webhook_svc.process_webhook(
                company_id=company_id,
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
    except Exception:
        pass
    return None


# ── Customer Management ──────────────────────────────────────────


def jarvis_create_customer(
    db: Session,
    company_id: str,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a customer record."""
    try:
        svc_cls = _get_service(
            "customer_service",
            "app.services.customer_service",
            "CustomerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            customer = svc.create_customer(
                name=name, email=email, phone=phone,
            )
            if customer and hasattr(customer, "to_dict"):
                return customer.to_dict()
            return {"id": str(customer.id), "name": name}
    except Exception:
        pass
    return None


def jarvis_get_customer(
    db: Session,
    company_id: str,
    customer_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a customer by ID."""
    try:
        svc_cls = _get_service(
            "customer_service",
            "app.services.customer_service",
            "CustomerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            customer = svc.get_customer(customer_id)
            if customer and hasattr(customer, "to_dict"):
                return customer.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_company_profile(
    db: Session,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get company profile settings."""
    try:
        company_svc = _get_service_module("app.services.company_service")
        if company_svc:
            return company_svc.get_company_profile(company_id, db)
    except Exception:
        pass
    return None


def jarvis_update_company_profile(
    db: Session,
    company_id: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update company profile settings."""
    try:
        company_svc = _get_service_module("app.services.company_service")
        if company_svc:
            return company_svc.update_company_profile(company_id, data, db)
    except Exception:
        pass
    return None


# ── Supporting Services ───────────────────────────────────────────


def jarvis_auto_tag_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[str]]:
    """Auto-tag a ticket based on content."""
    try:
        svc_cls = _get_service(
            "tag_service",
            "app.services.tag_service",
            "TagService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.auto_tag(ticket_id)
            if isinstance(result, list):
                return result
            if hasattr(result, "tags"):
                return result.tags
    except Exception:
        pass
    return None


def jarvis_detect_category(
    db: Session,
    company_id: str,
    text: str,
) -> Optional[Dict[str, Any]]:
    """Detect ticket category from text."""
    try:
        svc_cls = _get_service(
            "category_service",
            "app.services.category_service",
            "CategoryService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.detect_category(text)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"category": str(result)}
    except Exception:
        pass
    return None


def jarvis_detect_priority(
    db: Session,
    company_id: str,
    text: str,
    customer_tier: str = "standard",
) -> Optional[Dict[str, Any]]:
    """Detect ticket priority from text."""
    try:
        svc_cls = _get_service(
            "priority_service",
            "app.services.priority_service",
            "PriorityService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.detect_priority(text, customer_tier=customer_tier)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"priority": str(result)}
    except Exception:
        pass
    return None


def jarvis_auto_assign_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Auto-assign a ticket to the best agent."""
    try:
        svc_cls = _get_service(
            "assignment_service",
            "app.services.assignment_service",
            "AssignmentService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.auto_assign(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "assigned": str(result)}
    except Exception:
        pass
    return None


def jarvis_get_sla_target(
    db: Session,
    company_id: str,
    priority: str = "medium",
) -> Optional[Dict[str, Any]]:
    """Get SLA target for a priority level."""
    try:
        svc_cls = _get_service(
            "sla_service",
            "app.services.sla_service",
            "SLAService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.get_policy_by_tier_priority(
                company_id=company_id, priority=priority,
            )
            if result and hasattr(result, "to_dict"):
                return result.to_dict()
    except Exception:
        pass
    return None


def jarvis_evaluate_triggers(
    db: Session,
    company_id: str,
    ticket_id: str,
    event_type: str = "created",
) -> Optional[List[Dict[str, Any]]]:
    """Evaluate automation triggers for a ticket event."""
    try:
        svc_cls = _get_service(
            "trigger_service",
            "app.services.trigger_service",
            "TriggerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            results = svc.evaluate_triggers(ticket_id, event_type)
            if isinstance(results, list):
                return [
                    r.to_dict() if hasattr(r, "to_dict") else str(r)
                    for r in results
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_tags(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[str]]:
    """Get tags for a ticket."""
    try:
        svc_cls = _get_service(
            "tag_service",
            "app.services.tag_service",
            "TagService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc._get_ticket(ticket_id) if hasattr(svc, "_get_ticket") else None
            if ticket and hasattr(ticket, "tags"):
                return ticket.tags
    except Exception:
        pass
    return None


def jarvis_get_ticket_notes(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get internal notes for a ticket."""
    try:
        svc_cls = _get_service(
            "internal_note_service",
            "app.services.internal_note_service",
            "InternalNoteService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            notes = svc.list_notes(ticket_id)
            if isinstance(notes, list):
                return [
                    n.to_dict() if hasattr(n, "to_dict") else str(n)
                    for n in notes
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_messages(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get messages for a ticket."""
    try:
        svc_cls = _get_service(
            "message_service",
            "app.services.message_service",
            "MessageService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            messages = svc.list_messages(ticket_id)
            if isinstance(messages, list):
                return [
                    m.to_dict() if hasattr(m, "to_dict") else str(m)
                    for m in messages
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_attachments(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get attachments for a ticket."""
    try:
        svc_cls = _get_service(
            "attachment_service",
            "app.services.attachment_service",
            "AttachmentService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            attachments = svc.get_attachments(ticket_id)
            if isinstance(attachments, list):
                return [
                    a.to_dict() if hasattr(a, "to_dict") else str(a)
                    for a in attachments
                ]
    except Exception:
        pass
    return None


def jarvis_get_channel_config(
    db: Session,
    company_id: str,
    channel: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get channel configuration."""
    try:
        svc_cls = _get_service(
            "channel_service",
            "app.services.channel_service",
            "ChannelService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            if channel:
                return svc.get_channel_config(channel)
            return svc.get_company_channel_config()
    except Exception:
        pass
    return None


def jarvis_execute_bulk_action(
    db: Session,
    company_id: str,
    action_type: str,
    ticket_ids: List[str],
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Execute a bulk action on multiple tickets."""
    try:
        svc_cls = _get_service(
            "bulk_action_service",
            "app.services.bulk_action_service",
            "BulkActionService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.execute_bulk_action(
                company_id=company_id,
                action_type=action_type,
                ticket_ids=ticket_ids,
                params=params or {},
            )
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"action": action_type, "processed": len(ticket_ids)}
    except Exception:
        pass
    return None


def jarvis_get_channels(
    db: Session,
    company_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get available channels for a company."""
    try:
        svc_cls = _get_service(
            "channel_service",
            "app.services.channel_service",
            "ChannelService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            channels = svc.get_available_channels()
            if isinstance(channels, list):
                return channels
    except Exception:
        pass
    return None


def jarvis_scan_pii(
    db: Session,
    company_id: str,
    text: str,
    scan_types: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Scan text for PII via pii_scan_service."""
    try:
        svc_cls = _get_service(
            "pii_scan",
            "app.services.pii_scan_service",
            "PIIScanService",
        )
        if svc_cls:
            scanner = svc_cls(db, company_id)
            return scanner.scan_text(text, scan_types=scan_types)
    except Exception:
        pass
    return None


def jarvis_merge_with_brand_voice(
    db: Session,
    company_id: str,
    response_text: str,
) -> Optional[str]:
    """Merge response text with brand voice configuration."""
    try:
        svc_cls = _get_service(
            "brand_voice",
            "app.services.brand_voice_service",
            "BrandVoiceService",
        )
        if svc_cls:
            svc = svc_cls(db)
            return svc.merge_with_brand_voice(response_text, company_id)
    except Exception:
        pass
    return response_text


# ── Private Helpers ────────────────────────────────────────────────


def _parse_context(context_json: str) -> Dict[str, Any]:
    """Safely parse context_json string."""
    if not context_json:
        return {}
    try:
        return json.loads(context_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_default_system_prompt() -> str:
    """Default Jarvis system prompt — matches frontend buildSystemPrompt."""
    return (
        "You are Jarvis — PARWA's AI assistant 🤖 Think Iron Man's Jarvis: "
        "sharp, friendly, and always helpful.\n\n"

        "YOUR THREE ROLES:\n"
        "1. GUIDE — Walk users through PARWA naturally\n"
        "2. SALESMAN — Show value with real numbers\n"
        "3. DEMO — Roleplay as a customer support agent\n\n"

        "═══════════════════════════════════════════════\n"
        "PARWA — WHAT YOU CAN TELL CUSTOMERS\n"
        "═══════════════════════════════════════════════\n\n"

        "WHAT IS PARWA:\n"
        "AI-powered customer support platform. Businesses deploy AI agents that "
        "handle tickets 24/7 across email, chat, SMS, voice & social media. "
        "700+ features. 4 industries.\n\n"

        "THREE PLANS:\n"
        "🟠 Mini PARWA — $999/mo — 1 agent, 1K tickets/mo, Email+Chat — Saves $156K/yr\n"
        "🟠 PARWA — $2,499/mo — 3 agents, 5K tickets/mo, +SMS+Voice — Saves $186K/yr\n"
        "🟠 PARWA High — $3,999/mo — 5 agents, 15K tickets/mo, all channels — Saves $288K/yr\n\n"

        "INDUSTRIES:\n"
        "• E-commerce (Shopify, WooCommerce, Magento)\n"
        "• SaaS (GitHub, Jira, Slack, Intercom)\n"
        "• Logistics (TMS, WMS, GPS systems)\n"
        "• Healthcare (Epic EHR, HIPAA compliant)\n\n"

        "BILLING: Monthly, cancel anytime. 15% off annual. $0.10 overage/ticket. $1 Demo Pack.\n"
        "SECURITY: GDPR, SOC 2, HIPAA, AES-256, TLS 1.3, audit trail, PII redaction.\n"
        "vs COMPETITORS: 85-92%% savings vs Intercom, Zendesk AI, or hiring agents.\n\n"

        "═══════════════════════════════════════════════\n"
        "STRICT RULES — NEVER VIOLATE THESE:\n"
        "═══════════════════════════════════════════════\n"
        "1. NEVER reveal internal technical details: AI provider names, API keys, "
        "model names, routing logic, inference details, prompt engineering, or architecture.\n"
        "2. NEVER mention Google AI Studio, Cerebras, Groq, or any LLM/AI provider name to users.\n"
        "3. NEVER mention variant counts, internal pricing per variant "
        "($49/$59/$69/$79/$89/$99), or internal SKU names.\n"
        '4. When asked "what models do you use" or "what AI" — say: '
        '"PARWA uses cutting-edge AI that\'s fine-tuned for customer support. '
        'I can tell you about what it can DO for your business! 🚀"\n'
        '5. When asked "how many variants" or "what variants" — redirect to the 3 PLANS '
        "(Mini, PARWA, PARWA High).\n"
        '6. NEVER say "I\'m an AI language model" or "As an AI..." — you ARE Jarvis.\n'
        "7. NEVER break character. You work for PARWA.\n\n"

        "═══════════════════════════════════════════════\n"
        "CHAT STYLE — THIS IS CRITICAL:\n"
        "═══════════════════════════════════════════════\n"
        "• Keep EVERY response SHORT — 2-3 lines max, never a paragraph\n"
        "• Use emojis naturally (not too many, 1-2 per message)\n"
        "• Use bullet points with spaces between items\n"
        "• One idea per message — don't dump everything at once\n"
        "• Leave breathing room between points\n"
        "• Sound like texting a smart friend, NOT a corporate bot\n"
        "• Match their energy — casual if they're casual\n"
        "• When giving options, use 1-2 bullet points max, not a wall of text\n"
        "• ALWAYS end with a question to keep conversation going\n"
        "• If listing plans, use the 3 plan names only (Mini, PARWA, PARWA High) — "
        "no internal details\n"
    )


def _get_default_welcome() -> str:
    """Default welcome message."""
    return (
        "Hey there! 👋 I'm Jarvis from PARWA. Think of me as your personal AI consultant — "
        "I'll help you find the right AI agents for your business. So, what brings you in today?"
    )


def _get_friendly_error_message() -> str:
    """User-friendly error message for unexpected errors."""
    return (
        "I'm having a moment — something went wrong on my end. "
        "Could you try sending that again? "
        "If it keeps happening, refresh the page."
    )


def _get_recent_history(
    db: Session,
    session_id: str,
    limit: int = MAX_CONTEXT_HISTORY_MESSAGES,
) -> List[Dict[str, str]]:
    """Get recent messages for AI context window."""
    messages = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reverse to chronological order
    return [
        {"role": m.role, "content": m.content}
        for m in reversed(messages)
    ]


def _track_pages_visited(
    ctx: Dict[str, Any],
    message: str,
) -> None:
    """Heuristic: detect page/feature mentions in user messages."""
    pages = ctx.get("pages_visited", [])
    lower_msg = message.lower()

    page_keywords = {
        "pricing_page": ["price", "pricing", "cost", "plan", "tier"],
        "features_page": ["feature", "capability", "what can", "what does"],
        "integrations_page": ["integrat", "connect", "api", "webhook"],
        "roi_page": ["roi", "return", "saving", "invest"],
        "demo_page": ["demo", "try", "test", "sample"],
    }

    for page_key, keywords in page_keywords.items():
        if any(kw in lower_msg for kw in keywords):
            if page_key not in pages:
                pages.append(page_key)

    ctx["pages_visited"] = pages


def _call_ai_provider(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    context: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]:
    """Call AI provider for response generation.

    Routes to Cerebras, Groq, or Google AI Studio based on availability.
    Falls back to context-aware placeholder if all providers fail.

    Returns:
        Tuple of (content, message_type, metadata, knowledge_used)
    """
    # Build messages for AI
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Track which knowledge files were used
    knowledge: List[Dict[str, Any]] = []
    try:
        from app.services.jarvis_knowledge_service import search_knowledge
        kb_results = search_knowledge(user_message, context.get("industry"))
        if kb_results:
            for r in kb_results[:3]:
                knowledge.append({
                    "file": r.get("source", "unknown"),
                    "score": r.get("score", 0.5),
                })
    except Exception:
        pass

    # Try real AI providers (Cerebras → Groq → Google)
    content = _try_ai_providers(messages)
    if content is None:
        # Fallback to context-aware placeholder
        content = _get_stage_fallback(context)

    # Determine message type based on stage and context
    stage = context.get("detected_stage", "welcome")
    message_type, metadata = _determine_message_type(stage, context)

    return content, message_type, metadata, knowledge


def _try_ai_providers(messages: List[Dict[str, str]]) -> Optional[str]:
    """Try AI providers in order: Cerebras → Groq → Google. Returns content or None."""
    providers = [
        ("cerebras", "https://api.cerebras.ai/v1/chat/completions"),
        ("groq", "https://api.groq.com/openai/v1/chat/completions"),
        ("google", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"),
    ]

    for provider_name, endpoint in providers:
        try:
            content = _call_single_provider(provider_name, endpoint, messages)
            if content:
                return content
        except Exception:
            continue
    return None


def _call_single_provider(
    provider_name: str,
    endpoint: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """Call a single AI provider and return the response content."""
    from app.config import get_settings

    settings = get_settings()

    if provider_name == "cerebras":
        api_key = settings.CEREBRAS_API_KEY
    elif provider_name == "groq":
        api_key = settings.GROQ_API_KEY
    elif provider_name == "google":
        api_key = settings.GOOGLE_AI_API_KEY
    else:
        return None

    if not api_key:
        return None

    if provider_name == "google":
        return _call_google_api(endpoint, api_key, messages)

    # OpenAI-compatible: Cerebras and Groq
    payload = {
        "model": "llama-3.1-8b" if provider_name == "cerebras" else "llama-3.1-8b",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    import urllib.request
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    return None


def _call_google_api(
    endpoint: str,
    api_key: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """Call Google AI Studio API (non-OpenAI format)."""
    import urllib.request

    # Convert messages to Google's format
    system_text = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            contents.append({"role": "user" if msg["role"] == "user" else "model", "parts": [{"text": msg["content"]}]})

    payload: Dict[str, Any] = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}

    url = f"{endpoint}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
    return None


def _get_stage_fallback(context: Dict[str, Any]) -> str:
    """Context-aware fallback when all AI providers fail."""
    stage = context.get("detected_stage", "welcome")
    response_map = {
        "welcome": (
            "That's great! Let me help you explore what PARWA can do "
            "for your business. Could you tell me a bit more about "
            "your customer support challenges?"
        ),
        "discovery": (
            "Based on what you've shared, I think PARWA would be a "
            "great fit! We have several industry-specific variants "
            "tailored to your needs. Would you like to see the pricing?"
        ),
        "pricing": (
            "Here are the variants I'd recommend based on your needs. "
            "I can generate a detailed bill summary — just let me know "
            "which variants interest you most!"
        ),
        "demo": (
            "The Demo Pack is the best way to experience PARWA firsthand! "
            "For just $1, you'll get 500 messages and a 3-minute AI "
            "voice call. Want me to set that up for you?"
        ),
        "verification": (
            "To proceed, I'll need to verify your business email. "
            "I'll send you a one-time code — it only takes a moment."
        ),
        "payment": (
            "You're almost there! I'll create your checkout now. "
            "PARWA supports monthly and annual billing (2 months free "
            "with annual). Let me get that started."
        ),
        "handoff": (
            "Congratulations! Your onboarding is complete. "
            "I'm now handing you over to Customer Care Jarvis, "
            "who will help you get started with your PARWA account!"
        ),
    }
    return response_map.get(
        stage,
        "I'd be happy to help with that! Could you tell me more "
        "about what you're looking for?",
    )


def _determine_message_type(
    stage: str,
    context: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Determine message_type and metadata based on stage and context."""
    message_type = "text"
    metadata: Dict[str, Any] = {"stage": stage}

    if stage == "pricing" and context.get("selected_variants"):
        message_type = "bill_summary"
        metadata["variants"] = context["selected_variants"]
    elif stage == "demo":
        message_type = "payment_card"
        metadata["pack_type"] = "demo"
    elif stage == "verification":
        message_type = "otp_card"
    elif stage == "handoff":
        message_type = "handoff_card"

    return message_type, metadata
