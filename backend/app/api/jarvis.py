"""
PARWA Jarvis API Router (Week 6 — Day 2 Phase 3)

FastAPI router with all Jarvis onboarding endpoints.

22 endpoints covering:
- Session management (create, get, history)
- Message send/receive
- Context management
- Demo pack purchase + status
- OTP verification (send + verify)
- Payment (create, webhook, status)
- Demo call (initiate, verify OTP, summary)
- Handoff (execute, status)
- Action tickets (CRUD)
- Entry context routing

Auth: All endpoints use get_current_user except Paddle webhook.
Error format: Matches PARWA standard {"error": {"code": ..., "message": ..., "details": ...}}

Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
"""

from typing import Optional

import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ParwaBaseError
from app.schemas.jarvis import (
    JarvisSessionCreate,
    JarvisSessionResponse,
    JarvisMessageSend,
    JarvisMessageResponse,
    JarvisHistoryResponse,
    JarvisContextUpdate,
    JarvisEntryContextRequest,
    JarvisOtpRequest,
    JarvisOtpVerify,
    JarvisOtpResponse,
    JarvisDemoPackStatusResponse,
    JarvisPaymentCreate,
    JarvisPaymentStatusResponse,
    JarvisDemoCallRequest,
    JarvisDemoCallVerifyOtp,
    JarvisDemoCallSummaryResponse,
    JarvisHandoffRequest,
    JarvisHandoffStatusResponse,
    JarvisActionTicketCreate,
    JarvisActionTicketUpdateStatus,
    JarvisActionTicketResponse,
    JarvisActionTicketListResponse,
)
from app.services import jarvis_service
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/jarvis", tags=["Jarvis"])


# ── Session Endpoints ──────────────────────────────────────────────


@router.post("/session", response_model=JarvisSessionResponse)
def create_session(
    body: JarvisSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or resume an onboarding session.

    Called on /onboarding page load. If an active session exists,
    it is resumed. Otherwise a new session is created with the
    provided entry context.
    """
    session = jarvis_service.create_or_resume_session(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        entry_source=body.entry_source,
        entry_params=body.entry_params,
    )
    return _session_to_response(db, session)


@router.get("/session", response_model=JarvisSessionResponse)
def get_session(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current session details with context and limits."""
    session = jarvis_service.get_session(db, session_id, user.id)
    return _session_to_response(db, session)


@router.get("/history", response_model=JarvisHistoryResponse)
def get_history(
    session_id: str = Query(..., description="Session ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated chat history for a session."""
    messages, total = jarvis_service.get_history(
        db,
        session_id,
        user.id,
        limit,
        offset,
    )
    return JarvisHistoryResponse(
        messages=[_message_to_response(m) for m in messages],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


# ── Message Endpoints ──────────────────────────────────────────────


@router.post("/message", response_model=JarvisMessageResponse)
def send_message(
    body: JarvisMessageSend,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to Jarvis and get AI response.

    Flow:
    1. Validates message content
    2. Saves user message
    3. Checks daily message limit
    4. Calls AI provider with context
    5. Saves AI response
    6. Returns AI response message

    Rate limited to prevent spam.
    """
    # Resolve session
    session_id = body.session_id
    if not session_id:
        # Find active session for user
        session = jarvis_service.create_or_resume_session(
            db=db,
            user_id=user.id,
            company_id=user.company_id,
        )
        session_id = session.id

    try:
        user_msg, ai_msg, knowledge = jarvis_service.send_message(
            db=db,
            session_id=session_id,
            user_id=user.id,
            user_message=body.content,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        error_info = jarvis_service.handle_error(db, session_id, exc)
        raise  # Re-raise after logging

    response = _message_to_response(ai_msg)
    response.knowledge_used = [
        {"file": ku.get("file", ""), "score": float(ku.get("score", 1.0))}
        for ku in knowledge
    ]
    return response


# ── Context Endpoints ──────────────────────────────────────────────


@router.patch("/context", response_model=JarvisSessionResponse)
def update_context(
    body: JarvisContextUpdate,
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update session context (partial merge).

    Only provided fields are updated. Existing context is preserved.
    Used for tracking variant selections, industry, stage changes, etc.
    """
    updates = body.model_dump(exclude_none=True)
    session = jarvis_service.update_context(
        db=db,
        session_id=session_id,
        user_id=user.id,
        partial_updates=updates,
    )
    return _session_to_response(db, session)


@router.post("/context/entry", response_model=JarvisSessionResponse)
def set_entry_context(
    body: JarvisEntryContextRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set entry source context from URL params.

    Used for non-linear entry routing — Jarvis adapts its welcome
    message based on where the user came from (pricing, ROI, demo, etc.)
    """
    session = jarvis_service.set_entry_context(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        entry_source=body.entry_source,
        entry_params=body.entry_params,
    )
    return _session_to_response(db, session)


# ── Demo Pack Endpoints ────────────────────────────────────────────


@router.post("/demo-pack/purchase")
def purchase_demo_pack(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Purchase the $1 Demo Pack (500 messages + 3-min AI call, 24h).

    In production, creates a Paddle checkout for $1.
    """
    result = jarvis_service.purchase_demo_pack(
        db=db,
        session_id=session_id,
        user_id=user.id,
    )
    return result


@router.get("/demo-pack/status", response_model=JarvisDemoPackStatusResponse)
def demo_pack_status(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current demo pack status and remaining limits."""
    result = jarvis_service.get_demo_pack_status(
        db=db,
        session_id=session_id,
        user_id=user.id,
    )
    return JarvisDemoPackStatusResponse(**result)


# ── OTP Verification Endpoints ─────────────────────────────────────


@router.post("/verify/send-otp", response_model=JarvisOtpResponse)
def send_otp(
    body: JarvisOtpRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Send OTP to business email for verification.

    Generates a 6-digit code valid for 10 minutes.
    Max 3 attempts allowed.
    """
    result = jarvis_service.send_business_otp(
        db=db,
        session_id=session_id,
        user_id=user.id,
        email=body.email,
    )
    return JarvisOtpResponse(
        message=result["message"],
        status=result["status"],
        attempts_remaining=result.get("attempts_remaining"),
        expires_at=result.get("expires_at"),
    )


@router.post("/verify/verify-otp", response_model=JarvisOtpResponse)
def verify_otp(
    body: JarvisOtpVerify,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Verify OTP code sent to business email."""
    result = jarvis_service.verify_business_otp(
        db=db,
        session_id=session_id,
        user_id=user.id,
        code=body.code,
        email=body.email,
    )
    return JarvisOtpResponse(
        message=result["message"],
        status=result["status"],
        attempts_remaining=result.get("attempts_remaining"),
        expires_at=result.get("expires_at"),
    )


# ── Payment Endpoints ──────────────────────────────────────────────


@router.post("/payment/create")
def create_payment(
    body: JarvisPaymentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Create Paddle checkout session for variant purchase.

    Returns checkout URL for redirect.
    """
    result = jarvis_service.create_payment_session(
        db=db,
        session_id=session_id,
        user_id=user.id,
        variants=body.variants,
        industry=body.industry,
    )
    return result


@router.post("/payment/webhook")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Paddle webhook (NO auth — uses Paddle signature).

    Processes payment.success and payment.failed events.
    """
    # Read raw body bytes first (needed for HMAC signature verification)
    raw_body = await request.body()

    try:
        body = json.loads(raw_body)
        event_type = body.get("event_type", "")
        event_data = body.get("data", {})
    except Exception:
        return {
            "error": {
                "code": "INVALID_PAYLOAD",
                "message": "Invalid webhook payload",
                "details": None,
            }
        }

    # Pass request headers for Paddle signature verification in the service
    # layer
    webhook_headers = dict(request.headers)

    try:
        result = jarvis_service.handle_payment_webhook(
            db=db,
            event_type=event_type,
            event_data=event_data,
            headers=webhook_headers,
            raw_payload=raw_body,
        )
        return result
    except ParwaBaseError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Webhook processing failed",
                "details": str(exc),
            }
        }


@router.get("/payment/status", response_model=JarvisPaymentStatusResponse)
def payment_status(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check current payment status for a session."""
    result = jarvis_service.get_payment_status(
        db=db,
        session_id=session_id,
        user_id=user.id,
    )
    return JarvisPaymentStatusResponse(**result)


# ── Demo Call Endpoints ────────────────────────────────────────────


@router.post("/demo-call/initiate")
def initiate_call(
    body: JarvisDemoCallRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Initiate a 3-minute AI voice call.

    Requires active Demo Pack. One call per pack.
    In production, triggers Twilio outbound call.
    """
    result = jarvis_service.initiate_demo_call(
        db=db,
        session_id=session_id,
        user_id=user.id,
        phone=body.phone,
    )
    return result


@router.post("/demo-call/otp")
def verify_call_otp(
    body: JarvisDemoCallVerifyOtp,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Verify phone OTP for demo call.

    In production, this verifies the Twilio phone OTP.
    """
    # Placeholder — in production, verify Twilio OTP
    return {
        "message": "Phone verified. Call will start shortly.",
        "status": "verified",
    }


@router.get("/demo-call/summary", response_model=JarvisDemoCallSummaryResponse)
def call_summary(
    session_id: str = Query(..., description="Session ID"),
    call_id: Optional[str] = Query(None, description="Call ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get post-call summary with topics discussed.

    Returns call duration, topics, key moments, and ROI mapping.
    """
    result = jarvis_service.get_call_summary(
        db=db,
        session_id=session_id,
        user_id=user.id,
        call_id=call_id,
    )
    return JarvisDemoCallSummaryResponse(**result)


# ── Handoff Endpoints ──────────────────────────────────────────────


@router.post("/handoff", response_model=JarvisHandoffStatusResponse)
def execute_handoff(
    body: JarvisHandoffRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Transition from Onboarding Jarvis to Customer Care Jarvis.

    Creates a fresh customer_care session with selective context.
    NO chat history is transferred.
    """
    result = jarvis_service.execute_handoff(
        db=db,
        session_id=session_id,
        user_id=user.id,
    )
    return JarvisHandoffStatusResponse(
        handoff_completed=result["handoff_completed"],
        new_session_id=result.get("new_session_id"),
        handoff_at=result.get("handoff_at"),
    )


@router.get("/handoff/status", response_model=JarvisHandoffStatusResponse)
def handoff_status(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if handoff has been completed for a session."""
    result = jarvis_service.get_handoff_status(
        db=db,
        session_id=session_id,
        user_id=user.id,
    )
    return JarvisHandoffStatusResponse(**result)


# ── Action Ticket Endpoints ────────────────────────────────────────


@router.post("/tickets", response_model=JarvisActionTicketResponse)
def create_ticket(
    body: JarvisActionTicketCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Create an action ticket for tracking a user action."""
    ticket = jarvis_service.create_action_ticket(
        db=db,
        session_id=session_id,
        user_id=user.id,
        ticket_type=body.ticket_type,
        metadata=body.metadata,
    )
    return _ticket_to_response(ticket)


@router.get("/tickets", response_model=JarvisActionTicketListResponse)
def get_tickets(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all action tickets for a session."""
    tickets = jarvis_service.get_tickets(db, session_id, user.id)
    return JarvisActionTicketListResponse(
        tickets=[_ticket_to_response(t) for t in tickets],
        total=len(tickets),
    )


@router.get("/tickets/{ticket_id}", response_model=JarvisActionTicketResponse)
def get_ticket(
    ticket_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single action ticket with result data."""
    ticket = jarvis_service.get_ticket(db, ticket_id, user.id)
    return _ticket_to_response(ticket)


@router.patch(
    "/tickets/{ticket_id}/status",
    response_model=JarvisActionTicketResponse,
)
def update_ticket_status(
    ticket_id: str,
    body: JarvisActionTicketUpdateStatus,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update action ticket status."""
    ticket = jarvis_service.update_ticket_status(
        db=db,
        ticket_id=ticket_id,
        user_id=user.id,
        status=body.status,
    )
    return _ticket_to_response(ticket)


# ── Response Helpers ───────────────────────────────────────────────


def _session_to_response(
    db: Session,
    session: object,
) -> JarvisSessionResponse:
    """Convert JarvisSession ORM model to response schema."""
    from app.services.jarvis_service import check_message_limit

    limit, remaining = check_message_limit(db, session)
    ctx = {}
    try:
        ctx = json.loads(session.context_json) if session.context_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return JarvisSessionResponse(
        id=session.id,
        type=session.type,
        context=ctx,
        message_count_today=session.message_count_today,
        total_message_count=session.total_message_count,
        remaining_today=remaining,
        pack_type=session.pack_type,
        pack_expiry=(session.pack_expiry.isoformat() if session.pack_expiry else None),
        demo_call_used=session.demo_call_used,
        is_active=session.is_active,
        payment_status=session.payment_status,
        handoff_completed=session.handoff_completed,
        detected_stage=ctx.get("detected_stage", "welcome"),
        created_at=(session.created_at.isoformat() if session.created_at else None),
        updated_at=(session.updated_at.isoformat() if session.updated_at else None),
    )


def _message_to_response(msg: object) -> JarvisMessageResponse:
    """Convert JarvisMessage ORM model to response schema."""

    metadata = {}
    try:
        metadata = json.loads(msg.metadata_json) if msg.metadata_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return JarvisMessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        message_type=msg.message_type,
        metadata=metadata,
        timestamp=(msg.created_at.isoformat() if msg.created_at else None),
    )


def _ticket_to_response(
    ticket: object,
) -> JarvisActionTicketResponse:
    """Convert JarvisActionTicket ORM model to response schema."""

    result = {}
    try:
        result = json.loads(ticket.result_json) if ticket.result_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    metadata = {}
    try:
        metadata = json.loads(ticket.metadata_json) if ticket.metadata_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return JarvisActionTicketResponse(
        id=ticket.id,
        session_id=ticket.session_id,
        ticket_type=ticket.ticket_type,
        status=ticket.status,
        result=result,
        metadata=metadata,
        created_at=(ticket.created_at.isoformat() if ticket.created_at else None),
        updated_at=(ticket.updated_at.isoformat() if ticket.updated_at else None),
        completed_at=(ticket.completed_at.isoformat() if ticket.completed_at else None),
    )
