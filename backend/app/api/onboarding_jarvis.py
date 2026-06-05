"""
PARWA Onboarding Jarvis API Router — The Pre-Purchase AI Assistant

This is the API that potential clients use to interact with Onboarding
Jarvis — the AI that sells itself by demonstrating real capabilities.

The client says: "Show me how you'd handle a return request"
Jarvis responds: "I'd be happy to show you! Let me walk you through it..."

The client says: "Is this too expensive for a small business?"
Jarvis responds: "Great question — let me show you the numbers..."

Everything flows through the orchestrator which uses LLM function calling
to route to the right agent (guide/salesman/demo/call) and execute
actions (show pricing, send OTP, create payment session, etc.).

Endpoints:
  POST /api/onboarding-jarvis/session               — Create or resume session
  GET  /api/onboarding-jarvis/session               — Get current session + context
  GET  /api/onboarding-jarvis/history               — Paginated chat history
  POST /api/onboarding-jarvis/message               — Send message + get AI response
  PATCH /api/onboarding-jarvis/context               — Update session context
  POST /api/onboarding-jarvis/entry                 — Set entry source from URL params
  POST /api/onboarding-jarvis/demo-pack/purchase    — Buy $1 demo pack
  GET  /api/onboarding-jarvis/demo-pack/status      — Demo pack status
  POST /api/onboarding-jarvis/verify/send-otp       — Send OTP to business email
  POST /api/onboarding-jarvis/verify/verify-otp     — Verify OTP code
  POST /api/onboarding-jarvis/payment/create        — Create Paddle checkout session
  POST /api/onboarding-jarvis/handoff               — Execute handoff to customer care

Auth: All endpoints use get_current_user.
BC-001: company_id extracted from authenticated user.
BC-008: Graceful error handling — never crash.
BC-012: All timestamps UTC.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ParwaBaseError
from app.logger import get_logger
from app.services import jarvis_service
from app.services.onboarding_jarvis_orchestrator import process_onboarding_message
from database.base import get_db
from database.models.core import User
from database.models.jarvis import JarvisSession, JarvisMessage

logger = get_logger("onboarding_jarvis_api")

router = APIRouter(prefix="/api/onboarding-jarvis", tags=["Onboarding Jarvis"])


# ══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════


class OnboardingSessionCreateRequest(BaseModel):
    """Create or resume an onboarding Jarvis session."""

    entry_source: str = Field(
        default="direct",
        description="Where the user came from (pricing, roi, demo, etc.)",
    )
    entry_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional URL params (variant_id, industry, etc.)",
    )


class OnboardingSessionResponse(BaseModel):
    """Onboarding session details with context and limits."""

    session_id: str
    session_type: str = "onboarding"
    context: Dict[str, Any] = Field(default_factory=dict)
    message_count_today: int = 0
    total_message_count: int = 0
    remaining_today: int = 20
    pack_type: str = "free"
    pack_expiry: Optional[str] = None
    demo_call_used: bool = False
    is_active: bool = True
    payment_status: str = "none"
    handoff_completed: bool = False
    detected_stage: str = "welcome"

    model_config = {"from_attributes": True}


class OnboardingMessageRequest(BaseModel):
    """Send a message to Onboarding Jarvis."""

    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (optional, uses active session if omitted)",
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="User message text",
    )
    channel: str = Field(
        default="chat",
        description="Channel: 'chat' or 'call'",
    )


class OnboardingMessageResponse(BaseModel):
    """AI response with metadata."""

    session_id: str
    content: str
    message_type: str = "text"
    function_called: Optional[str] = None
    function_result: Optional[Dict[str, Any]] = None
    card_type: str = "none"
    card_data: Dict[str, Any] = Field(default_factory=dict)
    stage: str = "welcome"
    remaining_today: int = 20
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnboardingHistoryMessage(BaseModel):
    """A single message in chat history."""

    id: str
    role: str
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class OnboardingHistoryResponse(BaseModel):
    """Paginated chat history."""

    messages: List[OnboardingHistoryMessage]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class OnboardingContextUpdateRequest(BaseModel):
    """Partial update to session context_json."""

    industry: Optional[str] = Field(default=None, max_length=50)
    selected_variants: Optional[List[Dict[str, Any]]] = None
    roi_result: Optional[Dict[str, Any]] = None
    demo_topics: Optional[List[str]] = None
    concerns_raised: Optional[List[str]] = None
    business_email: Optional[str] = Field(default=None, max_length=255)
    email_verified: Optional[bool] = None
    detected_stage: Optional[str] = None


class OnboardingEntryRequest(BaseModel):
    """Set entry source context from URL params."""

    entry_source: str = Field(description="Where the user came from")
    entry_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="URL params (variant_id, industry, etc.)",
    )


class OnboardingDemoPackPurchaseRequest(BaseModel):
    """Purchase $1 demo pack request."""

    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Email for purchase receipt",
    )


class OnboardingDemoPackStatusResponse(BaseModel):
    """Demo pack status response."""

    pack_type: str
    remaining_today: int
    total_allowed: int
    pack_expiry: Optional[str] = None
    demo_call_remaining: bool = True


class OnboardingOtpRequest(BaseModel):
    """Send OTP to business email."""

    email: str = Field(
        min_length=5,
        max_length=255,
        description="Business email address",
    )


class OnboardingOtpVerifyRequest(BaseModel):
    """Verify OTP code."""

    email: str = Field(
        min_length=5,
        max_length=255,
        description="Email that received the OTP",
    )
    code: str = Field(
        min_length=4,
        max_length=6,
        description="OTP code",
    )


class OnboardingOtpResponse(BaseModel):
    """OTP send/verify response."""

    message: str
    status: str
    attempts_remaining: Optional[int] = None
    expires_at: Optional[str] = None


class OnboardingPaymentCreateRequest(BaseModel):
    """Create Paddle checkout session."""

    plan_id: str = Field(description="Subscription plan (mini_parwa, parwa, parwa_high)")
    variant_ids: List[str] = Field(
        description="Variant IDs to include in the subscription",
    )
    email: str = Field(description="Verified business email")
    billing_period: str = Field(default="monthly", description="monthly or annual")


class OnboardingHandoffRequest(BaseModel):
    """Execute handoff to customer care."""

    pass


class OnboardingHandoffResponse(BaseModel):
    """Handoff status response."""

    handoff_completed: bool
    new_session_id: Optional[str] = None
    handoff_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════


@router.post("/session", response_model=OnboardingSessionResponse)
async def create_session(
    body: OnboardingSessionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or resume an onboarding session.

    Called when the user opens the onboarding chat. If an active
    session exists, it is resumed. Otherwise a new session is created
    with the provided entry context.
    """
    try:
        session = jarvis_service.create_or_resume_session(
            db=db,
            user_id=user.id,
            company_id=user.company_id,
            entry_source=body.entry_source,
            entry_params=body.entry_params,
        )
        return _session_to_response(db, session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("create_onboarding_session_error: user=%s", user.id)
        return _error_response("INTERNAL_ERROR", "Failed to create session", 500)


@router.get("/session", response_model=OnboardingSessionResponse)
async def get_session(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current session details with context and limits."""
    try:
        session = jarvis_service.get_session(db, session_id, user.id)
        return _session_to_response(db, session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("get_onboarding_session_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to get session", 500)


# ══════════════════════════════════════════════════════════════════
# CHAT HISTORY
# ══════════════════════════════════════════════════════════════════


@router.get("/history", response_model=OnboardingHistoryResponse)
async def get_history(
    session_id: str = Query(..., description="Session ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated chat history for a session."""
    try:
        messages, total = jarvis_service.get_history(
            db, session_id, user.id, limit, offset,
        )

        history_messages = []
        for msg in messages:
            metadata = {}
            try:
                metadata = json.loads(msg.metadata_json) if msg.metadata_json else {}
            except (json.JSONDecodeError, TypeError):
                pass

            history_messages.append(OnboardingHistoryMessage(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                message_type=msg.message_type,
                metadata=metadata,
                timestamp=msg.created_at.isoformat() if msg.created_at else None,
            ))

        return OnboardingHistoryResponse(
            messages=history_messages,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("get_onboarding_history_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to get history", 500)


# ══════════════════════════════════════════════════════════════════
# MESSAGE — The main chat endpoint
# ══════════════════════════════════════════════════════════════════


@router.post("/message", response_model=OnboardingMessageResponse)
async def send_message(
    body: OnboardingMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to Onboarding Jarvis and get AI response.

    Flow:
      1. Check/create onboarding session
      2. Check message limits (20/day free, 500/day demo pack)
      3. Reset daily counter if new day
      4. Call process_onboarding_message from the orchestrator
      5. Save user message and AI response to DB
      6. Return response with metadata (remaining messages, stage, card data)
    """
    try:
        # Step 1: Resolve or create session
        session_id = body.session_id
        if not session_id:
            session = jarvis_service.create_or_resume_session(
                db=db,
                user_id=user.id,
                company_id=user.company_id,
            )
            session_id = str(session.id)

        # Step 2: Get session and check limits
        session = db.query(JarvisSession).filter(
            JarvisSession.id == session_id,
            JarvisSession.user_id == user.id,
        ).first()

        if not session:
            return _error_response("NOT_FOUND", "Session not found", 404)

        # Step 3: Reset daily counter if new day
        _maybe_reset_daily_counter(db, session)

        # Step 4: Check message limit
        limit_info = _check_message_limit(session)
        if limit_info["remaining"] <= 0:
            # Save user message even if limit reached
            _save_message(db, session_id, "user", body.message, "text")

            # Save limit-reached response
            limit_msg = (
                "You've reached your daily message limit. "
                "Upgrade to the Demo Pack for 500 messages/day + a 3-minute AI call!"
            )
            _save_message(db, session_id, "jarvis", limit_msg, "limit_reached")

            return OnboardingMessageResponse(
                session_id=session_id,
                content=limit_msg,
                message_type="limit_reached",
                card_type="recharge_cta",
                card_data={
                    "pack_type": session.pack_type,
                    "remaining_today": 0,
                    "total_allowed": limit_info["limit"],
                },
                stage=_get_stage(session),
                remaining_today=0,
            )

        # Step 5: Save user message
        _save_message(db, session_id, "user", body.message, "text")

        # Step 6: Call the orchestrator (primary pipeline)
        company_id = str(user.company_id) if user.company_id else ""
        user_id = str(user.id)

        result = await process_onboarding_message(
            db=db,
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            user_message=body.message,
            channel=body.channel,
        )

        # Step 7: Increment message counters
        session.message_count_today += 1
        session.total_message_count += 1
        db.flush()

        # Step 8: Save AI response
        ai_content = result.get("content", "I'm having trouble processing that. Could you try again?")
        ai_message_type = result.get("message_type", "text")
        function_called = result.get("function_called")
        function_result = result.get("function_result")

        # Build metadata for the AI message
        ai_metadata = {
            "model": result.get("metadata", {}).get("model", "unknown"),
            "function_called": function_called,
            "stage": result.get("metadata", {}).get("stage", ""),
        }
        if function_result:
            ai_metadata["function_success"] = function_result.get("success", False)

        _save_message(
            db, session_id, "jarvis", ai_content,
            ai_message_type, json.dumps(ai_metadata),
        )

        # Step 9: Get updated remaining count
        updated_limit = _check_message_limit(session)

        # Step 10: Detect card type from function result
        card_type, card_data = _extract_card_data(result, session)

        # Update detected_stage in context if orchestrator detected one
        _update_stage_if_changed(db, session, result)

        return OnboardingMessageResponse(
            session_id=session_id,
            content=ai_content,
            message_type=ai_message_type,
            function_called=function_called,
            function_result=function_result,
            card_type=card_type,
            card_data=card_data,
            stage=_get_stage(session),
            remaining_today=updated_limit["remaining"],
            metadata=result.get("metadata", {}),
        )

    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("onboarding_message_error: user=%s", user.id)
        return _error_response("INTERNAL_ERROR", "Failed to process message", 500)


# ══════════════════════════════════════════════════════════════════
# CONTEXT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


@router.patch("/context", response_model=OnboardingSessionResponse)
async def update_context(
    body: OnboardingContextUpdateRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update session context (partial merge).

    Only provided fields are updated. Existing context is preserved.
    Used for tracking variant selections, industry, stage changes, etc.
    """
    try:
        updates = body.model_dump(exclude_none=True)
        session = jarvis_service.update_context(
            db=db,
            session_id=session_id,
            user_id=user.id,
            partial_updates=updates,
        )
        return _session_to_response(db, session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("update_onboarding_context_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to update context", 500)


@router.post("/entry", response_model=OnboardingSessionResponse)
async def set_entry(
    body: OnboardingEntryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set entry source context from URL params.

    Used for non-linear entry routing — Jarvis adapts its welcome
    message based on where the user came from (pricing, ROI, demo, etc.)
    """
    try:
        session = jarvis_service.set_entry_context(
            db=db,
            user_id=user.id,
            company_id=user.company_id,
            entry_source=body.entry_source,
            entry_params=body.entry_params,
        )
        return _session_to_response(db, session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("set_onboarding_entry_error: user=%s", user.id)
        return _error_response("INTERNAL_ERROR", "Failed to set entry context", 500)


# ══════════════════════════════════════════════════════════════════
# DEMO PACK
# ══════════════════════════════════════════════════════════════════


@router.post("/demo-pack/purchase")
async def purchase_demo_pack(
    body: OnboardingDemoPackPurchaseRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase the $1 Demo Pack (500 messages + 3-min AI call, 24h).

    In production, creates a Paddle checkout for $1.
    """
    try:
        result = jarvis_service.purchase_demo_pack(
            db=db,
            session_id=session_id,
            user_id=user.id,
        )
        return result
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("purchase_demo_pack_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to purchase demo pack", 500)


@router.get("/demo-pack/status", response_model=OnboardingDemoPackStatusResponse)
async def demo_pack_status(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current demo pack status and remaining limits."""
    try:
        result = jarvis_service.get_demo_pack_status(
            db=db,
            session_id=session_id,
            user_id=user.id,
        )
        return OnboardingDemoPackStatusResponse(
            pack_type=result.get("pack_type", "free"),
            remaining_today=result.get("remaining_today", 20),
            total_allowed=result.get("total_allowed", 20),
            pack_expiry=result.get("pack_expiry"),
            demo_call_remaining=result.get("demo_call_remaining", True),
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("demo_pack_status_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to get demo pack status", 500)


# ══════════════════════════════════════════════════════════════════
# OTP VERIFICATION
# ══════════════════════════════════════════════════════════════════


@router.post("/verify/send-otp", response_model=OnboardingOtpResponse)
async def send_otp(
    body: OnboardingOtpRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send OTP to business email for verification.

    Generates a 6-digit code valid for 10 minutes.
    Max 3 attempts allowed.
    """
    try:
        result = jarvis_service.send_business_otp(
            db=db,
            session_id=session_id,
            user_id=user.id,
            email=body.email,
        )
        return OnboardingOtpResponse(
            message=result["message"],
            status=result["status"],
            attempts_remaining=result.get("attempts_remaining"),
            expires_at=result.get("expires_at"),
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("send_otp_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to send OTP", 500)


@router.post("/verify/verify-otp", response_model=OnboardingOtpResponse)
async def verify_otp(
    body: OnboardingOtpVerifyRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify OTP code sent to business email."""
    try:
        result = jarvis_service.verify_business_otp(
            db=db,
            session_id=session_id,
            user_id=user.id,
            code=body.code,
            email=body.email,
        )
        return OnboardingOtpResponse(
            message=result["message"],
            status=result["status"],
            attempts_remaining=result.get("attempts_remaining"),
            expires_at=result.get("expires_at"),
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("verify_otp_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to verify OTP", 500)


# ══════════════════════════════════════════════════════════════════
# PAYMENT
# ══════════════════════════════════════════════════════════════════


@router.post("/payment/create")
async def create_payment(
    body: OnboardingPaymentCreateRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Paddle checkout session for variant purchase.

    Returns checkout URL for redirect.
    """
    try:
        # Convert variant_ids to the format jarvis_service expects
        variants = [{"id": vid, "quantity": 1} for vid in body.variant_ids]

        result = jarvis_service.create_payment_session(
            db=db,
            session_id=session_id,
            user_id=user.id,
            variants=variants,
            industry=body.plan_id,  # Use plan_id as industry context
        )
        return result
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("create_payment_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to create payment session", 500)


# ══════════════════════════════════════════════════════════════════
# HANDOFF
# ══════════════════════════════════════════════════════════════════


@router.post("/handoff", response_model=OnboardingHandoffResponse)
async def execute_handoff(
    body: OnboardingHandoffRequest,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transition from Onboarding Jarvis to Customer Care Jarvis.

    Creates a fresh customer_care session with selective context.
    NO chat history is transferred.
    """
    try:
        result = jarvis_service.execute_handoff(
            db=db,
            session_id=session_id,
            user_id=user.id,
        )
        return OnboardingHandoffResponse(
            handoff_completed=result.get("handoff_completed", False),
            new_session_id=result.get("new_session_id"),
            handoff_at=result.get("handoff_at"),
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("execute_handoff_error: session=%s", session_id)
        return _error_response("INTERNAL_ERROR", "Failed to execute handoff", 500)


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _session_to_response(db: Session, session: object) -> OnboardingSessionResponse:
    """Convert JarvisSession ORM model to API response."""
    try:
        limit_info = jarvis_service.check_message_limit(db, session)
    except Exception:
        limit_info = {"limit": 20, "remaining": 20}

    ctx = {}
    try:
        ctx = json.loads(session.context_json) if session.context_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return OnboardingSessionResponse(
        session_id=str(session.id),
        session_type=session.type,
        context=ctx,
        message_count_today=session.message_count_today,
        total_message_count=session.total_message_count,
        remaining_today=limit_info.get("remaining", 20),
        pack_type=session.pack_type,
        pack_expiry=(
            session.pack_expiry.isoformat() if session.pack_expiry else None
        ),
        demo_call_used=session.demo_call_used,
        is_active=session.is_active,
        payment_status=session.payment_status,
        handoff_completed=session.handoff_completed,
        detected_stage=ctx.get("detected_stage", "welcome"),
    )


def _save_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    metadata_json: str = "{}",
) -> None:
    """Save a message to the database."""
    try:
        msg = JarvisMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_json=metadata_json,
        )
        db.add(msg)
        db.flush()
    except Exception:
        logger.exception("save_message_error: session=%s", session_id)


def _maybe_reset_daily_counter(db: Session, session: JarvisSession) -> None:
    """Reset daily message counter if it's a new day (BC-012 UTC)."""
    try:
        now = datetime.now(timezone.utc)
        if session.last_message_date:
            last_date = session.last_message_date
            if hasattr(last_date, "date"):
                last_date = last_date.date() if hasattr(last_date, "date") else last_date
            current_date = now.date()
            if last_date != current_date:
                session.message_count_today = 0
                session.last_message_date = now
                db.flush()
        else:
            session.last_message_date = now
            db.flush()
    except Exception:
        logger.debug("daily_reset_non_fatal", exc_info=True)


def _check_message_limit(session: JarvisSession) -> Dict[str, int]:
    """Check message limit and return remaining count."""
    try:
        limit = 500 if session.pack_type == "demo" else 20
        remaining = max(0, limit - session.message_count_today)
        return {"limit": limit, "remaining": remaining}
    except Exception:
        return {"limit": 20, "remaining": 20}


def _get_stage(session: JarvisSession) -> str:
    """Extract detected_stage from session context."""
    try:
        ctx = json.loads(session.context_json) if session.context_json else {}
        return ctx.get("detected_stage", "welcome")
    except (json.JSONDecodeError, TypeError):
        return "welcome"


def _update_stage_if_changed(
    db: Session, session: JarvisSession, result: Dict[str, Any],
) -> None:
    """Update detected_stage in session context if the orchestrator detected a new stage."""
    try:
        new_stage = result.get("metadata", {}).get("stage", "")
        if not new_stage:
            return

        ctx = json.loads(session.context_json) if session.context_json else {}
        old_stage = ctx.get("detected_stage", "welcome")

        if new_stage != old_stage:
            ctx["detected_stage"] = new_stage
            session.context_json = json.dumps(ctx)
            session.updated_at = datetime.now(timezone.utc)
            db.flush()
    except Exception:
        logger.debug("update_stage_non_fatal", exc_info=True)


def _extract_card_data(
    result: Dict[str, Any], session: JarvisSession,
) -> tuple:
    """Extract card type and data from the orchestrator result."""
    try:
        function_called = result.get("function_called")
        function_result = result.get("function_result", {})

        if not function_called:
            return "none", {}

        # Map function calls to card types
        card_map = {
            "show_bill_summary": ("bill_summary", function_result),
            "show_pricing": ("payment_card", function_result),
            "send_business_otp": ("otp_card", function_result),
            "verify_business_otp": ("otp_card", function_result),
            "purchase_demo_pack": ("payment_card", function_result),
            "create_payment_session": ("payment_card", function_result),
            "book_demo_call": ("demo_call_card", function_result),
            "execute_handoff": ("handoff_card", function_result),
        }

        if function_called in card_map:
            card_type, card_data = card_map[function_called]
            return card_type, card_data

        return "none", {}
    except Exception:
        return "none", {}


def _error_response(
    code: str, message: str, status: int, details: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build a standard error response."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
