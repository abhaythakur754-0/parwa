"""Industry change management routes (PHASE 16 — GAP 10).

Provides endpoints to:
  - Change industry with preservation guarantees
  - Preview impact of industry change
  - Get industry details and recommended integrations
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Tenant, IntegrationCredential, AuditLog, OnboardingState
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/industry", tags=["industry"])

# Industry metadata
INDUSTRY_META = {
    "saas": {
        "name": "SaaS",
        "description": "Software as a Service companies",
        "primary_categories": ["CRM", "Ticketing", "Analytics", "Dev Tools"],
        "typical_integrations": ["hubspot", "salesforce", "pipedrive", "zendesk", "freshdesk", "intercom", "mixpanel", "amplitude", "github", "jira", "linear", "slack", "notion"],
    },
    "ecommerce": {
        "name": "E-commerce",
        "description": "Online retail and commerce businesses",
        "primary_categories": ["E-commerce", "Marketing", "Payments", "Shipping"],
        "typical_integrations": ["hubspot", "shopify", "woocommerce", "bigcommerce", "zendesk", "gorgias", "google_analytics", "klaviyo", "mailchimp", "stripe", "paypal", "shipstation", "aftership", "slack"],
    },
    "logistics": {
        "name": "Logistics",
        "description": "Shipping, freight, and logistics companies",
        "primary_categories": ["CRM", "Shipping"],
        "typical_integrations": ["hubspot", "salesforce", "zendesk", "freshdesk", "stripe", "shipstation", "aftership", "easypost", "fedex", "ups", "dhl", "slack"],
    },
    "other": {
        "name": "Other",
        "description": "Other industries — shows ALL integrations",
        "primary_categories": ["All categories"],
        "typical_integrations": "all",
    },
}


class ChangeIndustryRequest(BaseModel):
    industry: str


# --- Routes ---

@router.post("/change")
def change_industry(
    req: ChangeIndustryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the tenant's industry.

    Preservation guarantees (GAP 10):
    - Connected integrations: STAY CONNECTED (never auto-disconnect)
    - Tickets: PRESERVED (all historical and active tickets remain)
    - Knowledge base: PRESERVED (uploaded docs remain)
    - Billing: NO CHANGE (same variant, same price)
    - Webhooks: PRESERVED (existing webhooks keep firing)

    Only the integration catalog suggestions change.
    """
    if req.industry not in INDUSTRY_META:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid industry '{req.industry}'. Valid: {list(INDUSTRY_META.keys())}",
        )

    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    old_industry = tenant.industry

    # Get currently connected integrations
    connected = db.query(IntegrationCredential).filter(
        IntegrationCredential.tenant_id == current_user.tenant_id,
    ).all()

    # Determine which integrations are "outside" the new industry
    new_meta = INDUSTRY_META[req.industry]
    new_typical = new_meta["typical_integrations"]

    outside_integrations = []
    recommended_integrations = []
    for cred in connected:
        if new_typical == "all" or cred.integration_id in new_typical:
            recommended_integrations.append({
                "integration_id": cred.integration_id,
                "name": cred.integration_name,
                "status": cred.status,
                "in_new_industry": True,
            })
        else:
            outside_integrations.append({
                "integration_id": cred.integration_id,
                "name": cred.integration_name,
                "status": cred.status,
                "in_new_industry": False,
            })

    # Update the tenant's industry
    tenant.industry = req.industry
    tenant.updated_at = datetime.utcnow()

    # Update onboarding state if it exists
    onboarding = db.query(OnboardingState).filter(
        OnboardingState.tenant_id == current_user.tenant_id,
    ).first()
    if onboarding:
        onboarding.industry = req.industry
        onboarding.updated_at = datetime.utcnow()

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="industry.changed",
        actor=current_user.email,
        resource_type="tenant",
        resource_id=current_user.tenant_id,
        details=json.dumps({
            "old_industry": old_industry,
            "new_industry": req.industry,
            "integrations_outside_industry": [i["integration_id"] for i in outside_integrations],
            "preservation_guarantees": {
                "connected_integrations": "preserved",
                "tickets": "preserved",
                "knowledge_base": "preserved",
                "billing": "no_change",
                "webhooks": "preserved",
            },
        }),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Industry changed from '{old_industry}' to '{req.industry}'",
        "old_industry": old_industry,
        "new_industry": req.industry,
        "preservation_guarantees": {
            "connected_integrations": "preserved — all integrations stay connected",
            "tickets": "preserved — all tickets remain unchanged",
            "knowledge_base": "preserved — all documents remain unchanged",
            "billing": "no_change — same variant, same price",
            "webhooks": "preserved — existing webhooks keep firing",
        },
        "outside_industry_integrations": outside_integrations,
        "recommended_integrations": recommended_integrations,
        "total_connected": len(connected),
        "total_outside_industry": len(outside_integrations),
    }


@router.post("/preview-change")
def preview_industry_change(
    req: ChangeIndustryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview the impact of changing industry WITHOUT making the change.

    Returns information about what would change and what would be preserved.
    """
    if req.industry not in INDUSTRY_META:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid industry '{req.industry}'. Valid: {list(INDUSTRY_META.keys())}",
        )

    # Get current tenant info
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    old_industry = tenant.industry if tenant else None

    # Get connected integrations
    connected = db.query(IntegrationCredential).filter(
        IntegrationCredential.tenant_id == current_user.tenant_id,
    ).all()

    new_meta = INDUSTRY_META[req.industry]
    new_typical = new_meta["typical_integrations"]

    outside = []
    recommended = []
    for cred in connected:
        if new_typical == "all" or cred.integration_id in new_typical:
            recommended.append({
                "integration_id": cred.integration_id,
                "name": cred.integration_name,
                "status": cred.status,
            })
        else:
            outside.append({
                "integration_id": cred.integration_id,
                "name": cred.integration_name,
                "status": cred.status,
                "message": f"Will still work, but no longer suggested for {new_meta['name']}",
            })

    return {
        "current_industry": old_industry,
        "proposed_industry": req.industry,
        "proposed_industry_name": new_meta["name"],
        "primary_categories": new_meta["primary_categories"],
        "changes": {
            "integration_catalog": f"Will show {new_meta['name']}-recommended integrations",
            "connected_integrations": "All preserved — no auto-disconnect",
            "tickets": "All preserved — no changes",
            "knowledge_base": "All preserved — no changes",
            "billing": "No change — same variant, same price",
            "webhooks": "All preserved — keep firing",
        },
        "integrations": {
            "recommended": recommended,
            "outside_industry": outside,
            "total_connected": len(connected),
            "total_outside": len(outside),
        },
        "warning": None if len(outside) == 0 else f"{len(outside)} connected integration(s) are not typical for {new_meta['name']}. They will still work but won't be suggested by default.",
    }


@router.get("/current")
def get_current_industry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current industry and its details."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    industry_key = tenant.industry or "other"
    meta = INDUSTRY_META.get(industry_key, INDUSTRY_META["other"])

    return {
        "industry": industry_key,
        "industry_name": meta["name"],
        "description": meta["description"],
        "primary_categories": meta["primary_categories"],
    }


@router.get("/list")
def list_industries():
    """List all available industries with metadata."""
    return {
        "industries": [
            {
                "id": key,
                "name": meta["name"],
                "description": meta["description"],
                "primary_categories": meta["primary_categories"],
                "typical_integration_count": len(meta["typical_integrations"]) if isinstance(meta["typical_integrations"], list) else 30,
            }
            for key, meta in INDUSTRY_META.items()
        ],
        "total": len(INDUSTRY_META),
    }
