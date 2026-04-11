"""
PARWA Jarvis Service (Week 6 — Day 2 Phase 2)

Core business logic for Jarvis onboarding chat system.

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
    # Tickets
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
