"""
PARWA Ticket Merge API - F-051 Merge/Unmerge Endpoints (Day 29)

Implements F-051: Ticket merge/unmerge API with:
- Merge multiple tickets into a primary ticket
- Unmerge (undo) capability
- Merge history tracking
- PS26: Unmerge preserves message history

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.schemas.bulk_action import (
    TicketMergeRequest,
    TicketUnmergeRequest,
    TicketMergeResponse,
)
from backend.app.services.ticket_merge_service import (
    TicketMergeService,
    TicketMergeError,
    TicketNotFoundError,
    TicketAlreadyMergedError,
    MergeAlreadyUndoneError,
    CrossTenantMergeError,
)


router = APIRouter(prefix="/tickets/merge", tags=["ticket-merge"])


@router.post(
    "",
    response_model=TicketMergeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Merge tickets",
)
async def merge_tickets(
    data: TicketMergeRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Merge multiple tickets into a primary ticket.
    
    The primary ticket will retain all messages from merged tickets.
    Merged tickets will be closed with a reference to the merge.
    
    An undo_token is returned for unmerge capability within 24 hours.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")
    
    service = TicketMergeService(db)
    
    try:
        merge_record, primary_ticket = service.merge_tickets(
            company_id=company_id,
            primary_ticket_id=data.primary_ticket_id,
            merged_ticket_ids=data.merged_ticket_ids,
            merged_by=user_id,
            reason=data.reason,
        )
        
        return TicketMergeResponse(
            id=merge_record.id,
            primary_ticket_id=merge_record.primary_ticket_id,
            merged_ticket_ids=data.merged_ticket_ids,
            undo_token=merge_record.undo_token,
            undone=merge_record.undone,
            merged_at=merge_record.created_at,
        )
        
    except TicketNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except TicketAlreadyMergedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CrossTenantMergeError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except TicketMergeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/unmerge/{merge_id}",
    summary="Unmerge tickets (PS26)",
)
async def unmerge_tickets(
    merge_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Unmerge previously merged tickets.
    
    PS26: Unmerge preserves message history.
    Restores merged tickets to reopened status.
    """
    company_id = current_user.get("company_id")
    
    service = TicketMergeService(db)
    
    try:
        merge_record, restored_tickets = service.unmerge_tickets(
            company_id=company_id,
            merge_id=merge_id,
        )
        
        return {
            "unmerged": True,
            "merge_id": merge_id,
            "restored_ticket_ids": [t.id for t in restored_tickets],
            "restored_count": len(restored_tickets),
        }
        
    except TicketNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merge record not found",
        )
    except MergeAlreadyUndoneError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merge has already been undone",
        )
    except TicketMergeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/history/{ticket_id}",
    summary="Get merge history for a ticket",
)
async def get_merge_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get all merge operations involving a ticket.
    
    Returns both merges where ticket is primary and where it was merged.
    """
    company_id = current_user.get("company_id")
    
    service = TicketMergeService(db)
    
    merges = service.get_merge_history(company_id, ticket_id)
    
    import json
    
    return {
        "ticket_id": ticket_id,
        "merges": [
            {
                "id": m.id,
                "primary_ticket_id": m.primary_ticket_id,
                "merged_ticket_ids": json.loads(m.merged_ticket_ids),
                "merged_by": m.merged_by,
                "reason": m.reason,
                "undone": m.undone,
                "created_at": m.created_at,
            }
            for m in merges
        ],
        "total": len(merges),
    }


@router.post(
    "/check",
    summary="Check if tickets can be merged",
)
async def check_merge_eligibility(
    ticket_ids: List[str],
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Check if a set of tickets can be merged.
    
    Returns list of any issues that would prevent merging.
    """
    company_id = current_user.get("company_id")
    
    service = TicketMergeService(db)
    
    can_merge, reasons = service.can_merge_tickets(company_id, ticket_ids)
    
    return {
        "can_merge": can_merge,
        "issues": reasons,
    }


@router.get(
    "/{merge_id}",
    summary="Get merge details",
)
async def get_merge_details(
    merge_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get detailed information about a merge operation.
    """
    company_id = current_user.get("company_id")
    
    service = TicketMergeService(db)
    
    merge = service.get_merge_by_id(company_id, merge_id)
    
    if not merge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merge record not found",
        )
    
    import json
    
    return {
        "id": merge.id,
        "primary_ticket_id": merge.primary_ticket_id,
        "merged_ticket_ids": json.loads(merge.merged_ticket_ids),
        "merged_by": merge.merged_by,
        "reason": merge.reason,
        "undo_token": merge.undo_token,
        "undone": merge.undone,
        "created_at": merge.created_at,
    }
