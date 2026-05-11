"""
PARWA Jarvis Customer Care API Router

FastAPI router for Jarvis in Customer Care mode (post-onboarding).
Completely separate from the onboarding jarvis.py router because
CC mode has fundamentally different endpoints and request shapes.

Architecture:
  Client -> CC API -> jarvis_cc_service -> variant_pipeline_bridge -> Variant Pipelines
  Client -> CC API -> jarvis_awareness_engine -> snapshots/alerts (Phase 2.2)

16 endpoints covering:
- Session management (create/resume, get, health)
- Message send with pipeline metadata
- Context get/update
- History (paginated)
- System prompt preview
- Awareness Engine tick/snapshot/alert/delta (Phase 2.2)

Auth: All endpoints use get_current_user.
Error format: Matches PARWA standard {"error": {"code": ..., "message": ..., "details": ...}}

BC-001: company_id extracted from authenticated user on every request.
BC-008: Graceful error handling -- never crash.
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
    # Awareness Engine schemas (Phase 2.2)
    JarvisAwarenessTickRequest,
    JarvisAwarenessTickResponse,
    JarvisAwarenessSnapshotResponse,
    JarvisAwarenessSnapshotListResponse,
    JarvisProactiveAlertResponse,
    JarvisProactiveAlertListResponse,
    JarvisAlertAcknowledgeRequest,
    JarvisAlertDismissRequest,
    JarvisAlertResolveRequest,
    JarvisAwarenessDeltaResponse,
)
from app.services import jarvis_cc_service
from app.services import jarvis_awareness_engine
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/jarvis/cc", tags=["Jarvis Customer Care"])


# ========================================================================
# SESSION ENDPOINTS
# ========================================================================


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


# ========================================================================
# MESSAGE ENDPOINTS
# ========================================================================


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


# ========================================================================
# CONTEXT ENDPOINTS
# ========================================================================


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


# ========================================================================
# HISTORY ENDPOINT
# ========================================================================


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


# ========================================================================
# SYSTEM PROMPT PREVIEW (DEBUG/ADMIN)
# ========================================================================


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


# ========================================================================
# AWARENESS ENGINE ENDPOINTS (Phase 2.2)
# ========================================================================


@router.post("/awareness/tick", response_model=JarvisAwarenessTickResponse)
def awareness_tick(
    body: JarvisAwarenessTickRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger an awareness tick for a customer care session.

    This is the main entry point to the Awareness Engine. A tick
    collects current state from 7 monitoring domains, creates a
    snapshot, runs rule checks, and generates alerts if thresholds
    are breached.

    Tick types:
      - periodic:  Automatic tick (every 30 seconds via Celery beat)
      - on_change: Triggered when a monitored field changes
      - manual:    User/admin triggers from dashboard
      - emergency: Written when emergency_state changes

    Returns the tick result with snapshot ID, any alerts created,
    and a summary of the current system state.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        result = jarvis_awareness_engine.run_awareness_tick(
            db=db,
            company_id=str(user.company_id),
            session_id=body.session_id,
            user_id=str(user.id),
            tick_type=body.tick_type,
        )
        return JarvisAwarenessTickResponse(**result)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to run awareness tick",
            500,
            details={"error": str(exc)},
        )


@router.get("/awareness/snapshot", response_model=JarvisAwarenessSnapshotResponse)
def get_awareness_snapshot(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the latest awareness snapshot for a session.

    Returns the most recent snapshot with all 7 monitoring domain
    fields. This is what the dashboard displays in real-time.
    If no snapshot exists yet, returns a 404 error.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        snapshot = jarvis_awareness_engine.get_latest_snapshot(
            db=db,
            session_id=session_id,
            company_id=str(user.company_id),
        )
        if snapshot is None:
            return _error_response(
                "NOT_FOUND",
                "No awareness snapshot found for this session",
                404,
            )
        return _snapshot_to_response(snapshot)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get awareness snapshot",
            500,
            details={"error": str(exc)},
        )


@router.get("/awareness/snapshots", response_model=JarvisAwarenessSnapshotListResponse)
def get_awareness_snapshots(
    session_id: str = Query(..., description="Customer care session ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated snapshot history for a session.

    Returns snapshots in reverse chronological order (newest first).
    Used by the dashboard for trend analysis and historical debugging.
    Each snapshot includes all 7 domain fields plus metadata.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        snapshots, total = jarvis_awareness_engine.get_snapshot_history(
            db=db,
            session_id=session_id,
            company_id=str(user.company_id),
            limit=limit,
            offset=offset,
        )
        # Safety: ensure limit and offset are ints (not FastAPI Query objects
        # when called directly from tests bypassing FastAPI DI)
        _limit = _coerce_int(limit, 50)
        _offset = _coerce_int(offset, 0)

        return JarvisAwarenessSnapshotListResponse(
            snapshots=[_snapshot_to_response(s) for s in snapshots],
            total=total,
            limit=_limit,
            offset=_offset,
            has_more=(_offset + _limit) < total,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get snapshot history",
            500,
            details={"error": str(exc)},
        )


@router.get("/awareness/alerts", response_model=JarvisProactiveAlertListResponse)
def get_awareness_alerts(
    session_id: str = Query(..., description="Customer care session ID"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical, emergency"),
    category: Optional[str] = Query(None, description="Filter by category: system_health, ticket_volume, etc."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active (non-resolved, non-expired) alerts for a session.

    Returns alerts sorted by severity (emergency first) and then
    by creation time (newest first). Supports filtering by severity
    and category for dashboard views.

    Alert lifecycle: active -> acknowledged -> dismissed/resolved/expired
    Only active and acknowledged alerts are returned by default.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        alerts, total = jarvis_awareness_engine.get_active_alerts(
            db=db,
            session_id=session_id,
            company_id=str(user.company_id),
            severity=severity,
            category=category,
            limit=limit,
            offset=offset,
        )
        _limit = _coerce_int(limit, 50)
        _offset = _coerce_int(offset, 0)

        return JarvisProactiveAlertListResponse(
            alerts=[_alert_to_response(a) for a in alerts],
            total=total,
            limit=_limit,
            offset=_offset,
            has_more=(_offset + _limit) < total,
        )
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to get alerts",
            500,
            details={"error": str(exc)},
        )


@router.post("/awareness/alerts/acknowledge", response_model=JarvisProactiveAlertResponse)
def acknowledge_alert(
    body: JarvisAlertAcknowledgeRequest,
    session_id: str = Query(..., description="Session ID for alert scoping"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an active alert.

    Transitions the alert from 'active' to 'acknowledged' status.
    The alert remains visible on the dashboard but is marked as
    seen by the acknowledging user. Only active alerts can be
    acknowledged -- already acknowledged, dismissed, or resolved
    alerts will return a NOT_FOUND error.

    This is the human-in-the-loop action: "I see this alert."
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        alert = jarvis_awareness_engine.acknowledge_alert(
            db=db,
            alert_id=body.alert_id,
            session_id=session_id,
            company_id=str(user.company_id),
            user_id=str(user.id),
        )
        return _alert_to_response(alert)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to acknowledge alert",
            500,
            details={"error": str(exc)},
        )


@router.post("/awareness/alerts/dismiss", response_model=JarvisProactiveAlertResponse)
def dismiss_alert(
    body: JarvisAlertDismissRequest,
    session_id: str = Query(..., description="Session ID for alert scoping"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss an active or acknowledged alert.

    Transitions the alert to 'dismissed' status. This means the
    user has reviewed the alert and decided no action is needed.
    Dismissed alerts are removed from the active dashboard view.

    Only active or acknowledged alerts can be dismissed.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        alert = jarvis_awareness_engine.dismiss_alert(
            db=db,
            alert_id=body.alert_id,
            session_id=session_id,
            company_id=str(user.company_id),
            user_id=str(user.id),
        )
        return _alert_to_response(alert)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to dismiss alert",
            500,
            details={"error": str(exc)},
        )


@router.post("/awareness/alerts/resolve", response_model=JarvisProactiveAlertResponse)
def resolve_alert(
    body: JarvisAlertResolveRequest,
    session_id: str = Query(..., description="Session ID for alert scoping"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve an active or acknowledged alert.

    Typically called when the underlying issue has been fixed
    (e.g., system health recovered, quality score improved,
    ticket volume returned to normal).

    Resolved alerts remain in the database for audit purposes
    but are no longer shown on the active dashboard view.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        alert = jarvis_awareness_engine.resolve_alert(
            db=db,
            alert_id=body.alert_id,
            session_id=session_id,
            company_id=str(user.company_id),
        )
        return _alert_to_response(alert)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to resolve alert",
            500,
            details={"error": str(exc)},
        )


@router.get("/awareness/delta", response_model=JarvisAwarenessDeltaResponse)
def get_awareness_delta(
    session_id: str = Query(..., description="Customer care session ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the delta between the two most recent awareness snapshots.

    Shows what changed between the previous and current tick,
    including threshold crossings, status changes, and recovered
    fields. If no snapshot exists yet, returns an empty delta
    with is_first_tick=True.

    Used by the dashboard to highlight changes and trigger
    on_change behaviors.
    """
    if not user.company_id:
        return _error_response(
            "VALIDATION_ERROR",
            "User has no associated company",
            422,
        )

    try:
        # Get the two most recent snapshots
        snapshots, _ = jarvis_awareness_engine.get_snapshot_history(
            db=db,
            session_id=session_id,
            company_id=str(user.company_id),
            limit=2,
            offset=0,
        )

        if not snapshots:
            return JarvisAwarenessDeltaResponse(
                changed_fields={},
                has_significant_changes=True,
                new_alerts=[],
                recovered=[],
                is_first_tick=True,
            )

        # snapshots are newest-first from get_snapshot_history
        current_state = _safe_parse_json(snapshots[0].raw_state_json)
        previous_state = None
        if len(snapshots) > 1:
            previous_state = _safe_parse_json(snapshots[1].raw_state_json)

        delta = jarvis_awareness_engine.compute_awareness_delta(
            current=current_state,
            previous=previous_state,
        )
        return JarvisAwarenessDeltaResponse(**delta)
    except ParwaBaseError:
        raise
    except Exception as exc:
        return _error_response(
            "INTERNAL_ERROR",
            "Failed to compute awareness delta",
            500,
            details={"error": str(exc)},
        )


# ========================================================================
# RESPONSE HELPERS
# ========================================================================


def _safe_parse_json(raw: str) -> dict:
    """Safely parse JSON string to dict."""
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _coerce_int(value, default: int = 0) -> int:
    """Coerce a value to int, falling back to default.

    Handles FastAPI Query objects that appear when endpoints are
    called directly (bypassing FastAPI DI in unit tests).
    """
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _snapshot_to_response(snapshot: object) -> JarvisAwarenessSnapshotResponse:
    """Convert JarvisAwarenessSnapshot ORM model to API response."""
    channel_health = _safe_parse_json(snapshot.channel_health_json)
    active_alerts_raw = _safe_parse_json(snapshot.active_alerts_json)
    quality_alerts_raw = _safe_parse_json(snapshot.quality_alerts_json)
    last_5_errors_raw = _safe_parse_json(snapshot.last_5_errors_json)

    # Validate that list items are dicts (not ints, strings, etc.)
    active_alerts = active_alerts_raw if isinstance(active_alerts_raw, list) and all(isinstance(x, dict) for x in active_alerts_raw) else []
    quality_alerts = quality_alerts_raw if isinstance(quality_alerts_raw, list) and all(isinstance(x, dict) for x in quality_alerts_raw) else []
    last_5_errors = last_5_errors_raw if isinstance(last_5_errors_raw, list) and all(isinstance(x, dict) for x in last_5_errors_raw) else []

    return JarvisAwarenessSnapshotResponse(
        id=str(snapshot.id),
        session_id=str(snapshot.session_id),
        company_id=str(snapshot.company_id),
        snapshot_type=snapshot.snapshot_type or "periodic",
        tick_number=snapshot.tick_number,
        current_plan=snapshot.current_plan,
        plan_usage_today=float(snapshot.plan_usage_today) if snapshot.plan_usage_today is not None else None,
        subscription_status=snapshot.subscription_status,
        days_until_renewal=snapshot.days_until_renewal,
        system_health=snapshot.system_health or "unknown",
        channel_health=channel_health if isinstance(channel_health, dict) else {},
        active_alerts_count=snapshot.active_alerts_count or 0,
        active_alerts=active_alerts if isinstance(active_alerts, list) else [],
        ticket_volume_today=snapshot.ticket_volume_today or 0,
        ticket_volume_avg=float(snapshot.ticket_volume_avg) if snapshot.ticket_volume_avg is not None else None,
        ticket_volume_spike=snapshot.ticket_volume_spike or False,
        active_agents=snapshot.active_agents or 0,
        agent_pool_capacity=snapshot.agent_pool_capacity or 0,
        agent_pool_utilization=float(snapshot.agent_pool_utilization) if snapshot.agent_pool_utilization is not None else None,
        training_running=snapshot.training_running or False,
        training_mistake_count=snapshot.training_mistake_count or 0,
        training_model_version=snapshot.training_model_version,
        drift_status=snapshot.drift_status or "none",
        drift_score=float(snapshot.drift_score) if snapshot.drift_score is not None else None,
        quality_score=float(snapshot.quality_score) if snapshot.quality_score is not None else None,
        quality_alerts=quality_alerts if isinstance(quality_alerts, list) else [],
        last_5_errors=last_5_errors if isinstance(last_5_errors, list) else [],
        created_at=(
            snapshot.created_at.isoformat() if snapshot.created_at else None
        ),
    )


def _alert_to_response(alert: object) -> JarvisProactiveAlertResponse:
    """Convert JarvisProactiveAlert ORM model to API response."""
    details = _safe_parse_json(alert.details_json)

    return JarvisProactiveAlertResponse(
        id=str(alert.id),
        session_id=str(alert.session_id),
        company_id=str(alert.company_id),
        alert_type=alert.alert_type,
        severity=alert.severity or "info",
        category=alert.category or "system_health",
        title=alert.title,
        message=alert.message,
        details=details if isinstance(details, dict) else {},
        status=alert.status or "active",
        action_required=alert.action_required or False,
        action_url=alert.action_url,
        ttl_seconds=alert.ttl_seconds or 0,
        related_snapshot_id=alert.related_snapshot_id,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=(
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
        ),
        resolved_at=(
            alert.resolved_at.isoformat() if alert.resolved_at else None
        ),
        created_at=(
            alert.created_at.isoformat() if alert.created_at else None
        ),
        updated_at=(
            alert.updated_at.isoformat() if alert.updated_at else None
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
