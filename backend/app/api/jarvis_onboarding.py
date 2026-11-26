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

from app.api.deps import get_current_user
from app.logger import get_logger
from database.models.core import User
from database.models.jarvis import JarvisSession
from database.base import get_db

logger = get_logger("jarvis_onboarding_api")


async def enforce_onboarding_identity(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Bind onboarding access to the authenticated tenant and session owner."""
    authenticated_company_id = str(user.company_id) if user.company_id else None
    if not authenticated_company_id:
        raise HTTPException(status_code=403, detail="A company account is required")

    payload: Dict[str, Any] = {}
    if request.method not in {"GET", "HEAD"}:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid request body")

    requested_company_id = (
        request.query_params.get("company_id") or payload.get("company_id")
    )
    if requested_company_id and str(requested_company_id) != authenticated_company_id:
        raise HTTPException(status_code=403, detail="Tenant access denied")

    requested_user_id = payload.get("user_id")
    if requested_user_id and str(requested_user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="User access denied")

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
    dependencies=[Depends(get_current_user), Depends(enforce_onboarding_identity)],
)


def _require_company_id(user: User) -> str:
    """Use the authenticated tenant, never the request-supplied company ID."""
    if not user.company_id:
        raise HTTPException(status_code=403, detail="A company account is required")
    return str(user.company_id)


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
def create_session(request: CreateSessionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new onboarding session.

    Called when a user lands on /jarvis for the first time.
    Creates a DB session and logs the creation to Activity Store.
    """
    try:
        from app.services.jarvis_onboarding_service import create_onboarding_session

        session = create_onboarding_session(
            db=db,
            company_id=_require_company_id(current_user),
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
    company_id: Optional[str] = Query(None, description="Ignored; tenant comes from JWT"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an onboarding session by ID."""
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_session

        session = get_onboarding_session(db, session_id, _require_company_id(current_user))
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
    company_id: Optional[str] = Query(None, description="Ignored; tenant comes from JWT"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resume an existing onboarding session."""
    try:
        from app.services.jarvis_onboarding_service import resume_onboarding_session

        result = resume_onboarding_session(db, session_id, _require_company_id(current_user))
        if not result:
            raise HTTPException(status_code=404, detail="Session not found or inactive")

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("resume_session_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.patch("/context")
def update_context(request: UpdateContextRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update the onboarding session context.

    Called whenever the frontend detects a context change —
    variant selection, industry change, ROI calculation, etc.
    """
    try:
        from app.services.jarvis_onboarding_service import update_onboarding_context

        updated_ctx = update_onboarding_context(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
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
def advance_stage(request: AdvanceStageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Advance the onboarding session to a new stage."""
    try:
        from app.services.jarvis_onboarding_service import advance_stage

        new_stage = advance_stage(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
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
def log_message(request: LogMessageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
            company_id=_require_company_id(current_user),
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
def verify_email(request: EmailVerificationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Record email verification during onboarding."""
    try:
        from app.services.jarvis_onboarding_service import record_email_verification
        from app.services.business_email_otp_service import check_business_email_verified

        company_id = _require_company_id(current_user)
        if not request.verified or not check_business_email_verified(
            db=db,
            email=request.email,
            company_id=company_id,
        ):
            raise HTTPException(status_code=403, detail="Email OTP verification is required")

        success = record_email_verification(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
            email=request.email,
            verified=request.verified,
            otp_method=request.otp_method,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "success": True,
            "verified": request.verified,
            "stage": "verification" if request.verified else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("verify_email_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/payment")
def record_payment(request: RecordPaymentRequest, current_user: User = Depends(get_current_user)):
    """Reject client-reported payment state; only a verified provider webhook may activate it."""
    _require_company_id(current_user)
    raise HTTPException(
        status_code=410,
        detail="Direct onboarding payment recording is disabled. Complete payment through verified billing checkout.",
    )


@router.post("/demo-call")
def initiate_demo_call(request: DemoCallRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Record a demo call initiation during onboarding."""
    try:
        from app.services.jarvis_onboarding_service import record_demo_call

        success = record_demo_call(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
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
def execute_handoff(request: HandoffRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Execute the handoff from onboarding to CC Jarvis.

    This is the final step — creates a CC session with full onboarding context.
    """
    try:
        from app.services.jarvis_onboarding_service import execute_handoff

        result = execute_handoff(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
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
def deactivate_session(request: DeactivateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deactivate an onboarding session (user left/dropped off)."""
    try:
        from app.services.jarvis_onboarding_service import deactivate_session

        success = deactivate_session(
            db=db,
            session_id=request.session_id,
            company_id=_require_company_id(current_user),
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
    company_id: Optional[str] = Query(None, description="Ignored; tenant comes from JWT"),
    hours: int = Query(24, description="Hours of history to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get onboarding funnel metrics for a tenant.

    Used by the awareness engine and analytics dashboards.
    """
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_funnel_metrics

        metrics = get_onboarding_funnel_metrics(
            db=db,
            company_id=_require_company_id(current_user),
            hours=hours,
        )

        return {"success": True, "metrics": metrics}

    except Exception as e:
        logger.exception("funnel_metrics_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/awareness")
def get_onboarding_awareness(
    company_id: Optional[str] = Query(None, description="Ignored; tenant comes from JWT"),
    hours: int = Query(1, description="Hours of history"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get onboarding-specific awareness data.

    This feeds into the awareness engine as Domain 11.
    """
    try:
        from app.services.jarvis_onboarding_service import get_onboarding_awareness

        awareness = get_onboarding_awareness(
            db=db,
            company_id=_require_company_id(current_user),
            hours=hours,
        )

        return {"success": True, "awareness": awareness}

    except Exception as e:
        logger.exception("onboarding_awareness_endpoint_failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])
