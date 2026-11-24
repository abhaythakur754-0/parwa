"""
PARWA Jarvis Onboarding API — FastAPI Routes

API endpoints for the onboarding Jarvis experience. These routes handle:
  - Session creation, resumption, and deactivation
  - Context updates (stage, variant, industry, concerns, etc.)
  - Message logging (persisted to DB)
  - Email verification
  - Payment recording
  - Demo call initiation
  - Handoff to CC Jarvis
  - Onboarding funnel analytics

These routes are designed to be called by the Next.js frontend's
useJarvisChat hook. The frontend handles AI chat routing locally
(z-ai SDK → Google → Cerebras → Groq → keyword fallback), but
persists session data and logs activities through these backend APIs.

The KEY benefit: every onboarding action is logged to the Activity Store,
which feeds into the awareness engine. This means CC Jarvis has FULL
AWARENESS of what happened during onboarding.

BC-001: company_id enforced on every endpoint.
BC-008: Every endpoint wrapped in try/except — graceful degradation.
BC-012: All timestamps UTC.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.logger import get_logger
from app.api.deps import get_current_user
from database.models.core import User
from database.models.jarvis import JarvisSession
from database.base import get_db

logger = get_logger("jarvis_onboarding_api")


async def enforce_onboarding_identity(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Bind every onboarding operation to the JWT user's tenant and identity.

    These endpoints sit under a public middleware prefix for legacy routing;
    this dependency is therefore the mandatory authentication boundary.
    """
    company_id = request.query_params.get("company_id")
    payload: Dict[str, Any] = {}
    if request.method not in {"GET", "HEAD"}:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid request body")
        company_id = company_id or payload.get("company_id")

    authenticated_company_id = str(user.company_id) if user.company_id else None
    if not authenticated_company_id or str(company_id or "") != authenticated_company_id:
        raise HTTPException(status_code=403, detail="Tenant access denied")

    requested_user_id = payload.get("user_id")
    if requested_user_id and str(requested_user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="User access denied")

    # Tenant ownership alone is not enough: onboarding conversations contain
    # personal business details and must remain private to their creator.
    session_id = (
        payload.get("session_id")
        or request.query_params.get("session_id")
        or request.path_params.get("session_id")
    )
    if session_id:
        session = db.query(JarvisSession).filter(
            JarvisSession.id == str(session_id),
            JarvisSession.company_id == authenticated_company_id,
            JarvisSession.type == "onboarding",
        ).first()
        if not session or str(session.user_id or "") != str(user.id):
            raise HTTPException(status_code=404, detail="Onboarding session not found")

    return user


router = APIRouter(
    prefix="/api/jarvis/onboarding",
    tags=["jarvis-onboarding"],
    dependencies=[Depends(enforce_onboarding_identity)],
)


# ══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════


class CreateSessionRequest(BaseModel):
    company_id: str = Field(..., description="Company ID for BC-001 tenant scoping")
    user_id: Optional[str] = Field(None, description="User ID if logged in")
    entry_source: str = Field("direct", description="Where the user came from")
    entry_params: Optional[Dict[str, Any]] = Field(None, description="URL params from entry point")
    referral_source: Optional[str] = Field(None, description="UTM referral source")
    industry: Optional[str] = Field(None, description="Pre-detected industry")
    preselected_variant: Optional[str] = Field(None, description="Pre-selected variant")
    preselected_plan: Optional[str] = Field(None, description="Pre-selected plan")


class UpdateContextRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    updates: Dict[str, Any] = Field(..., description="Context fields to update")


class AdvanceStageRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    new_stage: str = Field(..., description="Stage to advance to")
    reason: Optional[str] = Field(None, description="Why the stage is advancing")


class LogMessageRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    role: str = Field(..., description="Message role: user, jarvis, system")
    content: str = Field(..., description="Message content")
    message_type: str = Field("text", description="Message type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class EmailVerificationRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    email: str = Field(..., description="Email address to verify")
    verified: bool = Field(..., description="Whether verification succeeded")
    otp_method: str = Field("email", description="OTP delivery method")


class RecordPaymentRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    payment_data: Dict[str, Any] = Field(..., description="Payment details")


class DemoCallRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    call_data: Dict[str, Any] = Field(..., description="Call details")


class HandoffRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    user_id: str = Field(..., description="User ID for CC session")
    handoff_data: Optional[Dict[str, Any]] = Field(None, description="Additional handoff context")


class DeactivateRequest(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    company_id: str = Field(..., description="Company ID for BC-001")
    reason: str = Field("user_left", description="Reason for deactivation")


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.post("/session")
def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new onboarding session.

    Called when a user lands on /jarvis for the first time.
    Creates a DB session and logs the creation to Activity Store.
    """
    try:
        from app.services.jarvis_onboarding_service import create_onboarding_session

        session = create_onboarding_session(
            db=db,
            company_id=request.company_id,
            user_id=str(current_user.id),
            entry_source=request.entry_source,
            entry_params=request.entry_params,
            referral_source=request.referral_source,
            industry=request.industry,
            preselected_variant=request.preselected_variant,
            preselected_plan=request.preselected_plan,
        )

        # Parse context for response
        ctx = json.loads(session.context_json) if session.context_json else {}

        return {
            "success": True,
            "session_id": str(session.id),
            "context": ctx,
            "stage": ctx.get("detected_stage", "welcome"),
            "pack_type": session.pack_type,
            "remaining_messages": ctx.get("remaining_messages", 20),
        }

    except Exception as e:
        logger.exception("create_session_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/session/{session_id}")
def get_session(
    session_id: str,
    company_id: str = Query(..., description="Company ID for BC-001"),
    db: Session = Depends(get_db),
):
    """Get an onboarding session by ID."""
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_session

        session = get_onboarding_session(db, session_id, company_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        ctx = json.loads(session.context_json) if session.context_json else {}

        return {
            "success": True,
            "session_id": str(session.id),
            "context": ctx,
            "stage": ctx.get("detected_stage", "welcome"),
            "is_active": session.is_active,
            "pack_type": session.pack_type,
            "remaining_messages": ctx.get("remaining_messages", 20),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_session_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/session/resume")
def resume_session(
    session_id: str = Query(..., description="Session ID to resume"),
    company_id: str = Query(..., description="Company ID for BC-001"),
    db: Session = Depends(get_db),
):
    """Resume an existing onboarding session."""
    try:
        from app.services.jarvis_onboarding_service import resume_onboarding_session

        result = resume_onboarding_session(db, session_id, company_id)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found or inactive")

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("resume_session_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.patch("/context")
def update_context(request: UpdateContextRequest, db: Session = Depends(get_db)):
    """Update the onboarding session context.

    Called whenever the frontend detects a context change —
    variant selection, industry change, ROI calculation, etc.
    """
    try:
        from app.services.jarvis_onboarding_service import update_onboarding_context

        updated_ctx = update_onboarding_context(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            updates=request.updates,
        )

        if not updated_ctx:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "success": True,
            "context": updated_ctx,
            "stage": updated_ctx.get("detected_stage", "welcome"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_context_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/stage/advance")
def advance_stage(request: AdvanceStageRequest, db: Session = Depends(get_db)):
    """Advance the onboarding session to a new stage."""
    try:
        from app.services.jarvis_onboarding_service import advance_stage

        new_stage = advance_stage(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            new_stage=request.new_stage,
            reason=request.reason,
        )

        if not new_stage:
            raise HTTPException(status_code=400, detail="Stage transition not allowed")

        return {"success": True, "stage": new_stage}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("advance_stage_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/message")
def log_message(request: LogMessageRequest, db: Session = Depends(get_db)):
    """Log a chat message to the onboarding session.

    Persists messages to DB and logs user messages to Activity Store.
    """
    try:
        from app.services.jarvis_onboarding_service import (
            log_onboarding_message,
            get_onboarding_session,
        )

        msg = log_onboarding_message(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            role=request.role,
            content=request.content,
            message_type=request.message_type,
            metadata=request.metadata,
        )

        if not msg:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get updated remaining messages
        session = get_onboarding_session(db, request.session_id, request.company_id)
        ctx = json.loads(session.context_json) if session and session.context_json else {}

        return {
            "success": True,
            "message_id": str(msg.id),
            "remaining_messages": ctx.get("remaining_messages", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("log_message_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/verify-email")
def verify_email(
    request: EmailVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record email verification during onboarding."""
    try:
        from app.services.jarvis_onboarding_service import record_email_verification

        # The request's boolean is not proof. Trust only the OTP service's
        # persisted verification record for this tenant and email.
        from app.services.business_email_otp_service import check_business_email_verified
        verified = check_business_email_verified(
            db=db,
            email=request.email,
            company_id=request.company_id,
            user_id=str(current_user.id),
        )
        if request.verified and not verified:
            raise HTTPException(status_code=403, detail="Email OTP has not been verified")

        success = record_email_verification(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            email=request.email,
            verified=verified,
            otp_method=request.otp_method,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "success": True,
            "verified": verified,
            "stage": "verification" if verified else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("verify_email_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/payment")
def record_payment(request: RecordPaymentRequest, db: Session = Depends(get_db)):
    """Record a completed payment during onboarding."""
    # A browser request must never be able to mark a payment complete.
    # Payment completion is recorded only by the signed Razorpay webhook
    # handled by /api/billing/razorpay/webhook.
    raise HTTPException(
        status_code=410,
        detail="Client-side payment recording is disabled; payment status is confirmed by the verified provider webhook.",
    )


@router.post("/demo-call")
def initiate_demo_call(request: DemoCallRequest, db: Session = Depends(get_db)):
    """Record a demo call initiation during onboarding."""
    try:
        from app.services.jarvis_onboarding_service import record_demo_call

        success = record_demo_call(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            call_data=request.call_data,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"success": True, "call_status": "initiated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("demo_call_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/handoff")
def execute_handoff(
    request: HandoffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the handoff from onboarding to CC Jarvis.

    This is the final step — creates a CC session with full onboarding context.
    """
    try:
        from app.services.jarvis_onboarding_service import execute_handoff

        result = execute_handoff(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            user_id=str(current_user.id),
            handoff_data=request.handoff_data,
        )

        if not result:
            raise HTTPException(status_code=404, detail="Session not found or handoff failed")

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("handoff_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/deactivate")
def deactivate_session(request: DeactivateRequest, db: Session = Depends(get_db)):
    """Deactivate an onboarding session (user left/dropped off)."""
    try:
        from app.services.jarvis_onboarding_service import deactivate_session

        success = deactivate_session(
            db=db,
            session_id=request.session_id,
            company_id=request.company_id,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("deactivate_session_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/funnel-metrics")
def get_funnel_metrics(
    company_id: str = Query(..., description="Company ID for BC-001"),
    hours: int = Query(24, description="Hours of history to analyze"),
    db: Session = Depends(get_db),
):
    """Get onboarding funnel metrics for a tenant.

    Used by the awareness engine and analytics dashboards.
    """
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_funnel_metrics

        metrics = get_onboarding_funnel_metrics(
            db=db,
            company_id=company_id,
            hours=hours,
        )

        return {"success": True, "metrics": metrics}

    except Exception as e:
        logger.exception("funnel_metrics_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/awareness")
def get_onboarding_awareness(
    company_id: str = Query(..., description="Company ID for BC-001"),
    hours: int = Query(1, description="Hours of history"),
    db: Session = Depends(get_db),
):
    """Get onboarding-specific awareness data.

    This feeds into the awareness engine as Domain 11.
    """
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_awareness

        awareness = get_onboarding_awareness(
            db=db,
            company_id=company_id,
            hours=hours,
        )

        return {"success": True, "awareness": awareness}

    except Exception as e:
        logger.exception("onboarding_awareness_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])
