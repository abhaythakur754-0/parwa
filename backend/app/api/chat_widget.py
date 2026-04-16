"""
Chat Widget API Endpoints — Week 13 Day 4 (F-122: Live Chat Widget)

Provides:
- POST /api/v1/chat/session — Create new chat session
- GET /api/v1/chat/sessions — List chat sessions
- GET /api/v1/chat/sessions/{id} — Get session detail
- POST /api/v1/chat/sessions/{id}/assign — Assign agent
- POST /api/v1/chat/sessions/{id}/close — Close session
- POST /api/v1/chat/sessions/{id}/messages — Send message
- GET /api/v1/chat/sessions/{id}/messages — Get messages
- POST /api/v1/chat/sessions/{id}/typing — Typing indicator
- POST /api/v1/chat/sessions/{id}/read — Mark messages read
- POST /api/v1/chat/sessions/{id}/rate — CSAT rating
- GET /api/v1/chat/widget/config — Get widget config (public)
- PUT /api/v1/chat/widget/config — Update widget config (admin)
- GET /api/v1/chat/widget/embed — Get embed code (admin)
- GET /api/v1/chat/canned — List canned responses
- POST /api/v1/chat/canned — Create canned response
- PUT /api/v1/chat/canned/{id} — Update canned response
- DELETE /api/v1/chat/canned/{id} — Delete canned response

BC-001: All endpoints scoped to company_id.
BC-005: Messages trigger Socket.io events.
BC-011: Visitor tokens are HMAC-signed, not JWT.
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("parwa.chat_widget_api")

router = APIRouter(prefix="/api/v1/chat", tags=["Chat Widget"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    try:
        from database.base import get_db
        return next(get_db())
    except Exception:
        from database.base import SessionLocal
        return SessionLocal()


# ═══════════════════════════════════════════════════════════════
# Session Endpoints
# ═══════════════════════════════════════════════════════════════


@router.post("/session")
async def create_chat_session(request: Request):
    """Create a new chat widget session.

    No authentication required — visitors are unauthenticated.
    The company_id is extracted from the request body or query.
    An HMAC-signed visitor_token is returned for subsequent requests.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    company_id = body.get("company_id") or request.query_params.get("company_id")
    if not company_id:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "company_id is required (BC-001)",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.create_session(company_id, body)

        if result.get("status") == "error":
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )

        return result
    except Exception as exc:
        logger.error(
            "chat_session_create_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to create chat session",
                    "details": None,
                }
            },
        )


@router.get("/sessions")
async def list_chat_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    assigned_agent_id: Optional[str] = Query(None),
):
    """List chat sessions with pagination and filters.

    Requires authentication (company_id from middleware).
    """
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        return service.list_sessions(
            company_id=company_id,
            page=page,
            page_size=page_size,
            status=status,
            assigned_agent_id=assigned_agent_id,
        )
    except Exception as exc:
        logger.error(
            "chat_sessions_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list sessions",
                    "details": None,
                }
            },
        )


@router.get("/sessions/{session_id}")
async def get_chat_session(request: Request, session_id: str):
    """Get a single chat session by ID."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        session = service.get_session(session_id, company_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Session {session_id} not found",
                        "details": None,
                    }
                },
            )
        return session.to_dict()
    except Exception as exc:
        logger.error(
            "chat_session_get_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve session",
                    "details": None,
                }
            },
        )


@router.post("/sessions/{session_id}/assign")
async def assign_session(request: Request, session_id: str):
    """Assign an agent to a chat session."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    agent_id = body.get("agent_id")
    if not agent_id:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "agent_id is required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.assign_session(session_id, company_id, agent_id)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "chat_assign_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to assign session",
                    "details": None,
                }
            },
        )


@router.post("/sessions/{session_id}/close")
async def close_session(request: Request, session_id: str):
    """Close a chat session."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    except Exception:
        body = {}

    closer_id = body.get("closer_id") or getattr(request.state, "user_id", None)

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.close_session(session_id, company_id, closer_id)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "chat_close_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to close session",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# Message Endpoints
# ═══════════════════════════════════════════════════════════════


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(request: Request, session_id: str):
    """Send a message in a chat session.

    Visitors can send messages using their HMAC visitor_token.
    Agents use JWT authentication.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    # BC-011: Determine company_id from JWT auth or verify visitor token
    company_id = getattr(request.state, "company_id", None)
    visitor_token = body.get("visitor_token")

    if not company_id and visitor_token:
        # Verify HMAC visitor token (BC-011)
        try:
            db_tmp = _get_db(request)
            from app.services.chat_widget_service import ChatWidgetService
            tmp_svc = ChatWidgetService(db_tmp)
            if not tmp_svc.verify_visitor_token(session_id, body.get("company_id", ""), visitor_token):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "AUTHENTICATION_ERROR",
                            "message": "Invalid visitor token",
                            "details": None,
                        }
                    },
                )
            company_id = body.get("company_id")
        except Exception:
            pass

    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Authentication required (JWT or visitor token)",
                    "details": None,
                }
            },
        )

    content = body.get("content", "")
    role = body.get("role", "visitor")
    sender_id = body.get("sender_id") or getattr(request.state, "user_id", None)
    sender_name = body.get("sender_name")
    message_type = body.get("message_type", "text")

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.send_message(
            session_id=session_id,
            company_id=company_id,
            content=content,
            role=role,
            sender_id=sender_id,
            sender_name=sender_name,
            message_type=message_type,
            attachments_json=body.get("attachments_json", "[]"),
            quick_replies_json=body.get("quick_replies_json", "[]"),
        )

        if result.get("status") == "error":
            status_code = 422 if "rate" in result["error"].lower() else 404
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR" if status_code == 422 else "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )

        return result
    except Exception as exc:
        logger.error(
            "chat_message_send_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to send message",
                    "details": None,
                }
            },
        )


@router.get("/sessions/{session_id}/messages")
async def get_chat_messages(
    request: Request,
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get messages for a chat session with pagination."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        return service.get_messages(
            session_id=session_id,
            company_id=company_id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error(
            "chat_messages_get_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get messages",
                    "details": None,
                }
            },
        )


@router.post("/sessions/{session_id}/typing")
async def send_typing_indicator(request: Request, session_id: str):
    """Emit a typing indicator via Socket.io (BC-005, BC-011)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    # BC-011: Verify visitor token if no JWT auth
    company_id = getattr(request.state, "company_id", None)
    visitor_token = body.get("visitor_token")
    if not company_id and visitor_token:
        try:
            from app.services.chat_widget_service import ChatWidgetService
            tmp_svc = ChatWidgetService(_get_db(request))
            if not tmp_svc.verify_visitor_token(session_id, body.get("company_id", ""), visitor_token):
                return JSONResponse(status_code=401, content={"error": {"code": "AUTHENTICATION_ERROR", "message": "Invalid visitor token", "details": None}})
            company_id = body.get("company_id")
        except Exception:
            pass

    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Authentication required (JWT or visitor token)",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        return service.send_typing_indicator(
            session_id=session_id,
            company_id=company_id,
            user_id=body.get("user_id") or getattr(request.state, "user_id", None),
            role=body.get("role", "visitor"),
            is_typing=body.get("is_typing", True),
        )
    except Exception as exc:
        logger.error(
            "chat_typing_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to send typing indicator",
                    "details": None,
                }
            },
        )


@router.post("/sessions/{session_id}/read")
async def mark_messages_read(request: Request, session_id: str):
    """Mark all unread messages in a session as read."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    reader_id = getattr(request.state, "user_id", None)

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        count = service.mark_messages_read(
            session_id=session_id,
            company_id=company_id,
            reader_id=reader_id,
        )
        return {"status": "ok", "count": count}
    except Exception as exc:
        logger.error(
            "chat_read_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to mark messages read",
                    "details": None,
                }
            },
        )


@router.post("/sessions/{session_id}/rate")
async def submit_csat_rating(request: Request, session_id: str):
    """Submit a CSAT rating for a chat session (BC-011)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    # BC-011: Verify visitor token if no JWT auth
    company_id = getattr(request.state, "company_id", None)
    visitor_token = body.get("visitor_token")
    if not company_id and visitor_token:
        try:
            from app.services.chat_widget_service import ChatWidgetService
            tmp_svc = ChatWidgetService(_get_db(request))
            if not tmp_svc.verify_visitor_token(session_id, body.get("company_id", ""), visitor_token):
                return JSONResponse(status_code=401, content={"error": {"code": "AUTHENTICATION_ERROR", "message": "Invalid visitor token", "details": None}})
            company_id = body.get("company_id")
        except Exception:
            pass

    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Authentication required (JWT or visitor token)",
                    "details": None,
                }
            },
        )

    rating = body.get("rating")
    if rating is None or not 1 <= rating <= 5:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Rating must be between 1 and 5",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.submit_csat_rating(
            session_id=session_id,
            company_id=company_id,
            rating=rating,
            comment=body.get("comment"),
        )
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "chat_csat_error",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to submit rating",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# Widget Config Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/widget/config")
async def get_widget_config(request: Request):
    """Get widget configuration (public endpoint).

    Used by the chat widget JavaScript to load config.
    No JWT auth required — only company_id needed.
    """
    company_id = (
        getattr(request.state, "company_id", None)
        or request.query_params.get("company_id")
    )
    if not company_id:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "company_id is required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        config = service.get_or_create_widget_config(company_id)
        return config.to_dict()
    except Exception as exc:
        logger.error(
            "widget_config_get_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get widget config",
                    "details": None,
                }
            },
        )


@router.put("/widget/config")
async def update_widget_config(request: Request):
    """Update widget configuration (admin only)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.update_widget_config(company_id, body)
        return result
    except Exception as exc:
        logger.error(
            "widget_config_update_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update widget config",
                    "details": None,
                }
            },
        )


@router.get("/widget/embed")
async def get_widget_embed(request: Request):
    """Get widget embed code (admin only)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        return service.get_widget_embed_info(company_id)
    except Exception as exc:
        logger.error(
            "widget_embed_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get embed info",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# Canned Response Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/canned")
async def list_canned_responses(
    request: Request,
    category: Optional[str] = Query(None),
):
    """List canned responses for the tenant."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        items = service.list_canned_responses(
            company_id=company_id,
            category=category,
        )
        return {"items": items, "total": len(items)}
    except Exception as exc:
        logger.error(
            "canned_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list canned responses",
                    "details": None,
                }
            },
        )


@router.post("/canned")
async def create_canned_response(request: Request):
    """Create a new canned response."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    if not body.get("title") or not body.get("content"):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "title and content are required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        created_by = getattr(request.state, "user_id", None)
        result = service.create_canned_response(company_id, body, created_by)
        return result
    except Exception as exc:
        logger.error(
            "canned_create_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to create canned response",
                    "details": None,
                }
            },
        )


@router.put("/canned/{response_id}")
async def update_canned_response(request: Request, response_id: str):
    """Update a canned response."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        updated_by = getattr(request.state, "user_id", None)
        result = service.update_canned_response(
            response_id, company_id, body, updated_by,
        )
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "canned_update_error",
            extra={
                "company_id": company_id,
                "response_id": response_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update canned response",
                    "details": None,
                }
            },
        )


@router.delete("/canned/{response_id}")
async def delete_canned_response(request: Request, response_id: str):
    """Delete a canned response."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.chat_widget_service import ChatWidgetService
        service = ChatWidgetService(db, company_id)
        result = service.delete_canned_response(response_id, company_id)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "canned_delete_error",
            extra={
                "company_id": company_id,
                "response_id": response_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to delete canned response",
                    "details": None,
                }
            },
        )
