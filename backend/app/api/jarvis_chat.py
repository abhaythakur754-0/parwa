"""
PARWA Jarvis Chat API Router — The Natural Language Interface

This is the API that clients use to talk to Jarvis. They just send a
message and get a natural response back. No commands, no modes, no
technical jargon — just conversation.

The client says: "How's everything going?"
Jarvis responds: "Things are looking good! System is healthy, you've had
47 tickets today, and AI quality is at 94%. Anything specific you want to check?"

The client says: "Pause my AI for a bit"
Jarvis responds: "I'll pause all AI agents for you. They'll stop handling
tickets until you tell me to resume. Shall I go ahead?"

The client says: "Yeah go ahead"
Jarvis responds: "Done! All AI agents are paused. They won't handle any
tickets until you tell me to resume them."

Everything is handled by the orchestrator behind the scenes.

Auth: All endpoints use get_current_user.
BC-001: company_id extracted from authenticated user.
BC-008: Graceful error handling — never crash.
BC-012: All timestamps UTC.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ParwaBaseError
from app.logger import get_logger
from app.schemas.jarvis_chat import (
    JarvisChatRequest,
    JarvisChatResponse,
    JarvisChatCreateSession,
    JarvisChatSessionResponse,
    JarvisChatHistoryResponse,
    JarvisChatHealthResponse,
)
from app.services import jarvis_cc_service
from app.services.jarvis_orchestrator import process_message
from app.services.jarvis_safety_gate import get_pending_status
from app.services.jarvis_function_registry import get_function_names
from database.base import get_db
from database.models.core import User

logger = get_logger("jarvis_chat_api")

router = APIRouter(prefix="/api/jarvis/chat", tags=["Jarvis Chat"])


# ══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════


@router.post("/session", response_model=JarvisChatSessionResponse)
async def create_chat_session(
    body: JarvisChatCreateSession,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Jarvis chat session.

    This is the starting point. The client creates a session, then
    sends messages to it. If an active session exists, it's resumed.

    No technical setup required — just start chatting.
    """
    if not user.company_id:
        return _error_response("VALIDATION_ERROR", "User has no associated company", 422)

    try:
        # Reuse the CC session infrastructure
        session = jarvis_cc_service.get_or_create_cc_session(
            db=db,
            user_id=str(user.id),
            company_id=str(user.company_id),
            existing_session_id=body.existing_session_id,
        )

        # Determine initial mode from session context
        ctx = _safe_parse_json(session.context_json) if session.context_json else {}
        tier = ctx.get("variant_tier", "parwa")
        session_mode = ctx.get("mode", "customer_care")
        mode = "agentic" if session_mode == "customer_care" else "command"

        return JarvisChatSessionResponse(
            session_id=str(session.id),
            session_type=session.session_type,
            variant_tier=tier,
            mode=mode,
            message="Hey! I'm Jarvis. How can I help you today?",
        )

    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("create_chat_session_error")
        return _error_response("INTERNAL_ERROR", "Failed to create chat session", 500, {"error": str(exc)})


@router.get("/session/health", response_model=JarvisChatHealthResponse)
async def get_chat_health(
    session_id: str = Query(..., description="Chat session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the health of the Jarvis chat system.

    Returns status, available functions, pending confirmations,
    and model availability. Useful for frontend status indicators.
    """
    if not user.company_id:
        return _error_response("VALIDATION_ERROR", "User has no associated company", 422)

    try:
        # Check for pending safety confirmation
        pending = get_pending_status(str(user.company_id), session_id)

        # Check function availability
        functions = get_function_names(mode="command", tier="parwa")

        # Check LLM availability
        model_available = False
        try:
            from app.core.llm_gateway import llm_gateway
            model_available = llm_gateway.is_available
        except Exception:
            pass

        return JarvisChatHealthResponse(
            status="healthy",
            mode="command",
            functions_available=len(functions),
            pending_confirmation=pending is not None,
            model_available=model_available,
        )

    except Exception as exc:
        logger.exception("chat_health_error")
        return _error_response("INTERNAL_ERROR", "Health check failed", 500, {"error": str(exc)})


# ══════════════════════════════════════════════════════════════════
# CHAT MESSAGE
# ══════════════════════════════════════════════════════════════════


@router.post("/message", response_model=JarvisChatResponse)
async def send_chat_message(
    body: JarvisChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to Jarvis and get a natural response.

    This is the main interaction endpoint. The client sends their
    message, Jarvis processes it through the full pipeline (mode
    detection, LLM function calling, safety gate, execution), and
    returns a conversational response.

    The client never needs to specify what they want — just talk
    naturally and Jarvis figures it out.
    """
    if not user.company_id:
        return _error_response("VALIDATION_ERROR", "User has no associated company", 422)

    try:
        result = await process_message(
            db=db,
            company_id=str(user.company_id),
            session_id=body.session_id,
            user_id=str(user.id),
            user_message=body.message,
        )

        return JarvisChatResponse(
            response=result.get("response", "I'm not sure how to help with that."),
            mode=result.get("mode", "command"),
            function_called=result.get("function_called"),
            safety_status=result.get("safety_status"),
            execution_result=result.get("execution_result"),
            latency_ms=result.get("latency_ms", 0),
            model=result.get("model", "unknown"),
            tokens_used=result.get("tokens_used", 0),
        )

    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("send_chat_message_error")
        return _error_response("INTERNAL_ERROR", "Failed to process message", 500, {"error": str(exc)})


# ══════════════════════════════════════════════════════════════════
# HISTORY
# ══════════════════════════════════════════════════════════════════


@router.get("/history", response_model=JarvisChatHistoryResponse)
async def get_chat_history(
    session_id: str = Query(..., description="Chat session ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated chat history for a session.

    Returns messages in chronological order with metadata.
    """
    if not user.company_id:
        return _error_response("VALIDATION_ERROR", "User has no associated company", 422)

    try:
        messages, total = jarvis_cc_service.get_cc_history(
            db=db,
            session_id=session_id,
            user_id=str(user.id),
            company_id=str(user.company_id),
            limit=limit,
            offset=offset,
        )

        return JarvisChatHistoryResponse(
            messages=messages,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )

    except ParwaBaseError:
        raise
    except Exception as exc:
        logger.exception("chat_history_error")
        return _error_response("INTERNAL_ERROR", "Failed to get chat history", 500, {"error": str(exc)})


# ══════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: Any) -> Any:
    """Safely parse JSON, returning empty structure on failure."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _error_response(code: str, message: str, status: int, details: Optional[Dict] = None) -> Dict:
    """Build a standard error response."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
