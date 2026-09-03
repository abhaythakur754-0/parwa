"""
Jarvis API — All Jarvis REST Endpoints

Every endpoint is wired to a real backend module from jarvis_pipeline.
Handlers are thin: validate input → call module → return result.

Route groups mirror the functional areas:
  /api/jarvis/*         — core chat, status, notifications, flags, audit
  /api/jarvis/command/* — control commands (pause/resume/redirect/mode)
  /api/quality/*        — quality coach, drift, feedback, reports
  /api/sla/*            — SLA status & credits
  /api/approvals/*      — approval queues
  /api/emergency/*      — emergency shutdown & global pause
  /api/pause_all_refunds — global refund pause (convenience)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Request

from app.api.models import (
    ChatRequest,
    MetricsQuery,
    NotificationsQuery,
    BatchActionRequest,
    SetFlagRequest,
    PauseRequest,
    ResumeRequest,
    RedirectRequest,
    ModeRequest,
    QualityScoresQuery,
    FeedbackRequest,
    SLAQuery,
    ApprovalBatchRequest,
    EmergencyShutdownRequest,
    PauseAllRefundsRequest,
    AuditQuery,
    OkResponse,
    ErrorResponse,
    TicketSubmitRequest,
)
from app.api.api_utils import _err
from app.api.deps import get_company_id, get_current_user, require_roles
from app.api.sse import emit_pipeline_event
from database.models.core import User

logger = logging.getLogger("jarvis.api.routes")

# ── Authentication (BC-011 / BC-001) ────────────────────────
# Every endpoint on this router requires a valid JWT access token
# (Authorization: Bearer — the Next.js /api/pipeline proxy injects it
# from the parwa_at httpOnly cookie, see
# src/app/api/pipeline/[...path]/route.ts).
#
# BC-001: the tenant for every operation is derived from the
# authenticated user's company_id. tenant_id values supplied via
# query string or request body are IGNORED — this router previously
# trusted client-supplied tenant_id, which allowed cross-tenant
# access and unauthenticated command execution.

router = APIRouter(dependencies=[Depends(get_current_user)])


# ═══════════════════════════════════════════════════════════════
# CHAT & COMMANDS
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/jarvis/chat",
    summary="Main chat endpoint — runs full SENSE → EVALUATE → NOTIFY pipeline",
    response_model=Dict[str, Any],
)
async def jarvis_chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Accept a natural-language question and run the full Jarvis pipeline."""
    from app.core.jarvis_pipeline.graph import run_jarvis_chat

    tenant_id = company_id

    # Emit SSE init event
    await emit_pipeline_event(tenant_id, "init", {
        "question": req.question,
        "user_email": current_user.email,
    })
    await emit_pipeline_event(tenant_id, "sense_start", {})

    try:
        result = await run_jarvis_chat(
            tenant_id=tenant_id,
            question=req.question,
            user_email=current_user.email,
            user_role=current_user.role,
        )
    except Exception as exc:
        await emit_pipeline_event(tenant_id, "error", {"error": str(exc)})
        raise _err(f"Pipeline error: {exc}", 500)

    # Emit pipeline completion events
    await emit_pipeline_event(tenant_id, "sense_complete",
                              {"signals": result.get("signals", {}).get("integration_health", {})})
    await emit_pipeline_event(tenant_id, "evaluate_start", {})
    await emit_pipeline_event(tenant_id, "evaluate_complete",
                              {"evaluations": len(result.get("evaluations", []))})
    await emit_pipeline_event(tenant_id, "notify_start", {})
    await emit_pipeline_event(tenant_id, "notify_complete",
                              {"notifications": len(result.get("notifications", []))})
    await emit_pipeline_event(tenant_id, "done", {"chat_response": result.get("chat_response", "")[:200]})

    return result


@router.get(
    "/jarvis/status",
    summary="System status — integration health, load, active flags",
    response_model=Dict[str, Any],
)
async def jarvis_status(
    company_id: str = Depends(get_company_id),
):
    """Return integration health, load status, active flags, and uptime info."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()
    health = await db.get_integration_health(tenant_id)
    load = await db.get_load_status(tenant_id)
    flags = await db.get_active_flags(tenant_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "tenant_id": tenant_id,
        "timestamp": now_iso,
        "integration_health": health,
        "load_status": load,
        "active_flags": flags,
        "active_flags_count": len(flags),
    }


@router.get(
    "/jarvis/metrics",
    summary="Performance metrics — volume, accuracy, confidence, efficiency",
    response_model=Dict[str, Any],
)
async def jarvis_metrics(
    days: int = 7,
    company_id: str = Depends(get_company_id),
):
    """Performance dashboard data for a tenant over N days."""
    from app.core.jarvis_pipeline.report_generator import get_performance_dashboard

    return await get_performance_dashboard(tenant_id=company_id, days=days)


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/jarvis/notifications",
    summary="Get notifications for a tenant",
    response_model=Dict[str, Any],
)
async def get_notifications(
    include_resolved: bool = False,
    company_id: str = Depends(get_company_id),
):
    """List notifications ordered by priority."""
    from app.core.jarvis_pipeline.notification_center import get_tenant_notifications

    notifs = await get_tenant_notifications(
        tenant_id=company_id,
        include_resolved=include_resolved,
    )
    return {
        "tenant_id": company_id,
        "notifications": notifs,
        "count": len(notifs),
    }


@router.post(
    "/jarvis/notifications/{key}/resolve",
    summary="Resolve a notification by key",
    response_model=Dict[str, Any],
)
async def resolve_notification(
    key: str,
    company_id: str = Depends(get_company_id),
):
    """Mark a notification as resolved (must belong to caller's tenant)."""
    from app.core.jarvis_pipeline.notification_center import (
        get_notification,
        resolve_notification as resolve_ntf,
    )

    # Tenant check (BC-001): only resolve notifications owned by the caller.
    notif = await get_notification(key)
    if not notif or notif.get("tenant_id") != company_id:
        raise _err(f"Notification '{key}' not found", 404)

    ok = await resolve_ntf(key)
    if not ok:
        raise _err(f"Notification '{key}' not found or already resolved", 404)
    return {"ok": True, "message": f"Notification '{key}' resolved", "key": key}


@router.post(
    "/jarvis/notifications/batch/approve",
    summary="Approve all pending batches for a tenant",
    response_model=Dict[str, Any],
)
async def approve_batch(
    req: BatchActionRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Approve (flush) pending notification batches."""
    from app.core.jarvis_pipeline.notification_center import flush_batches
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()

    flushed = await flush_batches(tenant_id)

    # Audit
    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="batch_approve",
        actor_email=current_user.email,
        target_type="batch",
        target_id=req.batch_key,
        payload={"batch_key": req.batch_key, "flushed_count": len(flushed)},
    )

    return {
        "ok": True,
        "action": "approve",
        "tenant_id": tenant_id,
        "batch_key": req.batch_key,
        "flushed_count": len(flushed),
        "batches": flushed,
    }


@router.post(
    "/jarvis/notifications/batch/reject",
    summary="Reject all pending batches for a tenant",
    response_model=Dict[str, Any],
)
async def reject_batch(
    req: BatchActionRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Reject (flush & discard) pending notification batches."""
    from app.core.jarvis_pipeline.notification_center import flush_batches
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()

    flushed = await flush_batches(tenant_id)

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="batch_reject",
        actor_email=current_user.email,
        target_type="batch",
        target_id=req.batch_key,
        payload={"batch_key": req.batch_key, "flushed_count": len(flushed)},
    )

    return {
        "ok": True,
        "action": "reject",
        "tenant_id": tenant_id,
        "batch_key": req.batch_key,
        "flushed_count": len(flushed),
        "batches": flushed,
    }


# ═══════════════════════════════════════════════════════════════
# FLAGS & CONTROL
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/jarvis/flags",
    summary="List active system flags",
    response_model=Dict[str, Any],
)
async def get_flags(
    flag_type: str | None = None,
    company_id: str = Depends(get_company_id),
):
    """List all active flags for a tenant."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()
    flags = await db.get_active_flags(tenant_id, flag_type=flag_type)
    return {
        "tenant_id": tenant_id,
        "flags": flags,
        "count": len(flags),
    }


@router.post(
    "/jarvis/flags",
    summary="Set a system flag",
    response_model=Dict[str, Any],
)
async def set_flag(
    req: SetFlagRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Create a new system flag."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type=req.flag_type,
        flag_value=req.flag_value,
        set_by=current_user.email,
        scope=req.scope,
        reason=req.reason,
        expires_at=req.expires_at,
    )

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="set_flag",
        actor_email=current_user.email,
        target_type="flag",
        target_id=flag.get("id", ""),
        payload={
            "flag_type": req.flag_type,
            "flag_value": req.flag_value,
            "scope": req.scope,
            "reason": req.reason,
        },
    )

    return {"ok": True, "flag": flag}


@router.post(
    "/jarvis/flags/{flag_id}/revoke",
    summary="Revoke a system flag",
    response_model=Dict[str, Any],
)
async def revoke_flag(
    flag_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Revoke an active flag by its ID (must belong to caller's tenant)."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()

    # Tenant check (BC-001): only revoke flags owned by the caller.
    flags = await db.get_active_flags(tenant_id)
    if not any(f.get("id") == flag_id for f in flags):
        raise _err(f"Flag '{flag_id}' not found", 404)

    ok = await db.revoke_flag(flag_id, revoked_by=current_user.email)
    if not ok:
        raise _err(f"Flag '{flag_id}' not found or already revoked", 404)

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="revoke_flag",
        actor_email=current_user.email,
        target_type="flag",
        target_id=flag_id,
        payload={},
    )

    return {"ok": True, "message": f"Flag '{flag_id}' revoked", "flag_id": flag_id}


# ═══════════════════════════════════════════════════════════════
# CONTROL COMMANDS
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/jarvis/command/pause",
    summary="Pause an action/channel",
    response_model=Dict[str, Any],
)
async def command_pause(
    req: PauseRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Pause processing for a target (refund, return, all, etc.)."""
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id
    raw_input = f"pause {req.target}"
    if req.duration:
        raw_input += f" for {req.duration}"

    result = await execute_command(
        intent="control_pause",
        target=req.target,
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input=raw_input,
    )
    return result.to_dict()


@router.post(
    "/jarvis/command/resume",
    summary="Resume a paused action/channel",
    response_model=Dict[str, Any],
)
async def command_resume(
    req: ResumeRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Resume processing for a target."""
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id
    raw_input = f"resume {req.target}"

    result = await execute_command(
        intent="control_resume",
        target=req.target,
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input=raw_input,
    )
    return result.to_dict()


@router.post(
    "/jarvis/command/redirect",
    summary="Redirect a channel to AI or human",
    response_model=Dict[str, Any],
)
async def command_redirect(
    req: RedirectRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Redirect a channel to AI or human handler."""
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id
    raw_input = f"redirect {req.target} to {req.handler}"

    result = await execute_command(
        intent="control_route",
        target=req.target,
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input=raw_input,
    )
    return result.to_dict()


@router.post(
    "/jarvis/command/mode",
    summary="Change system operating mode",
    response_model=Dict[str, Any],
)
async def command_mode(
    req: ModeRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Switch between shadow / supervised / graduated mode."""
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id
    raw_input = f"switch mode to {req.mode}"

    result = await execute_command(
        intent="control_mode",
        target=req.mode,
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input=raw_input,
    )
    return result.to_dict()


# ═══════════════════════════════════════════════════════════════
# QUALITY & REPORTS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/quality/scores",
    summary="Quality scores — accuracy, volume, breakdown",
    response_model=Dict[str, Any],
)
async def quality_scores(
    days: int = 7,
    company_id: str = Depends(get_company_id),
):
    """Retrieve quality statistics for a tenant."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    stats = await db.get_quality_stats(company_id, days=days)
    return {"tenant_id": company_id, "days": days, **stats}


@router.get(
    "/quality/alerts",
    summary="Quality alerts — drift, accuracy drops",
    response_model=Dict[str, Any],
)
async def quality_alerts(company_id: str = Depends(get_company_id)):
    """Get active quality alerts."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    alerts = await db.get_quality_alerts(company_id, include_resolved=False)
    return {"tenant_id": company_id, "alerts": alerts, "count": len(alerts)}


@router.post(
    "/quality/alerts/{alert_id}/resolve",
    summary="Resolve a quality alert",
    response_model=Dict[str, Any],
)
async def resolve_quality_alert(
    alert_id: str,
    company_id: str = Depends(get_company_id),
):
    """Mark a quality alert as resolved (must belong to caller's tenant)."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()

    # Tenant check (BC-001): only resolve alerts owned by the caller.
    alerts = await db.get_quality_alerts(company_id, include_resolved=True)
    if not any(a.get("id") == alert_id for a in alerts):
        raise _err(f"Quality alert '{alert_id}' not found", 404)

    ok = await db.resolve_quality_alert(alert_id)
    if not ok:
        raise _err(f"Quality alert '{alert_id}' not found or already resolved", 404)
    return {"ok": True, "message": f"Alert '{alert_id}' resolved", "alert_id": alert_id}


@router.get(
    "/quality/recommendations",
    summary="Training priority recommendations",
    response_model=Dict[str, Any],
)
async def quality_recommendations(company_id: str = Depends(get_company_id)):
    """Get ranked training priority list with actionable suggestions."""
    from app.core.jarvis_pipeline.quality_coach import generate_training_priority_list

    priorities = await generate_training_priority_list(company_id)
    return {
        "tenant_id": company_id,
        "recommendations": priorities,
        "count": len(priorities),
    }


@router.post(
    "/quality/feedback",
    summary="Submit training feedback",
    response_model=Dict[str, Any],
)
async def quality_feedback(
    req: FeedbackRequest,
    company_id: str = Depends(get_company_id),
):
    """Record approved/rejected training data for the AI."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()

    record = await db.record_training_data(
        tenant_id=tenant_id,
        ticket_id=req.ticket_id or "",
        signal_type=req.signal_type,
        original_response=req.ai_response,
        corrected_response=req.correct_response,
        quality_score=req.quality_score,
        ticket_type=req.ticket_type,
        metadata=req.metadata or {},
    )

    return {"ok": True, "tenant_id": tenant_id, "record": record}


@router.get(
    "/quality/weekly-report",
    summary="Weekly wins report",
    response_model=Dict[str, Any],
)
async def weekly_report(
    days: int = 7,
    company_id: str = Depends(get_company_id),
):
    """Generate the weekly wins report."""
    from app.core.jarvis_pipeline.report_generator import generate_weekly_wins_report

    report = await generate_weekly_wins_report(tenant_id=company_id, days=days)
    return report


@router.get(
    "/quality/health-score",
    summary="Agent health score + coaching recommendation",
    response_model=Dict[str, Any],
)
async def agent_health_score(company_id: str = Depends(get_company_id)):
    """Get comprehensive agent health summary with coaching."""
    from app.core.jarvis_pipeline.quality_coach import get_agent_health_summary

    return await get_agent_health_summary(company_id)


@router.get(
    "/quality/drift-check",
    summary="Run drift detection and create alerts",
    response_model=Dict[str, Any],
)
async def drift_check(company_id: str = Depends(get_company_id)):
    """Run drift check and auto-create alerts if drift detected."""
    from app.core.jarvis_pipeline.quality_coach import run_drift_check_and_alert

    return await run_drift_check_and_alert(company_id)


# ═══════════════════════════════════════════════════════════════
# SLA
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/sla/status",
    summary="SLA status — uptime, incidents, credits",
    response_model=Dict[str, Any],
)
async def sla_status(
    days: int = 30,
    company_id: str = Depends(get_company_id),
):
    """Compute SLA status for a tenant."""
    from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

    return await compute_sla_status(tenant_id=company_id, days=days)


@router.get(
    "/sla/credits",
    summary="SLA credits owed",
    response_model=Dict[str, Any],
)
async def sla_credits(
    days: int = 30,
    company_id: str = Depends(get_company_id),
):
    """Get SLA credits information (part of SLA status)."""
    from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

    status = await compute_sla_status(tenant_id=company_id, days=days)
    return {
        "tenant_id": company_id,
        "period_days": days,
        "credit_owed_usd": status.get("credit_owed_usd", 0),
        "sla_status": status.get("sla_status", "meeting"),
        "actual_uptime_pct": status.get("actual_uptime_pct", 100),
        "target_uptime_pct": status.get("target_uptime_pct", 99.5),
    }


# ═══════════════════════════════════════════════════════════════
# APPROVALS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/approvals/pending",
    summary="Pending approval batches",
    response_model=Dict[str, Any],
)
async def approvals_pending(company_id: str = Depends(get_company_id)):
    """Get pending approval batch queue."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()
    # Access the internal batch metas for reading (non-destructive).
    # InMemoryBackend stores them in _batch_metas, Supabase would need
    # a dedicated query — fall back to empty list if unavailable.
    if hasattr(db, "_batch_metas"):
        pending = list(db._batch_metas.get(tenant_id, {}).values())
    else:
        pending = []
    return {
        "tenant_id": tenant_id,
        "pending": pending,
        "count": len(pending),
    }


@router.post(
    "/approvals/batch",
    summary="Batch approve or reject pending items",
    response_model=Dict[str, Any],
)
async def approval_batch(
    req: ApprovalBatchRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Approve or reject a batch of pending items."""
    from app.core.jarvis_pipeline.notification_center import flush_batches
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    action = req.action.lower()

    if action not in ("approve", "reject"):
        raise _err("action must be 'approve' or 'reject'")

    db = get_db()
    flushed = await flush_batches(tenant_id)

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action=f"approval_{action}",
        actor_email=current_user.email,
        target_type="batch",
        target_id=req.batch_key or "all",
        payload={"action": action, "batch_key": req.batch_key, "flushed_count": len(flushed)},
    )

    return {
        "ok": True,
        "action": action,
        "tenant_id": tenant_id,
        "batch_key": req.batch_key,
        "processed_count": len(flushed),
        "batches": flushed,
    }


# ═══════════════════════════════════════════════════════════════
# EMERGENCY
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/emergency/shutdown",
    summary="Emergency stop — halt all AI processing",
    response_model=Dict[str, Any],
)
async def emergency_shutdown(
    req: EmergencyShutdownRequest,
    current_user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
):
    """Emergency shutdown — creates a global_shutdown flag.

    Owner/admin only. The tenant is derived from the authenticated
    user's company_id (BC-001) and the audit trail written by the
    command executor records the authenticated user's email as actor.
    """
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id

    result = await execute_command(
        intent="emergency_shutdown",
        target="all",
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input="emergency shutdown everything",
    )
    return result.to_dict()


@router.post(
    "/pause_all_refunds",
    summary="Global refund pause — pause all refund processing",
    response_model=Dict[str, Any],
)
async def pause_all_refunds(
    req: PauseAllRefundsRequest,
    current_user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
):
    """Pause all refund processing globally.

    Owner/admin only. The tenant is derived from the authenticated
    user's company_id (BC-001) and the audit trail written by the
    command executor records the authenticated user's email as actor.
    """
    from app.core.jarvis_pipeline.pipeline_command_executor import execute_command

    tenant_id = company_id

    result = await execute_command(
        intent="control_pause",
        target="refund",
        tenant_id=tenant_id,
        actor_email=current_user.email,
        raw_input="pause all refunds",
    )
    return result.to_dict()


# ═══════════════════════════════════════════════════════════════
# AUDIT
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/jarvis/audit",
    summary="Audit trail — who did what and when",
    response_model=Dict[str, Any],
)
async def audit_trail(
    limit: int = 50,
    action: str | None = None,
    company_id: str = Depends(get_company_id),
):
    """Get the audit trail for a tenant."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    tenant_id = company_id
    db = get_db()
    trail = await db.get_audit_trail(
        tenant_id=tenant_id,
        limit=limit,
        action=action,
    )
    return {
        "tenant_id": tenant_id,
        "audit_trail": trail,
        "count": len(trail),
    }


# ═══════════════════════════════════════════════════════════════
# HEALTH & ROI
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/jarvis/customer-health",
    summary="Customer health score — onboarding milestones & readiness",
    response_model=Dict[str, Any],
)
async def customer_health(company_id: str = Depends(get_company_id)):
    """Get comprehensive customer health score with milestone tracking."""
    from app.core.jarvis_pipeline.health_scorer import get_customer_health

    return await get_customer_health(company_id)


@router.get(
    "/jarvis/roi",
    summary="ROI calculator — cost savings analysis",
    response_model=Dict[str, Any],
)
async def roi_calculator(
    days: int = 30,
    company_id: str = Depends(get_company_id),
):
    """Calculate ROI comparing human cost vs AI cost."""
    from app.core.jarvis_pipeline.health_scorer import calculate_roi

    return await calculate_roi(tenant_id=company_id, days=days)


# ═══════════════════════════════════════════════════════════════
# TICKET SUBMISSION (PARWA PIPELINE)
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/tickets/submit",
    summary="Submit a ticket to the PARWA pipeline",
    response_model=Dict[str, Any],
)
async def submit_ticket(
    req: TicketSubmitRequest,
    company_id: str = Depends(get_company_id),
):
    """Run a customer ticket through the full PARWA pipeline.

    This endpoint processes the ticket INSIDE the server process,
    so quality scores, notifications, and audit entries are written
    to the same shared DB that all API endpoints read from.

    Flow: Ingest → Classify → Route → Knowledge → Reasoning/Simple
          → Act+Verify → Quality → Finalize → END
    """
    import uuid
    import time as _time

    from app.core.parwa_pipeline.graph_v2 import run_parwa_pipeline
    from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant

    tenant_id = company_id
    ticket_id = f"tkt_api_{uuid.uuid4().hex[:8]}"

    # Emit SSE events
    await emit_pipeline_event(tenant_id, "ticket_received", {
        "ticket_id": ticket_id,
        "channel": req.channel_type,
    })
    await emit_pipeline_event(tenant_id, "pipeline_start", {"ticket_id": ticket_id})

    # Set variant for this ticket
    set_test_variant(tenant_id, req.variant_tier, 2000)

    initial_state = {
        "ticket_id": ticket_id,
        "tenant_id": tenant_id,
        "query": req.query,
        "channel_type": req.channel_type,
        "customer_context": req.customer_context or {},
        "metadata": {
            "sender": req.sender or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "api_submission",
        },
        "loop_count": 0,
        "total_token_usage": 0,
        "technique_log": [],
        "errors": [],
    }

    try:
        start = _time.monotonic()
        # run_parwa_pipeline is sync — handles async internally
        result = run_parwa_pipeline(initial_state)
        elapsed = round(_time.monotonic() - start, 2)

        status = result.get("status", "unknown")
        quality = result.get("quality_score", None)
        route = result.get("route_decision", result.get("current_path", "unknown"))
        response = (
            result.get("final_response", "")
            or result.get("formatted_response", "")
            or result.get("simple_answer", "")
            or result.get("super_node_answer", "")
        )

        # Emit completion events
        await emit_pipeline_event(tenant_id, "pipeline_complete", {
            "ticket_id": ticket_id,
            "status": status,
            "quality": quality,
            "elapsed": elapsed,
        })

        # Write audit entry
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        await db.create_audit_entry(
            tenant_id=tenant_id,
            action="ticket_processed",
            actor_email="system",
            target_type="ticket",
            target_id=ticket_id,
            payload={
                "status": status,
                "quality_score": quality,
                "route": route,
                "elapsed": elapsed,
                "channel": req.channel_type,
            },
        )

        return {
            "ok": True,
            "ticket_id": ticket_id,
            "status": status,
            "quality_score": quality,
            "route": route,
            "loop_count": result.get("loop_count", 0),
            "escalated": bool(result.get("escalation_context")),
            "elapsed_seconds": elapsed,
            "response_preview": response[:500],
        }

    except Exception as exc:
        await emit_pipeline_event(tenant_id, "pipeline_error", {
            "ticket_id": ticket_id,
            "error": str(exc),
        })
        raise _err(f"Pipeline error: {exc}", 500)


# ═══════════════════════════════════════════════════════════════
# WAVE 8 ROUTES — Agent Provisioning, Skills, Co-Pilot, Proactive
# ═══════════════════════════════════════════════════════════════

@router.get("/wave8/agents")
async def list_agents(company_id: str = Depends(get_company_id)):
    """List all agent configs for a tenant."""
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()
    agents = await db.get_all_agent_configs(company_id)
    return {"ok": True, "agents": agents, "count": len(agents)}


@router.post("/wave8/provision")
async def provision_agent_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Provision new agents via chat command."""
    tenant_id = company_id
    raw_command = request.get("command", "")
    actor_email = current_user.email

    if not raw_command:
        raise _err("Missing 'command' field", 400)

    from app.core.jarvis_pipeline.agent_provisioner import (
        parse_provision_command, provision_agents,
    )
    parsed = parse_provision_command(raw_command)
    result = await provision_agents(
        tenant_id=tenant_id,
        actor_email=actor_email,
        parsed=parsed,
    )
    return result


@router.get("/wave8/skills")
async def list_skills(company_id: str = Depends(get_company_id)):
    """List all client skills for a tenant."""
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()
    skills = await db.get_client_skills(company_id)
    return {"ok": True, "skills": skills, "count": len(skills)}


@router.post("/wave8/teach")
async def teach_skill_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Teach a new skill via natural language."""
    tenant_id = company_id
    description = request.get("description", "")
    actor_email = current_user.email

    if len(description) < 20:
        raise _err("Description too short (min 20 chars)", 400)

    from app.core.jarvis_pipeline.skill_instructor import teach_skill
    result = await teach_skill(
        tenant_id=tenant_id,
        actor_email=actor_email,
        raw_input=description,
    )
    return result


@router.post("/wave8/copilot/draft")
async def copilot_draft_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Generate a co-pilot draft response."""
    tenant_id = company_id
    ticket_id = request.get("ticket_id", "manual")
    customer_query = request.get("customer_query", "")
    channel = request.get("channel", "chat")
    actor_email = current_user.email

    if not customer_query:
        raise _err("Missing customer_query", 400)

    from app.core.jarvis_pipeline.copilot_mode import draft_response
    result = await draft_response(
        tenant_id=tenant_id,
        actor_email=actor_email,
        ticket_id=ticket_id,
        customer_query=customer_query,
        channel=channel,
    )
    return result


@router.post("/wave8/copilot/edit")
async def copilot_edit_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Save manager's edited draft for AI learning."""
    tenant_id = company_id
    draft_id = request.get("draft_id", "")
    edited_text = request.get("edited_text", "")
    actor_email = current_user.email

    if not draft_id or not edited_text:
        raise _err("Missing draft_id or edited_text", 400)

    from app.core.jarvis_pipeline.copilot_mode import save_edited_draft
    result = await save_edited_draft(
        tenant_id=tenant_id,
        draft_id=draft_id,
        edited_text=edited_text,
        actor_email=actor_email,
    )
    return result


@router.post("/wave8/proactive")
async def proactive_outreach_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Create a proactive outreach message (requires approval)."""
    tenant_id = company_id
    outreach_type = request.get("type", "general")
    customer_id = request.get("customer_id", "")
    reason = request.get("reason", "")
    draft_content = request.get("draft_content", "")
    actor_email = current_user.email

    from app.core.jarvis_pipeline.copilot_mode import create_proactive_outreach
    result = await create_proactive_outreach(
        tenant_id=tenant_id,
        actor_email=actor_email,
        outreach_type=outreach_type,
        customer_id=customer_id,
        reason=reason,
        draft_content=draft_content,
    )
    return result


@router.post("/wave8/correction")
async def dspy_correction_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Apply a DSPy correction."""
    tenant_id = company_id
    target = request.get("target", "")
    code = request.get("code", "manual")
    description = request.get("description", "")
    actor_email = current_user.email

    from app.core.jarvis_pipeline.copilot_mode import apply_dspy_correction
    result = await apply_dspy_correction(
        tenant_id=tenant_id,
        actor_email=actor_email,
        target_behavior=target,
        correction_code=code,
        description=description,
    )
    return result


@router.get("/wave8/provisioning-logs")
async def list_provisioning_logs(company_id: str = Depends(get_company_id)):
    """List agent provisioning history."""
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()
    # Use audit trail to get provisioning history
    trail = await db.get_audit_trail(company_id, limit=50)
    provisioning = [e for e in trail if e.get("action") == "agent_provisioned"]
    return {"ok": True, "provisioning_logs": provisioning, "count": len(provisioning)}
