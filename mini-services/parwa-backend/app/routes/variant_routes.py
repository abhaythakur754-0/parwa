"""Variant management routes for PARWA backend (PHASE 14 - GAP 9)."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AIVariant, AuditLog
from app.auth import get_current_user
from app.services.variant_router import route_ticket

router = APIRouter(prefix="/api/v1/variants", tags=["variants"])


# --- Pydantic Models ---

class AddVariantRequest(BaseModel):
    variant_type: str  # mini, parwa, parwa_high


class RemoveVariantRequest(BaseModel):
    variant_id: str


class RouteTicketRequest(BaseModel):
    intent: str
    complexity_score: int = 5  # 1-10


# --- Variant defaults ---

VARIANT_DEFAULTS = {
    "mini": {
        "ticket_limit": 100,
        "ai_pipeline_steps": json.dumps(["intent_classification", "faq_match"]),
        "concurrent_ai": 1,
    },
    "parwa": {
        "ticket_limit": 500,
        "ai_pipeline_steps": json.dumps(["intent_classification", "faq_match", "kb_search", "rag_response"]),
        "concurrent_ai": 2,
    },
    "parwa_high": {
        "ticket_limit": 2000,
        "ai_pipeline_steps": json.dumps(["intent_classification", "faq_match", "kb_search", "rag_response", "external_tool_call", "sentiment_analysis"]),
        "concurrent_ai": 4,
    },
}


# --- Routes ---

@router.get("/list")
def list_variants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active variants for tenant."""
    variants = (
        db.query(AIVariant)
        .filter(AIVariant.tenant_id == current_user.tenant_id)
        .all()
    )

    return {
        "variants": [
            {
                "id": v.id,
                "variant_type": v.variant_type,
                "status": v.status,
                "ticket_limit": v.ticket_limit,
                "tickets_used": v.tickets_used,
                "ai_pipeline_steps": json.loads(v.ai_pipeline_steps) if v.ai_pipeline_steps else [],
                "concurrent_ai": v.concurrent_ai,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in variants
        ],
        "total": len(variants),
    }


@router.post("/add")
def add_variant(
    req: AddVariantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a new variant for the tenant."""
    if req.variant_type not in VARIANT_DEFAULTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variant type. Must be one of: {list(VARIANT_DEFAULTS.keys())}",
        )

    # Check if variant already exists and is active
    existing = (
        db.query(AIVariant)
        .filter(
            AIVariant.tenant_id == current_user.tenant_id,
            AIVariant.variant_type == req.variant_type,
            AIVariant.status != "scheduled_removal",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Variant '{req.variant_type}' already exists for this tenant",
        )

    # If there's a scheduled_removal one, reactivate it
    scheduled = (
        db.query(AIVariant)
        .filter(
            AIVariant.tenant_id == current_user.tenant_id,
            AIVariant.variant_type == req.variant_type,
            AIVariant.status == "scheduled_removal",
        )
        .first()
    )

    if scheduled:
        scheduled.status = "active"
        db.commit()
        db.refresh(scheduled)

        # Audit log
        audit = AuditLog(
            tenant_id=current_user.tenant_id,
            action="variant.reactivated",
            actor=current_user.email,
            resource_type="variant",
            resource_id=scheduled.id,
            details=json.dumps({"variant_type": req.variant_type}),
            severity="info",
        )
        db.add(audit)
        db.commit()

        return {
            "message": f"Variant '{req.variant_type}' reactivated",
            "variant": {
                "id": scheduled.id,
                "variant_type": scheduled.variant_type,
                "status": scheduled.status,
                "ticket_limit": scheduled.ticket_limit,
            },
        }

    defaults = VARIANT_DEFAULTS[req.variant_type]
    variant = AIVariant(
        tenant_id=current_user.tenant_id,
        variant_type=req.variant_type,
        status="active",
        ticket_limit=defaults["ticket_limit"],
        tickets_used=0,
        ai_pipeline_steps=defaults["ai_pipeline_steps"],
        concurrent_ai=defaults["concurrent_ai"],
    )
    db.add(variant)

    # Audit log
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="variant.added",
        actor=current_user.email,
        resource_type="variant",
        resource_id=variant.id,
        details=json.dumps({"variant_type": req.variant_type}),
        severity="info",
    )
    db.add(audit)
    db.commit()
    db.refresh(variant)

    return {
        "message": f"Variant '{req.variant_type}' added successfully",
        "variant": {
            "id": variant.id,
            "variant_type": variant.variant_type,
            "status": variant.status,
            "ticket_limit": variant.ticket_limit,
        },
    }


@router.delete("/remove")
def remove_variant(
    req: RemoveVariantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a variant - schedule for next-cycle removal."""
    variant = (
        db.query(AIVariant)
        .filter(
            AIVariant.id == req.variant_id,
            AIVariant.tenant_id == current_user.tenant_id,
        )
        .first()
    )

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    # Schedule removal instead of instant deletion
    variant.status = "scheduled_removal"

    # Audit log
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="variant.scheduled_removal",
        actor=current_user.email,
        resource_type="variant",
        resource_id=variant.id,
        details=json.dumps({
            "variant_type": variant.variant_type,
            "tickets_used": variant.tickets_used,
        }),
        severity="warning",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Variant '{variant.variant_type}' scheduled for removal at next cycle",
        "variant_id": variant.id,
        "status": "scheduled_removal",
    }


@router.get("/usage")
def get_variant_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get ticket usage per variant."""
    variants = (
        db.query(AIVariant)
        .filter(AIVariant.tenant_id == current_user.tenant_id)
        .all()
    )

    usage = []
    for v in variants:
        pct = (v.tickets_used / v.ticket_limit * 100) if v.ticket_limit > 0 else 0
        usage.append({
            "id": v.id,
            "variant_type": v.variant_type,
            "status": v.status,
            "tickets_used": v.tickets_used,
            "ticket_limit": v.ticket_limit,
            "usage_percentage": round(pct, 1),
            "remaining": max(0, v.ticket_limit - v.tickets_used),
        })

    return {"usage": usage}


@router.post("/route-ticket")
def route_ticket_endpoint(
    req: RouteTicketRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Route a ticket to the appropriate variant based on complexity."""
    if req.complexity_score < 1 or req.complexity_score > 10:
        raise HTTPException(
            status_code=400,
            detail="Complexity score must be between 1 and 10",
        )

    variant = route_ticket(
        tenant_id=current_user.tenant_id,
        intent=req.intent,
        complexity_score=req.complexity_score,
        db=db,
    )

    return {
        "routed_to": {
            "id": variant.id,
            "variant_type": variant.variant_type,
            "status": variant.status,
            "tickets_used": variant.tickets_used,
            "ticket_limit": variant.ticket_limit,
        },
        "intent": req.intent,
        "complexity_score": req.complexity_score,
    }
