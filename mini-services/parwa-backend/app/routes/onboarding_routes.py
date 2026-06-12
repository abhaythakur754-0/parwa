"""Onboarding routes for PARWA backend."""
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Tenant, OnboardingState, AIVariant
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


# --- Pydantic Models ---

class IndustryVariantRequest(BaseModel):
    industry: str
    variant: str  # mini, parwa, parwa_high


class LegalConsentRequest(BaseModel):
    accepted: bool


class CompleteStepRequest(BaseModel):
    step: int


class ActivateRequest(BaseModel):
    pass


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


# --- Helper ---

def _get_or_create_onboarding_state(db: Session, tenant_id: str) -> OnboardingState:
    state = db.query(OnboardingState).filter(OnboardingState.tenant_id == tenant_id).first()
    if not state:
        state = OnboardingState(tenant_id=tenant_id)
        db.add(state)
        db.flush()
    return state


# --- Routes ---

@router.get("/state")
def get_onboarding_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current onboarding state for tenant."""
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)
    return {
        "id": state.id,
        "current_step": state.current_step,
        "industry": state.industry,
        "variant": state.variant,
        "legal_accepted": state.legal_accepted,
        "integrations": json.loads(state.integrations) if state.integrations else [],
        "kb_uploaded": state.kb_uploaded,
        "ai_configured": state.ai_configured,
        "payment_done": state.payment_done,
    }


@router.post("/industry-variant")
def set_industry_variant(
    req: IndustryVariantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set industry and variant during onboarding."""
    if req.variant not in VARIANT_DEFAULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid variant. Must be one of: {list(VARIANT_DEFAULTS.keys())}",
        )

    # Update onboarding state
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)
    state.industry = req.industry
    state.variant = req.variant
    state.current_step = max(state.current_step, 1)

    # Update tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if tenant:
        tenant.industry = req.industry
        tenant.onboarding_step = state.current_step

    # Create AI variant record
    defaults = VARIANT_DEFAULTS[req.variant]
    existing_variant = (
        db.query(AIVariant)
        .filter(AIVariant.tenant_id == current_user.tenant_id, AIVariant.variant_type == req.variant)
        .first()
    )
    if not existing_variant:
        variant = AIVariant(
            tenant_id=current_user.tenant_id,
            variant_type=req.variant,
            status="active",
            ticket_limit=defaults["ticket_limit"],
            tickets_used=0,
            ai_pipeline_steps=defaults["ai_pipeline_steps"],
            concurrent_ai=defaults["concurrent_ai"],
        )
        db.add(variant)

    db.commit()

    return {
        "message": "Industry and variant set successfully",
        "industry": req.industry,
        "variant": req.variant,
        "step": state.current_step,
    }


@router.post("/legal-consent")
def accept_legal_conent(
    req: LegalConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept legal terms during onboarding."""
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)
    state.legal_accepted = req.accepted
    if req.accepted:
        state.current_step = max(state.current_step, 2)

    db.commit()

    return {
        "message": "Legal consent updated" if not req.accepted else "Legal consent accepted",
        "legal_accepted": state.legal_accepted,
        "step": state.current_step,
    }


@router.post("/complete-step")
def complete_step(
    req: CompleteStepRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a specific onboarding step."""
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)

    step_map = {
        1: "industry",
        2: "legal_accepted",
        3: "integrations",
        4: "kb_uploaded",
        5: "ai_configured",
        6: "payment_done",
    }

    if req.step not in step_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step. Must be one of: {list(step_map.keys())}",
        )

    # Update the step
    state.current_step = max(state.current_step, req.step + 1)

    # Set the corresponding boolean field
    step_field_map = {
        1: ("industry", True),   # industry already set via industry-variant endpoint
        2: ("legal_accepted", True),
        3: ("integrations", True),  # integrations set via integration routes
        4: ("kb_uploaded", True),
        5: ("ai_configured", True),
        6: ("payment_done", True),
    }
    if req.step in step_field_map:
        field_name, field_value = step_field_map[req.step]
        if hasattr(state, field_name):
            setattr(state, field_name, field_value)

    # Also update tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if tenant:
        tenant.onboarding_step = state.current_step

    db.commit()

    return {
        "message": f"Step {req.step} completed",
        "current_step": state.current_step,
    }


@router.get("/prerequisites")
def get_prerequisites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get prerequisites for current onboarding step."""
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)

    prerequisites = {
        0: {"description": "Choose your industry and AI variant", "required": ["industry", "variant"]},
        1: {"description": "Accept legal terms", "required": ["legal_accepted"]},
        2: {"description": "Connect at least one integration", "required": ["integrations"]},
        3: {"description": "Upload knowledge base documents", "required": ["kb_uploaded"]},
        4: {"description": "Configure AI settings", "required": ["ai_configured"]},
        5: {"description": "Complete payment", "required": ["payment_done"]},
    }

    step = state.current_step
    prereq = prerequisites.get(step, {"description": "Onboarding complete", "required": []})

    return {
        "current_step": step,
        "prerequisites": prereq,
        "completed": {
            "industry": state.industry is not None,
            "variant": state.variant is not None,
            "legal_accepted": state.legal_accepted,
            "integrations": bool(json.loads(state.integrations) if state.integrations else []),
            "kb_uploaded": state.kb_uploaded,
            "ai_configured": state.ai_configured,
            "payment_done": state.payment_done,
        },
    }


@router.post("/activate")
def activate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate after all onboarding steps are complete."""
    state = _get_or_create_onboarding_state(db, current_user.tenant_id)

    # Verify required steps (industry + variant + legal are mandatory)
    if not state.industry or not state.variant:
        raise HTTPException(status_code=400, detail="Industry and variant must be set")
    if not state.legal_accepted:
        raise HTTPException(status_code=400, detail="Legal terms must be accepted")

    # Auto-complete optional steps if not already done
    if not state.kb_uploaded:
        state.kb_uploaded = True
    if not state.ai_configured:
        state.ai_configured = True
    if not state.payment_done:
        state.payment_done = True

    # Mark onboarding as complete
    state.current_step = 7  # Past all steps

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if tenant:
        tenant.onboarding_complete = True
        tenant.onboarding_step = 7

    db.commit()

    return {
        "message": "Account activated successfully",
        "onboarding_complete": True,
    }


@router.get("/first-victory")
def get_first_victory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get first victory data after activation."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant or not tenant.onboarding_complete:
        raise HTTPException(
            status_code=400,
            detail="Onboarding must be completed first",
        )

    # Get variants for the tenant
    variants = db.query(AIVariant).filter(AIVariant.tenant_id == current_user.tenant_id).all()

    return {
        "message": "Congratulations! Your AI support system is live.",
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "industry": tenant.industry,
        },
        "variants": [
            {
                "id": v.id,
                "type": v.variant_type,
                "status": v.status,
                "ticket_limit": v.ticket_limit,
            }
            for v in variants
        ],
        "next_steps": [
            "Connect your support channels",
            "Upload more knowledge base documents",
            "Configure auto-response rules",
            "Invite team members",
        ],
    }
