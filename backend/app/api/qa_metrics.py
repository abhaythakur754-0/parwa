"""
AI QA Report Card API (GET only — grades are written by the pipeline hook).

Tenant lock: every query filters on the caller's company_id
(BC-001) taken from the authenticated user — a client can never read
another client's report card, by construction.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_company_id
from app.services.qa_service import get_flagged_conversations, get_qa_summary
from database.base import get_db

router = APIRouter(prefix="/api/qa", tags=["AI QA Report Card"])


@router.get("/summary")
async def qa_summary(
    days: int = Query(default=30, ge=1, le=365),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Report Card KPIs for the caller's company only."""
    return get_qa_summary(db, company_id, days=days)


@router.get("/conversations")
async def qa_conversations(
    flagged_only: bool = Query(default=True, alias="flagged"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Flagged conversations (with reasons) for the caller's company only."""
    rows, total = get_flagged_conversations(
        db, company_id, limit=limit, offset=offset,
    )
    return {
        "flagged": flagged_only,
        "total": total,
        "limit": limit,
        "offset": offset,
        "conversations": rows if flagged_only else rows,
    }
