"""PARWA Superglue Actions Router — manage tool action safety classifications.

Separate from the MCP server endpoints (those are for external AI tool invocation).
These are internal API endpoints for viewing / classifying / overriding action safety.

Endpoints:
- GET    /api/superglue/actions             — List safety classifications (BC-001: scoped to company)
- POST   /api/superglue/actions/classify    — Classify a tool name (ephemeral, no persist)
- POST   /api/superglue/actions/persist     — Classify AND persist to DB
- GET    /api/superglue/actions/{tool_id}   — Get one classification
- PATCH  /api/superglue/actions/{tool_id}/override — Toggle approval_required_override

BC-001: All queries scoped to authenticated user's company_id.
BC-008: Every endpoint wrapped in try/except.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.action_safety import classify_action, needs_approval
from app.core.regulatory_guardrails import get_applicable_frameworks
from app.schemas.superglue_actions import (
    ActionSafetyResponse,
    ClassifyActionRequest,
    ClassifyActionResponse,
    OverrideRequest,
    PersistClassificationRequest,
    PersistClassificationResponse,
)
from app.services.superglue_action_service import (
    classify_and_persist,
    get_classification,
    list_classifications,
    toggle_override,
)


router = APIRouter(prefix="/api/superglue/actions", tags=["superglue-actions"])


def _row_to_response(r) -> ActionSafetyResponse:
    return ActionSafetyResponse(
        id=r.get("id", ""), tool_id=r.get("tool_id", ""),
        tool_name=r.get("tool_name", ""), safety_level=r.get("safety_level", "read"),
        needs_approval=r.get("needs_approval", False),
        regulatory_frameworks=r.get("regulatory_frameworks", []),
        is_active=r.get("is_active", True),
    )


@router.get("/", response_model=list[ActionSafetyResponse])
def list_actions(
    safety_level: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(lambda: None),
    user=Depends(lambda: None),
):
    """List safety classifications for the authenticated user's company. BC-001."""
    try:
        rows = list_classifications(
            str(getattr(user, 'company_id', '')), safety_level, active_only, db_session=db,
        )
        return [_row_to_response(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify", response_model=ClassifyActionResponse)
def classify_tool(body: ClassifyActionRequest, user=Depends(lambda: None)):
    """Classify a tool name (ephemeral — does not persist). BC-008."""
    try:
        result = classify_action(body.tool_name, body.tool_description or "")
        return ClassifyActionResponse(
            safety_level=result.level.value,
            needs_approval=needs_approval(result.level),
            matched_keyword=result.matched_keyword,
            reasoning=result.reasoning,
            confidence=result.confidence,
            regulatory_frameworks=get_applicable_frameworks(result.level.value),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/persist", response_model=PersistClassificationResponse)
def persist_classification(
    body: PersistClassificationRequest,
    db: Session = Depends(lambda: None),
    user=Depends(lambda: None),
):
    """Classify AND persist a tool's safety classification. BC-001."""
    try:
        result = classify_and_persist(
            company_id=str(getattr(user, 'company_id', '')),
            tool_id=body.tool_id,
            tool_name=body.tool_name,
            tool_description=body.tool_description or "",
            output_schema=body.output_schema,
            db_session=db,
        )
        return PersistClassificationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tool_id}", response_model=ActionSafetyResponse)
def get_action(
    tool_id: str,
    db: Session = Depends(lambda: None),
    user=Depends(lambda: None),
):
    """Get safety classification for a specific tool. BC-001."""
    try:
        row = get_classification(str(getattr(user, 'company_id', '')), tool_id, db_session=db)
        if not row:
            raise HTTPException(status_code=404, detail="Classification not found")
        return _row_to_response(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{tool_id}/override", response_model=ActionSafetyResponse)
def override_approval(
    tool_id: str,
    body: OverrideRequest,
    db: Session = Depends(lambda: None),
    user=Depends(lambda: None),
):
    """Toggle approval_required_override for a tool. BC-001."""
    try:
        row = toggle_override(
            str(getattr(user, 'company_id', '')), tool_id, body.approval_required_override, db_session=db,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Classification not found")
        return _row_to_response(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
