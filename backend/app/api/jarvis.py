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

import logging
from typing import Optional

import json

from fastapi import APIRouter, Depends, Query, Request, HTTPException
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
    JarvisDemoPackPurchase,
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

# Semaphore to limit concurrent Jarvis chat requests.
# Render Starter has WEB_CONCURRENCY=1 (single worker). Without this,
# many concurrent Jarvis users all hit sync DB calls + LLM calls
# simultaneously, exhausting the DB pool and freezing the event loop.
#
# MAX_CONCURRENT_JARVIS = 5 (matches 3 LLM providers × ~15 RPM each
# = ~45 RPM combined, ÷ 2 LLM calls per message = ~22 users, but we
# cap at 5 for safety on 512MB RAM).
#
# 6th+ user waits briefly in async queue (no thread blocking).
# Like MAX_CONCURRENT_PIPELINES=10 for tickets.
import asyncio as _asyncio_mod
import os as _os
# Only 2 Jarvis chats run at once — rest wait in async queue (3-5s).
# Each chat = 1 LLM call (~2-4s). With 2 concurrent:
#   - 2 users: complete in ~2-4s each
#   - 3rd-4th users: wait ~2-4s, then complete (~4-8s total)
#   - 5th-6th users: wait ~4-8s, then complete (~6-12s total)
#   - 7th-8th users: wait ~6-12s, then complete (~8-16s total)
# This keeps DB contention low (only 2 concurrent sync DB sessions)
# so the event loop stays responsive — no more freeze.
MAX_CONCURRENT_JARVIS = int(_os.environ.get("MAX_CONCURRENT_JARVIS", "2"))
_JARVIS_SEMAPHORE = _asyncio_mod.Semaphore(MAX_CONCURRENT_JARVIS)

# Hard cap per chat message — the same 30s the queue worker enforces.
# Without it, a hung LLM provider call hangs the user's chat until the
# gateway kills it with 504 (~60s) — reproduced live on parwa.buzz.
JARVIS_MESSAGE_TIMEOUT_S = int(_os.environ.get("JARVIS_MESSAGE_TIMEOUT_S", "30"))

logger = logging.getLogger("parwa.api.jarvis")


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
        db, session_id, user.id, limit, offset,
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
async def send_message(
    body: JarvisMessageSend,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to Jarvis and get AI response (ASYNC).

    ASYNC FIX (2026-08-12): Was sync — blocked the FastAPI event loop for
    up to 60s per LLM call (sync urllib). Now async so concurrent ticket
    processing and Jarvis chat can run side-by-side without stalling.

    Flow:
    1. Validates message content
    2. Saves user message
    3. Checks daily message limit
    4. Calls AI provider with context (async)
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

    # Limit concurrent Jarvis requests to prevent server freeze.
    # Render Starter has WEB_CONCURRENCY=1 (single worker). Without this
    # semaphore, 3+ concurrent users all hit the sync DB calls + LLM
    # simultaneously, exhausting the DB pool and freezing the event loop.
    # With this semaphore, only 1 Jarvis request runs at a time; others
    # wait briefly in the async queue (cooperative, no thread blocking).
    async with _JARVIS_SEMAPHORE:
        try:
            user_msg, ai_msg, knowledge = await _asyncio_mod.wait_for(
                jarvis_service.send_message(
                    db=db,
                    session_id=session_id,
                    user_id=user.id,
                    user_message=body.content,
                ),
                timeout=JARVIS_MESSAGE_TIMEOUT_S,
            )
        except _asyncio_mod.TimeoutError:
            logger.warning(
                "jarvis_message_timeout session=%s after %ss",
                session_id, JARVIS_MESSAGE_TIMEOUT_S,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Jarvis is taking too long to reply. "
                    "Please try again in a moment."
                ),
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
    """Legacy demo-pack checkout is disabled until payment activation is persisted."""
    jarvis_service.get_session(db, session_id, str(user.id))
    raise HTTPException(
        status_code=410,
        detail="Demo Pack checkout is temporarily unavailable. No payment has been taken.",
    )


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


@router.post("/verify/send-otp")
def send_otp(
    body: JarvisOtpRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Send a user-scoped business email OTP without exposing the code."""
    from datetime import datetime, timedelta, timezone
    from app.services.business_email_otp_service import send_business_email_otp
    from app.services.jarvis.chat import _parse_context

    if not user.company_id:
        raise HTTPException(status_code=403, detail="User is not associated with a company")

    session = jarvis_service.get_session(db, session_id, str(user.id))
    if session.type != "onboarding" or str(session.company_id or "") != str(user.company_id):
        raise HTTPException(status_code=404, detail="Onboarding session not found")

    result = send_business_email_otp(
        db=db,
        email=body.email,
        user_id=str(user.id),
        company_id=str(user.company_id),
        user_name=user.full_name,
    )

    # Keep OTP secrets only in the dedicated hashed OTP table, never in
    # session context returned by the session API.
    context = _parse_context(session.context_json)
    context.pop("otp", None)
    context["business_email"] = body.email.strip().lower()
    context["email_verified"] = False
    session.context_json = json.dumps(context)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(result["expires_in"]))
    return {
        "message": result["message"],
        "status": "sent",
        "attempts_remaining": 5,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/verify/verify-otp", response_model=JarvisOtpResponse)
def verify_otp(
    body: JarvisOtpVerify,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Verify the persisted, user-scoped business email OTP."""
    from datetime import datetime, timezone
    from app.services.business_email_otp_service import verify_business_email_otp
    from app.services.jarvis.chat import _parse_context

    if not user.company_id:
        raise HTTPException(status_code=403, detail="User is not associated with a company")

    session = jarvis_service.get_session(db, session_id, str(user.id))
    if session.type != "onboarding" or str(session.company_id or "") != str(user.company_id):
        raise HTTPException(status_code=404, detail="Onboarding session not found")

    result = verify_business_email_otp(
        db=db,
        email=body.email,
        otp_code=body.code,
        company_id=str(user.company_id),
        user_id=str(user.id),
    )

    context = _parse_context(session.context_json)
    context.pop("otp", None)
    context["business_email"] = body.email.strip().lower()
    context["email_verified"] = True
    session.context_json = json.dumps(context)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    return JarvisOtpResponse(
        message=result["message"],
        status=result["status"],
        attempts_remaining=result.get("attempts_remaining"),
        expires_at=None,
    )


# ── Payment Endpoints ──────────────────────────────────────────────


@router.post("/payment/create")
def create_payment(
    body: JarvisPaymentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="Session ID"),
):
    """Disable the legacy client-priced payment flow."""
    jarvis_service.get_session(db, session_id, str(user.id))
    raise HTTPException(
        status_code=410,
        detail="Legacy Jarvis checkout is disabled. Use the authenticated Razorpay subscription checkout with server-owned pricing.",
    )


@router.post("/payment/webhook")
async def payment_webhook(request: Request):
    """Reject the legacy unsigned webhook; use the signed Razorpay webhook route."""
    raise HTTPException(
        status_code=410,
        detail="Legacy Jarvis payment webhook is disabled. Use /api/billing/razorpay/webhook.",
    )


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

    R-03 FIX: No longer a placeholder bypass — now delegates to the
    jarvis_service layer which validates the OTP code against the
    stored value. Rejects invalid/expired OTPs instead of always
    returning "verified".
    """
    result = jarvis_service.verify_demo_call_otp(
        db=db,
        session_id=session_id,
        user_id=user.id,
        otp_code=body.code,
    )
    return result


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
    db: Session, session: object,
) -> JarvisSessionResponse:
    """Convert JarvisSession ORM model to response schema."""
    from app.services.jarvis_service import check_message_limit

    limit, remaining = check_message_limit(db, session)
    ctx = {}
    try:
        ctx = json.loads(session.context_json) if session.context_json else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("session_context_json_parse_error error=%s", str(e))

    return JarvisSessionResponse(
        id=session.id,
        type=session.type,
        context=ctx,
        message_count_today=session.message_count_today,
        total_message_count=session.total_message_count,
        remaining_today=remaining,
        pack_type=session.pack_type,
        pack_expiry=(
            session.pack_expiry.isoformat() if session.pack_expiry else None
        ),
        demo_call_used=session.demo_call_used,
        is_active=session.is_active,
        payment_status=session.payment_status,
        handoff_completed=session.handoff_completed,
        detected_stage=ctx.get("detected_stage", "welcome"),
        created_at=(
            session.created_at.isoformat() if session.created_at else None
        ),
        updated_at=(
            session.updated_at.isoformat() if session.updated_at else None
        ),
    )


def _message_to_response(msg: object) -> JarvisMessageResponse:
    """Convert JarvisMessage ORM model to response schema."""

    metadata = {}
    try:
        metadata = json.loads(msg.metadata_json) if msg.metadata_json else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("message_metadata_json_parse_error error=%s", str(e))

    return JarvisMessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        message_type=msg.message_type,
        metadata=metadata,
        timestamp=(
            msg.created_at.isoformat() if msg.created_at else None
        ),
    )


def _ticket_to_response(
    ticket: object,
) -> JarvisActionTicketResponse:
    """Convert JarvisActionTicket ORM model to response schema."""

    result = {}
    try:
        result = json.loads(ticket.result_json) if ticket.result_json else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("ticket_result_json_parse_error error=%s", str(e))

    metadata = {}
    try:
        metadata = (
            json.loads(ticket.metadata_json) if ticket.metadata_json else {}
        )
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("ticket_metadata_json_parse_error error=%s", str(e))

    return JarvisActionTicketResponse(
        id=ticket.id,
        session_id=ticket.session_id,
        ticket_type=ticket.ticket_type,
        status=ticket.status,
        result=result,
        metadata=metadata,
        created_at=(
            ticket.created_at.isoformat() if ticket.created_at else None
        ),
        updated_at=(
            ticket.updated_at.isoformat() if ticket.updated_at else None
        ),
        completed_at=(
            ticket.completed_at.isoformat() if ticket.completed_at else None
        ),
    )
