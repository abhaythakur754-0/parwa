"""
Escalation API Endpoints

Provides REST endpoints for:
  - Viewing escalations (list, get by ID, get by notification key)
  - Providing human guidance for escalated tickets
  - Triggering resume pipeline (re-process with human guidance)
  - Auto-resume all pending escalations
  - Vault statistics

All endpoints are production-ready with proper error handling.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("parwa.escalation_api")

router = APIRouter(prefix="/api/escalation", tags=["Escalation"])


# ── Request/Response Models ───────────────────────────────────

class GuidanceRequest(BaseModel):
    """Human guidance for an escalated ticket."""
    guidance: str = Field(..., min_length=5, description="Human agent's guidance/instructions")
    source: str = Field(default="jarvis_chat", description="Source: jarvis_chat, api, notification")


class GuidanceByNotificationRequest(BaseModel):
    """Guidance submitted by PARWA-NFY notification key."""
    notification_key: str = Field(..., description="PARWA-NFY-XXX notification key")
    guidance: str = Field(..., min_length=5, description="Human agent's guidance")
    source: str = Field(default="notification_click", description="Source of guidance")


class ResumeRequest(BaseModel):
    """Request to resume a specific escalation."""
    escalation_id: str = Field(..., description="Escalation ID to resume")


class AutoResumeRequest(BaseModel):
    """Request to auto-resume all eligible escalations."""
    tenant_id: str = Field(..., description="Tenant ID")


# ── Endpoints ────────────────────────────────────────────────


@router.get("/list")
async def list_escalations(
    tenant_id: str,
    human_status: Optional[str] = None,
    reprocess_status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List escalations for a tenant.

    Filters:
      - human_status: "pending", "guidance_provided", "resolved"
      - reprocess_status: "pending", "processing", "done", "failed"
    """
    from app.core.escalation_vault.vault_manager import VaultManager

    escalations = await VaultManager.list_escalations(
        tenant_id=tenant_id,
        human_status=human_status,
        reprocess_status=reprocess_status,
        limit=limit,
    )

    return {
        "success": True,
        "tenant_id": tenant_id,
        "count": len(escalations),
        "escalations": escalations,
    }


@router.get("/stats")
async def vault_stats(tenant_id: str) -> Dict[str, Any]:
    """Get escalation vault statistics."""
    from app.core.escalation_vault.vault_manager import VaultManager

    stats = await VaultManager.get_vault_stats(tenant_id)
    return {"success": True, **stats}


@router.get("/pending")
async def pending_resumes(tenant_id: str) -> Dict[str, Any]:
    """Get escalations awaiting resume (have guidance, not yet processed)."""
    from app.core.escalation_vault.vault_manager import VaultManager

    pending = await VaultManager.get_pending_resumes(tenant_id)
    return {
        "success": True,
        "tenant_id": tenant_id,
        "count": len(pending),
        "escalations": pending,
    }


@router.get("/{escalation_id}")
async def get_escalation(escalation_id: str) -> Dict[str, Any]:
    """Get a specific escalation by ID (full detail with pipeline state)."""
    from app.core.escalation_vault.vault_manager import VaultManager

    escalation = await VaultManager.get_escalation(escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")

    return {"success": True, "escalation": escalation}


@router.get("/by-ticket/{ticket_id}")
async def get_escalation_by_ticket(ticket_id: str) -> Dict[str, Any]:
    """Get escalation by original PARWA ticket ID."""
    from app.core.escalation_vault.vault_manager import VaultManager

    escalation = await VaultManager.get_escalation_by_ticket(ticket_id)
    if not escalation:
        raise HTTPException(status_code=404, detail=f"No escalation for ticket {ticket_id}")

    return {"success": True, "escalation": escalation}


@router.get("/by-notification/{notification_key}")
async def get_escalation_by_notification(notification_key: str) -> Dict[str, Any]:
    """Get escalation by PARWA-NFY notification key."""
    from app.core.escalation_vault.vault_manager import VaultManager

    escalation = await VaultManager.get_escalation_by_notification(notification_key)
    if not escalation:
        raise HTTPException(
            status_code=404,
            detail=f"No escalation for notification {notification_key}",
        )

    return {"success": True, "escalation": escalation}


@router.post("/{escalation_id}/guidance")
async def provide_guidance(escalation_id: str, req: GuidanceRequest) -> Dict[str, Any]:
    """Provide human guidance for an escalated ticket.

    This is called by JARVIS when a human agent types guidance.
    After guidance is saved, the escalation becomes eligible for resume.
    """
    from app.core.escalation_vault.vault_manager import VaultManager

    # Verify escalation exists
    existing = await VaultManager.get_escalation(escalation_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")

    if existing.get("human_status") == "resolved":
        raise HTTPException(
            status_code=400,
            detail=f"Escalation {escalation_id} already resolved",
        )

    # Save guidance
    record = await VaultManager.provide_human_guidance(
        escalation_id=escalation_id,
        guidance=req.guidance,
        source=req.source,
    )

    if not record:
        raise HTTPException(
            status_code=500,
            detail="Failed to save guidance",
        )

    logger.info(
        "API: Guidance provided for escalation=%s source=%s len=%d",
        escalation_id[:8], req.source, len(req.guidance),
    )

    return {
        "success": True,
        "escalation_id": escalation_id,
        "human_status": record.get("human_status"),
        "message": "Guidance saved. Ticket is now eligible for resume processing.",
    }


@router.post("/guidance-by-notification")
async def provide_guidance_by_notification(req: GuidanceByNotificationRequest) -> Dict[str, Any]:
    """Provide human guidance using PARWA-NFY notification key.

    Convenience endpoint — finds escalation by notification key,
    then adds guidance. Used when human clicks notification in JARVIS.
    """
    from app.core.escalation_vault.vault_manager import VaultManager

    record = await VaultManager.provide_guidance_by_notification(
        notification_key=req.notification_key,
        guidance=req.guidance,
        source=req.source,
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No escalation found for notification {req.notification_key}",
        )

    return {
        "success": True,
        "escalation_id": record.get("escalation_id"),
        "notification_key": req.notification_key,
        "human_status": record.get("human_status"),
        "message": "Guidance saved via notification key. Ticket eligible for resume.",
    }


@router.post("/resume")
async def resume_escalation(req: ResumeRequest) -> Dict[str, Any]:
    """Resume an escalated ticket with human guidance.

    Runs the resume pipeline:
      1. Load vault state + human guidance
      2. Re-reason with enriched context
      3. Quality check
      4. Save result + push to CRM

    Returns the improved response if quality passes.
    """
    from app.core.escalation_vault.resume_pipeline import resume_escalated_ticket

    result = await resume_escalated_ticket(req.escalation_id)

    if not result.get("success"):
        logger.warning(
            "API: Resume failed for escalation=%s quality=%.4f",
            req.escalation_id[:8],
            result.get("reprocess_quality", 0),
        )

    return result


@router.post("/auto-resume")
async def auto_resume_all(req: AutoResumeRequest) -> Dict[str, Any]:
    """Auto-resume all escalations that have human guidance but haven't been processed.

    Typically called by a scheduled job (cron) every few minutes.
    """
    from app.core.escalation_vault.resume_pipeline import auto_resume_pending

    result = await auto_resume_pending(req.tenant_id)
    return result


@router.post("/{escalation_id}/crm-status")
async def update_crm_status(
    escalation_id: str,
    crm_status: str,
    crm_ticket_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Manually update CRM push-back status for an escalation.

    Used when CRM push is done externally or for testing.
    """
    from app.core.escalation_vault.vault_manager import VaultManager

    record = await VaultManager.update_crm_push_back(
        escalation_id=escalation_id,
        status=crm_status,
        crm_ticket_id=crm_ticket_id or "",
    )

    if not record:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")

    return {
        "success": True,
        "escalation_id": escalation_id,
        "crm_status": crm_status,
    }


class GuidanceTicketRequest(BaseModel):
    """Request to create a guidance-as-new-ticket."""
    escalation_id: str = Field(..., description="Escalation ID to process")


class BatchGuidanceTicketRequest(BaseModel):
    """Request to batch-process failed escalations as guidance tickets."""
    tenant_id: str = Field(..., description="Tenant ID")


@router.post("/guidance-ticket")
async def create_guidance_ticket_endpoint(req: GuidanceTicketRequest) -> Dict[str, Any]:
    """Create a new ticket from human guidance when resume has failed.

    Alternative to resume pipeline: uses human guidance as the PRIMARY answer
    and validates it with LLM, rather than re-running the full reasoning pipeline.
    """
    from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

    result = await create_guidance_ticket(req.escalation_id)

    if not result.get("success"):
        logger.warning(
            "API: Guidance ticket failed for escalation=%s quality=%.4f",
            req.escalation_id[:8],
            result.get("quality_score", 0),
        )

    return result


@router.post("/batch-guidance-tickets")
async def batch_guidance_tickets_endpoint(req: BatchGuidanceTicketRequest) -> Dict[str, Any]:
    """Batch-process all failed escalations as guidance tickets.

    For escalations where the resume pipeline failed but human guidance exists,
    this tries the lighter 'guidance-as-ticket' approach.
    """
    from app.core.escalation_vault.guidance_ticket_flow import batch_guidance_tickets

    result = await batch_guidance_tickets(req.tenant_id)
    return result
