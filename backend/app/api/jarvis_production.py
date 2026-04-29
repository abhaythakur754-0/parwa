"""
PARWA Jarvis Production API Routes

FastAPI router endpoints for Production Jarvis (post-onboarding).

Endpoints:
- POST /api/jarvis/prod/chat       - Main chat endpoint
- GET  /api/jarvis/prod/context    - Get current context/awareness
- GET  /api/jarvis/prod/history    - Get conversation history
- GET  /api/jarvis/prod/memory     - Get stored memories
- POST /api/jarvis/prod/action     - Execute or draft an action
- GET  /api/jarvis/prod/drafts     - List pending drafts
- POST /api/jarvis/prod/drafts/{id}/approve - Approve draft
- POST /api/jarvis/prod/drafts/{id}/cancel  - Cancel draft
- GET  /api/jarvis/prod/alerts     - Get active alerts
- POST /api/jarvis/prod/alerts/{id}/acknowledge - Acknowledge alert
- GET  /api/jarvis/prod/status     - Get system status summary
- POST /api/jarvis/prod/track      - Track user activity (for awareness)

Based on: JARVIS_Production_Documentation.md
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_company_id
from app.logger import get_logger
from database.base import get_db
from database.models.core import User
from app.services import jarvis_production_service as jps

logger = get_logger("jarvis_production_api")

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# Request/Response Models
# ══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = None
    auto_execute: bool = False


class ActionRequest(BaseModel):
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    force_draft: bool = False


class TrackActivityRequest(BaseModel):
    event_type: str
    event_name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    page_url: Optional[str] = None
    page_name: Optional[str] = None


class MemoryStoreRequest(BaseModel):
    category: str
    key: str
    value: Any
    importance: int = Field(default=5, ge=1, le=10)


# ══════════════════════════════════════════════════════════════════
# Main Chat Endpoint
# ══════════════════════════════════════════════════════════════════

@router.post("/api/jarvis/prod/chat")
async def jarvis_production_chat(
    request: Request,
    body: ChatRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Main Production Jarvis chat endpoint.

    Handles all user messages and returns Jarvis responses.
    Can execute actions directly or create drafts for review.

    Jarvis responds with:
    - Natural language response
    - Optional action draft (for complex actions)
    - Context awareness (what Jarvis knows)
    """

    user_id = str(user.id)
    message = body.message.strip()
    context = body.context or {}

    # Get or create session
    session = jps.get_or_create_session(
        db=db,
        user_id=user_id,
        company_id=company_id,
        variant_tier=_get_user_variant_tier(db, user),
    )

    # Track this message
    jps.track_activity(
        db=db,
        session_id=str(session.id),
        company_id=company_id,
        user_id=user_id,
        event_type="message",
        event_category="user",
        event_name="jarvis_chat_message",
        description=message[:200],
        metadata={"auto_execute": body.auto_execute},
    )

    # Get system context for AI
    system_context = jps.get_system_overview(db, company_id, user_id)

    # Get recent memories
    memories = jps.recall_memory(db, company_id, user_id, limit=5)
    memory_context = [
        {"key": m.memory_key, "value": m.memory_value, "category": m.category}
        for m in memories
    ]

    # Get today's tasks
    today_tasks = json.loads(session.today_tasks_json or "[]")

    # Build AI context
    ai_context = {
        "system_overview": system_context,
        "recent_memories": memory_context,
        "today_tasks": today_tasks[-20:],  # Last 20 tasks
        "user_context": context,
        "variant_tier": session.variant_tier,
        "features": json.loads(session.features_enabled_json or "{}"),
    }

    # Process message with AI
    try:
        ai_response, action_result = await _process_message_with_ai(
            db=db,
            session_id=str(session.id),
            company_id=company_id,
            user_id=user_id,
            message=message,
            context=ai_context,
            auto_execute=body.auto_execute,
            variant_tier=session.variant_tier,
        )
    except Exception as e:
        logger.error(f"jarvis_ai_error: {e}")
        ai_response = _get_fallback_response()
        action_result = None

    # Update session
    session.last_interaction_at = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    response = {
        "response": ai_response,
        "context": {
            "activities_today": system_context.get("activities_today", 0),
            "active_alerts": system_context.get("active_alerts", 0),
            "pending_drafts": system_context.get("pending_drafts", 0),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Include draft if created
    if action_result and action_result.get("draft"):
        response["draft"] = action_result["draft"]

    # Include alert if any critical
    if system_context.get("alerts_by_severity", {}).get("critical", 0) > 0:
        alerts = jps.get_active_alerts(
            db, company_id, user_id, min_severity="critical")
        if alerts:
            response["alert"] = {
                "id": str(alerts[0].id),
                "title": alerts[0].title,
                "message": alerts[0].message,
                "severity": alerts[0].severity,
            }

    return response


# ══════════════════════════════════════════════════════════════════
# Context & History Endpoints
# ══════════════════════════════════════════════════════════════════

@router.get("/api/jarvis/prod/context")
async def get_jarvis_context(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current Jarvis context and awareness.

    Returns what Jarvis knows about:
    - Today's activities
    - Active alerts
    - Pending drafts
    - System status
    - Recent errors
    """

    user_id = str(user.id)
    overview = jps.get_system_overview(db, company_id, user_id)

    # Get recent activities
    activities = jps.get_recent_activities(db, company_id, user_id, limit=10)

    return {
        **overview,
        "recent_activities": [
            {
                "event": a.event_name,
                "description": a.description,
                "time": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ],
    }


@router.get("/api/jarvis/prod/history")
async def get_jarvis_history(
        user_filter: Optional[str] = Query(
            None,
            description="Filter by user ID"),
    event_type: Optional[str] = Query(
            None,
            description="Filter by event type"),
        hours: int = Query(
            24,
            ge=1,
            le=168,
            description="Hours to look back"),
        limit: int = Query(
            50,
            ge=1,
            le=200),
        company_id: str = Depends(get_company_id),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Get activity history for awareness queries."""

    activities = jps.get_recent_activities(
        db=db,
        company_id=company_id,
        user_id=user_filter,
        event_types=[event_type] if event_type else None,
        hours=hours,
        limit=limit,
    )

    return {
        "total": len(activities),
        "activities": [
            {
                "id": str(a.id),
                "event_type": a.event_type,
                "event_name": a.event_name,
                "description": a.description,
                "category": a.event_category,
                "page": a.page_name,
                "time": a.created_at.isoformat() if a.created_at else None,
                "metadata": json.loads(a.metadata_json or "{}"),
            }
            for a in activities
        ],
    }


# ══════════════════════════════════════════════════════════════════
# Memory Endpoints
# ══════════════════════════════════════════════════════════════════

@router.get("/api/jarvis/prod/memory")
async def get_jarvis_memory(
    category: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get stored memories."""

    user_id = str(user.id)
    memories = jps.recall_memory(
        db=db,
        company_id=company_id,
        user_id=user_id,
        category=category,
        key=key,
        limit=limit,
    )

    return {
        "total": len(memories),
        "memories": [
            {
                "id": str(m.id),
                "category": m.category,
                "key": m.memory_key,
                "value": m.memory_value,
                "importance": m.importance,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "last_accessed": m.last_accessed_at.isoformat() if m.last_accessed_at else None,
                "access_count": m.access_count,
            }
            for m in memories
        ],
    }


@router.post("/api/jarvis/prod/memory")
async def store_jarvis_memory(
    body: MemoryStoreRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store a memory for later recall."""

    user_id = str(user.id)

    # Get session
    session = jps.get_or_create_session(
        db=db,
        user_id=user_id,
        company_id=company_id,
    )

    memory = jps.store_memory(
        db=db,
        session_id=str(session.id),
        company_id=company_id,
        user_id=user_id,
        category=body.category,
        key=body.key,
        value=body.value,
        importance=body.importance,
    )

    return {
        "success": True,
        "memory_id": str(memory.id),
        "category": memory.category,
        "key": memory.memory_key,
    }


# ══════════════════════════════════════════════════════════════════
# Action Endpoints
# ══════════════════════════════════════════════════════════════════

@router.post("/api/jarvis/prod/action")
async def execute_jarvis_action(
    body: ActionRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute or draft an action.

    If action is simple/reversible: execute directly
    If action is complex/bulk: create draft for review

    Returns:
    - Direct execution: result
    - Draft creation: draft details for approval
    """

    user_id = str(user.id)

    # Get session
    session = jps.get_or_create_session(
        db=db,
        user_id=user_id,
        company_id=company_id,
    )

    # Determine execution mode
    use_draft = body.force_draft or jps.should_use_draft(
        action_type=body.action_type,
        params=body.params,
    )

    if use_draft:
        # Create draft for review
        draft = jps.create_draft(
            db=db,
            session_id=str(session.id),
            company_id=company_id,
            user_id=user_id,
            draft_type=body.action_type,
            content=body.params,
            recipients=body.params.get("recipients"),
            subject=body.params.get("subject"),
        )

        return {
            "mode": "draft",
            "draft": {
                "id": str(
                    draft.id),
                "type": draft.draft_type,
                "subject": draft.subject,
                "recipient_count": draft.recipient_count,
                "content": json.loads(
                    draft.content_json),
                "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
            },
            "message": "Action requires review. Draft created for approval.",
        }

    else:
        # Execute directly
        success, result, error = jps.execute_direct_action(
            db=db,
            session_id=str(session.id),
            company_id=company_id,
            user_id=user_id,
            action_type=body.action_type,
            params=body.params,
        )

        if success:
            return {
                "mode": "direct",
                "success": True,
                "result": result,
            }
        else:
            return {
                "mode": "direct",
                "success": False,
                "error": error,
            }


@router.get("/api/jarvis/prod/drafts")
async def list_pending_drafts(
    status: str = Query("pending"),
    limit: int = Query(20, ge=1, le=100),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending drafts awaiting approval."""

    from database.models.jarvis_production import JarvisDraft

    drafts = db.query(JarvisDraft).filter(
        JarvisDraft.company_id == company_id,
        JarvisDraft.user_id == str(user.id),
        JarvisDraft.status == status,
    ).order_by(JarvisDraft.created_at.desc()).limit(limit).all()

    return {
        "total": len(drafts),
        "drafts": [
            {
                "id": str(d.id),
                "type": d.draft_type,
                "subject": d.subject,
                "recipient_count": d.recipient_count,
                "content": json.loads(d.content_json),
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "expires_at": d.expires_at.isoformat() if d.expires_at else None,
            }
            for d in drafts
        ],
    }


@router.post("/api/jarvis/prod/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve and execute a pending draft."""

    success, result, error = jps.approve_and_execute_draft(
        db=db,
        draft_id=draft_id,
        user_id=str(user.id),
    )

    if success:
        return {
            "success": True,
            "result": result,
        }
    else:
        return {
            "success": False,
            "error": error,
        }


@router.post("/api/jarvis/prod/drafts/{draft_id}/cancel")
async def cancel_draft(
    draft_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a pending draft."""

    success = jps.cancel_draft(
        db=db,
        draft_id=draft_id,
        user_id=str(user.id),
    )

    return {
        "success": success,
        "draft_id": draft_id,
    }


# ══════════════════════════════════════════════════════════════════
# Alert Endpoints
# ══════════════════════════════════════════════════════════════════

@router.get("/api/jarvis/prod/alerts")
async def list_active_alerts(
    min_severity: Optional[str] = Query(None),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active alerts for this user/company."""

    alerts = jps.get_active_alerts(
        db=db,
        company_id=company_id,
        user_id=str(user.id),
        min_severity=min_severity,
    )

    return {
        "total": len(alerts),
        "alerts": [
            {
                "id": str(
                    a.id),
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "suggested_action": json.loads(
                    a.suggested_action_json) if a.suggested_action_json else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            } for a in alerts],
    }


@router.post("/api/jarvis/prod/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert."""

    alert = jps.acknowledge_alert(
        db=db,
        alert_id=alert_id,
        user_id=str(user.id),
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "success": True,
        "alert_id": alert_id,
        "status": alert.status,
    }


@router.post("/api/jarvis/prod/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss an alert."""

    alert = jps.dismiss_alert(
        db=db,
        alert_id=alert_id,
        user_id=str(user.id),
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "success": True,
        "alert_id": alert_id,
        "status": alert.status,
    }


# ══════════════════════════════════════════════════════════════════
# Activity Tracking Endpoint
# ══════════════════════════════════════════════════════════════════

@router.post("/api/jarvis/prod/track")
async def track_user_activity(
    body: TrackActivityRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track user activity for Jarvis awareness.

    Called by frontend to track:
    - Page visits
    - Button clicks
    - Form submissions
    - Any user interaction
    """

    user_id = str(user.id)

    # Get session
    session = jps.get_or_create_session(
        db=db,
        user_id=user_id,
        company_id=company_id,
    )

    # Track the activity
    jps.track_activity(
        db=db,
        session_id=str(session.id),
        company_id=company_id,
        user_id=user_id,
        event_type=body.event_type,
        event_category="user",
        event_name=body.event_name,
        description=body.description,
        metadata=body.metadata,
        page_url=body.page_url,
        page_name=body.page_name,
    )

    return {
        "success": True,
        "tracked": body.event_name,
    }


# ══════════════════════════════════════════════════════════════════
# User Activity Summary
# ══════════════════════════════════════════════════════════════════

@router.get("/api/jarvis/prod/user/{target_user_id}/activity")
async def get_user_activity(
    target_user_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get activity summary for a specific user.

    Used when user asks: "What did John do today?"
    """

    # TODO: Add permission check

    summary = jps.get_user_activity_summary(
        db=db,
        company_id=company_id,
        user_id=target_user_id,
    )

    return summary


# ══════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════

def _get_user_variant_tier(db: Session, user: User) -> str:
    """Get user's variant tier from their subscription."""

    try:
        # Check company subscription
        if user.company:
            company = user.company
            # Map subscription tier to Jarvis tier
            tier_map = {
                "starter": "starter",
                "growth": "growth",
                "high": "high",
                "parwa": "growth",
                "parwa_high": "high",
            }
            subscription_tier = getattr(
                company, "subscription_tier", "starter")
            return tier_map.get(subscription_tier, "starter")
    except Exception:
        pass

    return "starter"


async def _process_message_with_ai(
    db: Session,
    session_id: str,
    company_id: str,
    user_id: str,
    message: str,
    context: Dict[str, Any],
    auto_execute: bool,
    variant_tier: str,
) -> tuple:
    """Process message with AI and return response + optional action."""

    import asyncio
    import concurrent.futures

    # Build system prompt
    system_prompt = _build_jarvis_system_prompt(context, variant_tier)

    # Call AI
    try:
        from app.core.ai_pipeline import process_ai_message

        try:
            result = asyncio.run(process_ai_message(
                query=message,
                company_id=company_id,
                conversation_id=session_id,
                variant_type=variant_tier,
                customer_id=user_id,
                system_prompt=system_prompt,
            ))
        except RuntimeError:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run,
                    process_ai_message(
                        query=message,
                        company_id=company_id,
                        conversation_id=session_id,
                        variant_type=variant_tier,
                        customer_id=user_id,
                        system_prompt=system_prompt,
                    )
                ).result(timeout=60)

        response = result.response

        # Check if AI wants to execute an action
        action_result = None
        if result.auto_action and auto_execute:
            # Parse action from AI response
            action_type = result.auto_action.get("type")
            action_params = result.auto_action.get("params", {})

            if action_type:
                # Execute or draft based on complexity
                use_draft = jps.should_use_draft(action_type, action_params)

                if use_draft:
                    draft = jps.create_draft(
                        db=db,
                        session_id=session_id,
                        company_id=company_id,
                        user_id=user_id,
                        draft_type=action_type,
                        content=action_params,
                    )
                    action_result = {
                        "draft": {
                            "id": str(draft.id),
                            "type": draft.draft_type,
                            "content": json.loads(draft.content_json),
                        }
                    }
                else:
                    success, result_data, error = jps.execute_direct_action(
                        db=db,
                        session_id=session_id,
                        company_id=company_id,
                        user_id=user_id,
                        action_type=action_type,
                        params=action_params,
                    )
                    action_result = {
                        "executed": success,
                        "result": result_data if success else None,
                        "error": error,
                    }

        return response, action_result

    except Exception as e:
        logger.error(f"AI processing error: {e}")
        return _get_fallback_response(), None


def _build_jarvis_system_prompt(
        context: Dict[str, Any], variant_tier: str) -> str:
    """Build system prompt for Jarvis AI."""

    features = jps.TIER_FEATURES.get(jps.VariantTier(variant_tier), {})

    prompt = """You are Jarvis, PARWA's AI assistant. You are:
- Friendly and professional (like Iron Man's Jarvis)
- Human-like in conversation, not robotic
- Aware of everything happening in the system
- Helpful but proactive about important issues

PERSONALITY:
- Use natural, conversational language
- Use contractions (I'm, you're, don't, can't)
- Be friendly but focused on business
- Adjust tone based on user's mood

CURRENT AWARENESS:
- Activities today: {context.get('system_overview', {}).get('activities_today', 0)}
- Active alerts: {context.get('system_overview', {}).get('active_alerts', 0)}
- Pending drafts: {context.get('system_overview', {}).get('pending_drafts', 0)}
- Recent errors: {context.get('system_overview', {}).get('recent_errors', 0)}

USER'S TODAY TASKS:
{json.dumps(context.get('today_tasks', [])[-10:], indent=2)}

USER MEMORIES (what you remember about them):
{json.dumps(context.get('recent_memories', []), indent=2)}

CAPABILITIES (your tier: {variant_tier}):
- Awareness level: {features.get('awareness_level', 'basic')}
- SMS/Email control: {'Yes' if features.get('sms_email_control') else 'No'}
- Team management: {'Yes' if features.get('team_management') else 'No'}
- Bulk actions: {'Yes' if features.get('bulk_actions') else 'No'}

When user asks to do something:
1. Simple actions (pause AI, send single SMS): Execute directly
2. Complex actions (bulk email, settings changes): Create draft for approval

Always be helpful and provide clear, concise responses. If something important
has happened (alerts, errors), mention it proactively but don't be annoying.
"""
    return prompt


def _get_fallback_response() -> str:
    """Get fallback response when AI fails."""
    return (
        "Hey! I'm here, but I'm having a bit of trouble processing that right now. "
        "Could you try again? If this keeps happening, there might be a brief "
        "connectivity issue I'm working through.")
