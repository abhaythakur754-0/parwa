"""
PARWA Phase 3 — Industry API Routes

Endpoints for previewing and applying industry changes, and retrieving
industry metadata.

CRITICAL RULES:
- Industry is a SUGGESTION filter, not a restriction
- Existing connections NEVER auto-disconnect
- Tickets, KB, billing, webhooks are ALWAYS preserved
- BC-001: All endpoints use company_id from JWT/header for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_db, get_audit_trail
from app.core.industry_change_handler import IndustryChangeHandler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/industry", tags=["industry"])

# ---------------------------------------------------------------------------
# Shared handler instance
# ---------------------------------------------------------------------------

_industry_handler = IndustryChangeHandler()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PreviewChangeRequest(BaseModel):
    """Preview what would happen if industry changes."""
    new_industry: str = Field(..., min_length=1, description="Target industry (ecommerce, saas, logistics, general)")


class ApplyChangeRequest(BaseModel):
    """Apply an industry change."""
    new_industry: str = Field(..., min_length=1, description="Target industry (ecommerce, saas, logistics, general)")
    disconnect_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of integration IDs to disconnect during the change",
    )


# ---------------------------------------------------------------------------
# POST /industry/preview-change
# ---------------------------------------------------------------------------

@router.post("/preview-change")
def preview_industry_change(
    body: PreviewChangeRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Preview what would happen if industry changes.

    Returns warning data WITHOUT making changes. Shows which integrations
    are in/out of the new industry's recommended tools.

    KEY PRINCIPLES:
    - Existing connections NEVER auto-disconnect
    - Tickets, KB, billing, webhooks are ALWAYS preserved

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        handler = IndustryChangeHandler(db_session=db)
        preview = handler.preview_industry_change(
            company_id=company_id,
            new_industry=body.new_industry,
        )
        return {
            "status": "success",
            "company_id": company_id,
            "preview": preview,
        }
    except Exception as exc:
        logger.error(
            "preview_industry_change failed for company_id=%s: %s",
            company_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "preview": {},
        }


# ---------------------------------------------------------------------------
# POST /industry/apply-change
# ---------------------------------------------------------------------------

@router.post("/apply-change")
def apply_industry_change(
    body: ApplyChangeRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Apply the industry change.

    Steps:
    1. Update company.industry
    2. Flag outside-industry integrations in settings JSON
    3. Update AI tool priority via CompanySetting
    4. Log to audit trail
    5. If disconnect_ids provided, disconnect those specific integrations

    KEY PRINCIPLES:
    - Industry is a SUGGESTION filter, not a restriction
    - Existing connections NEVER auto-disconnect (unless explicitly requested)
    - Tickets, KB, billing, webhooks are ALWAYS preserved

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        audit_service = get_audit_trail()
        handler = IndustryChangeHandler(
            db_session=db,
            audit_service=audit_service,
        )
        result = handler.apply_industry_change(
            company_id=company_id,
            new_industry=body.new_industry,
            disconnect_ids=body.disconnect_ids,
        )
        return {
            "status": "success" if result.get("success", False) else "error",
            "company_id": company_id,
            "result": result,
        }
    except Exception as exc:
        logger.error(
            "apply_industry_change failed for company_id=%s: %s",
            company_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "result": {},
        }


# ---------------------------------------------------------------------------
# GET /industry/metadata
# ---------------------------------------------------------------------------

@router.get("/metadata")
def get_industry_metadata(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get all industry metadata including labels, tools, AI settings.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        metadata = IndustryChangeHandler.INDUSTRY_METADATA
        industries = []

        for industry_key, meta in metadata.items():
            industries.append({
                "id": industry_key,
                "label": meta.get("label", industry_key),
                "primary_tools": meta.get("primary_tools", []),
                "ai_tone": meta.get("ai_tone", ""),
                "ai_priority": meta.get("ai_priority", ""),
            })

        return {
            "status": "success",
            "company_id": company_id,
            "total": len(industries),
            "industries": industries,
        }
    except Exception as exc:
        logger.error("get_industry_metadata failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "industries": [],
        }
