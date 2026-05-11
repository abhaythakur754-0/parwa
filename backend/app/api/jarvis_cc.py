"""
PARWA Jarvis Customer Care API Router

FastAPI router for Jarvis in Customer Care mode (post-onboarding).
Completely separate from the onboarding jarvis.py router because
CC mode has fundamentally different endpoints and request shapes.

Architecture:
  Client → CC API → jarvis_cc_service → variant_pipeline_bridge → Variant Pipelines

9 endpoints covering:
- Session management (create/resume, get, health)
- Message send with pipeline metadata
- Context get/update
- History (paginated)
- System prompt preview

Auth: All endpoints use get_current_user.
Error format: Matches PARWA standard {"error": {"code": ..., "message": ..., "details": ...}}

BC-001: company_id extracted from authenticated user on every request.
BC-008: Graceful error handling — never crash.
BC-012: All timestamps UTC.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ParwaBaseError
from app.schemas.jarvis_cc import (
    JarvisCCSessionCreate,
    JarvisCCSessionResponse,
    JarvisCCMessageSend,
    JarvisCCMessageResponse,
    JarvisCCHistoryResponse,
    JarvisCCContextResponse,
    JarvisCCContextUpdate,
    JarvisCCSessionHealthResponse,
)
from app.services import jarvis_cc_service
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/jarvis/cc", tags=["Jarvis Customer Care"])


# ══════════════════════════════════════════════════════════════════
# SESSION ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.post("/session", response_model=JarvisCCSessionResponse)
def create_cc_session(
    body: JarvisCCSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or resume a customer care session.

    After onboarding handoff, the client creates a CC session here.
    If an active CC session already exists for this user+company,
    it is resumed. The new session inherits variant_tier and
    industry from the most recent handoff (onboarding) session.

    This is the entry point for the Jarvis CC dashboard.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        session = jarvis_cc_service.get_or_create_cc_session(
            db=db,
            user_id=str(user.id),
            company_id=str(user.company_id),
            existing_session_id=body.existing_session_id,
        )
        return _session_to_response(session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to create customer care session",
            500,
            details={"error": str(exc)},
        )


@router.get("/session", response_model=JarvisCCSessionResponse)
def get_cc_session(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get customer care session details with context and limits."""
    try:
        session = jarvis_cc_service.get_cc_session(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
        )
        return _session_to_response(session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get customer care session",
            500,
            details={"error": str(exc)},
        )


@router.get("/session/health", response_model=JarvisCCSessionHealthResponse)
def get_cc_session_health(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get operational health metrics for a customer care session.

    Returns message counts, pipeline status, variant instance health,
    emergency state, and daily remaining limits.
    Used by the Jarvis CC dashboard for monitoring.
    """
    try:
        health = jarvis_cc_service.get_cc_session_health(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
        )
        return JarvisCCSessionHealthResponse(**health)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get session health",
            500,
            details={"error": str(exc)},
        )


# ══════════════════════════════════════════════════════════════════
# MESSAGE ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.post("/message", response_model=JarvisCCMessageResponse)
def send_cc_message(
    body: JarvisCCMessageSend,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to Jarvis in customer care mode.

    This is the main interaction endpoint. The message is routed
    through the variant pipeline bridge with a 3-level fallback:

    1. variant_pipeline_bridge (primary)
    2. Legacy AI pipeline (fallback 1)
    3. Direct AI provider (fallback 2)

    Response includes pipeline metadata for dashboard display:
    quality_score, technique_used, latency, billing_tokens, etc.
    """
    try:
        user_msg, ai_msg, pipeline_metadata = jarvis_cc_service.send_cc_message(
            db=db,
            session_id=body.session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
            user_message=body.content,
            ticket_id=body.ticket_id,
            channel=body.channel,
        )
        return _ai_message_to_response(ai_msg, pipeline_metadata)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to process customer care message",
            500,
            details={"error": str(exc)},
        )


# ══════════════════════════════════════════════════════════════════
# CONTEXT ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.get("/context", response_model=JarvisCCContextResponse)
def get_cc_context(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current context snapshot for a customer care session.

    Returns both stored context (variant_tier, industry, etc.) and
    runtime-enriched data (instance status, ticket counts, emergency state).
    This is what the awareness engine (Phase 2) will read from.
    """
    try:
        context = jarvis_cc_service.get_cc_context(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
        )
        return JarvisCCContextResponse(
            session_id=session_id,
            variant_tier=context.get("variant_tier", "mini_parwa"),
            variant_instance_id=context.get("variant_instance_id", ""),
            industry=context.get("industry", "general"),
            mode=context.get("mode", "customer_care"),
            awareness_enabled=context.get("awareness_enabled", False),
            pipeline_status=context.get("pipeline_status", "unknown"),
            last_pipeline_metadata=context.get("last_pipeline_metadata", {}),
            proactive_alerts=context.get("proactive_alerts", []),
            runtime=context.get("runtime", {}),
            full_context=context,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get customer care context",
            500,
            details={"error": str(exc)},
        )


@router.patch("/context", response_model=JarvisCCSessionResponse)
def update_cc_context(
    body: JarvisCCContextUpdate,
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge partial updates into the customer care session context.

    Only provided fields are merged. Existing keys are preserved.
    Protected keys (variant_tier, variant_instance_id, industry)
    cannot be overwritten with None.

    This is how the awareness engine (Phase 2) and command executor
    (Phase 3) will update the session context.
    """
    # Build partial updates dict from body
    partial_updates = {}
    if body.awareness_enabled is not None:
        partial_updates["awareness_enabled"] = body.awareness_enabled
    if body.proactive_alerts is not None:
        partial_updates["proactive_alerts"] = body.proactive_alerts
    if body.custom_fields is not None:
        partial_updates.update(body.custom_fields)

    if not partial_updates:
        return _error_response(
            "VALIDATION_ERROR",
            "No fields provided for update",
            422,
        )

    try:
        session = jarvis_cc_service.update_cc_context(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
            partial_updates=partial_updates,
        )
        return _session_to_response(session)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to update customer care context",
            500,
            details={"error": str(exc)},
        )


# ══════════════════════════════════════════════════════════════════
# HISTORY ENDPOINT
# ══════════════════════════════════════════════════════════════════


@router.get("/history", response_model=JarvisCCHistoryResponse)
def get_cc_history(
    session_id: str = Query(..., description="Customer care session ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated message history for a customer care session.

    Returns messages in chronological order (oldest first).
    Each message includes its metadata (pipeline info, channel, etc.).
    """
    try:
        messages, total = jarvis_cc_service.get_cc_history(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
            limit=limit,
            offset=offset,
        )
        return JarvisCCHistoryResponse(
            messages=[
                JarvisCCMessageResponse(
                    id=msg["id"],
                    session_id=session_id,
                    role=msg["role"],
                    content=msg["content"],
                    message_type=msg.get("message_type", "text"),
                    metadata=msg.get("metadata", {}),
                    pipeline_metadata=msg.get("metadata", {}).get("pipeline_metadata", {}),
                    timestamp=msg.get("created_at"),
                )
                for msg in messages
            ],
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get customer care history",
            500,
            details={"error": str(exc)},
        )


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT PREVIEW (DEBUG/ADMIN)
# ══════════════════════════════════════════════════════════════════


@router.get("/prompt")
def get_cc_system_prompt(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview the system prompt for a CC session (debug/admin).

    Returns the full system prompt that would be sent to the AI model.
    Useful for debugging prompt quality and verifying tenant-specific
    context (brand voice, KB, capabilities) is correctly injected.
    """
    try:
        prompt = jarvis_cc_service.build_cc_system_prompt(
            db=db,
            session_id=session_id,
            company_id=str(user.company_id),
        )
        return {"session_id": session_id, "prompt": prompt}
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to generate system prompt",
            500,
            details={"error": str(exc)},
        )


# ══════════════════════════════════════════════════════════════════
# RESPONSE HELPERS
# ══════════════════════════════════════════════════════════════════


def _session_to_response(session: object) -> JarvisCCSessionResponse:
    """Convert JarvisSession ORM model to CC session response."""
    ctx = {}
    try:
        ctx = json.loads(session.context_json) if session.context_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    from app.services.jarvis_cc_service import CC_DAILY_MESSAGE_LIMIT

    remaining = max(0, CC_DAILY_MESSAGE_LIMIT - session.message_count_today)

    return JarvisCCSessionResponse(
        id=str(session.id),
        type=session.type,
        context=ctx,
        message_count_today=session.message_count_today,
        total_message_count=session.total_message_count,
        remaining_today=remaining,
        is_active=session.is_active,
        variant_tier=ctx.get("variant_tier", "mini_parwa"),
        industry=ctx.get("industry", "general"),
        awareness_enabled=ctx.get("awareness_enabled", False),
        pipeline_status=ctx.get("pipeline_status", "unknown"),
        created_at=(
            session.created_at.isoformat() if session.created_at else None
        ),
        updated_at=(
            session.updated_at.isoformat() if session.updated_at else None
        ),
    )


def _ai_message_to_response(
    ai_msg: object,
    pipeline_metadata: dict,
) -> JarvisCCMessageResponse:
    """Convert JarvisMessage ORM model to CC message response."""
    metadata = {}
    try:
        metadata = json.loads(ai_msg.metadata_json) if ai_msg.metadata_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return JarvisCCMessageResponse(
        id=str(ai_msg.id),
        session_id=str(ai_msg.session_id),
        role=ai_msg.role,
        content=ai_msg.content,
        message_type=ai_msg.message_type,
        metadata=metadata,
        pipeline_metadata=pipeline_metadata,
        timestamp=(
            ai_msg.created_at.isoformat() if ai_msg.created_at else None
        ),
    )


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: object = None,
) -> dict:
    """Build a PARWA-standard error response dict."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
