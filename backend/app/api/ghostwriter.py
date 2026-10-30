"""
Ghostwriter API — draft help articles from a client's own knowledge gaps.

Tenant lock: every route resolves company_id from the authenticated
user (BC-001). Approve/reject filters by BOTH id and company_id, so a
client physically cannot touch another client's drafts.

Honesty: nothing auto-publishes. Approve is a recorded human decision AND
the explicit step that feeds the approved article into the agent's
knowledge store (knowledge_documents + document_chunks) — the same tables
the live pipeline's knowledge fetch reads. Publish failures never undo
the approval; they are reported honestly in the response.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_company_id
from app.services.ghostwriter_service import (
    DraftCapReached,
    GhostwriterDisabled,
    approve_and_publish,
    create_draft_from_gap,
    list_drafts,
    set_draft_status,
)
from database.base import get_db

router = APIRouter(prefix="/api/ghostwriter", tags=["Ghostwriter"])


class DraftRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=255)


@router.post("/drafts", status_code=201)
async def create_draft(
    req: DraftRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Draft an article for a gap — on demand, uses this company's data only."""
    try:
        draft = await create_draft_from_gap(db, company_id, req.topic)
    except GhostwriterDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except DraftCapReached as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Daily draft cap reached ({exc.used}/{exc.cap}). Try tomorrow.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": draft.id,
        "gap_topic": draft.gap_topic,
        "status": draft.status,
        "title": draft.title,
        "content": draft.content,
        "sources": draft.sources_json,
        "model_used": draft.model_used,
    }


@router.get("/drafts")
async def get_drafts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """All drafts for the caller's company, newest first."""
    rows, total = list_drafts(db, company_id, limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "drafts": rows}


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = approve_and_publish(db, company_id, draft_id)
    if result["id"] is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return result


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    draft = set_draft_status(db, company_id, draft_id, "rejected")
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"id": draft.id, "status": draft.status}
