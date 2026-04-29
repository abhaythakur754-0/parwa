"""
PARWA Ticket Bulk Action API - F-051 Bulk Operations Endpoints (Day 29)

Implements F-051: Bulk Action API with:
- Bulk status changes
- Bulk reassignment
- Bulk tagging
- Bulk priority changes
- Bulk close
- Undo mechanism

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.schemas.bulk_action import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionType,
)
from app.services.bulk_action_service import (
    BulkActionService,
    BulkActionError,
    BulkActionNotFoundError,
    BulkActionAlreadyUndoneError,
    BulkActionUndoExpiredError,
)

router = APIRouter(
    prefix="/tickets/bulk",
    tags=["bulk-actions"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


@router.post(
    "",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute bulk action on tickets",
)
async def execute_bulk_action(
    data: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Execute a bulk action on multiple tickets.

    Supports:
    - status_change: Change ticket status (requires new_status in params)
    - reassign: Reassign tickets (requires assignee_id in params)
    - tag: Add/remove/replace tags (requires tags in params)
    - priority: Change priority (requires priority in params)
    - close: Close tickets

    Max 500 tickets per bulk action.
    Undo available within 24 hours.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=data.action_type.value,
            ticket_ids=data.ticket_ids,
            params=data.params,
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=data.action_type,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={
                "created_at": bulk_action.created_at.isoformat(),
            },
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/status",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk status change",
)
async def bulk_status_change(
    ticket_ids: List[str],
    new_status: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Bulk change ticket status.

    Convenience endpoint for status changes.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=BulkActionType.STATUS_CHANGE.value,
            ticket_ids=ticket_ids,
            params={"new_status": new_status, "reason": reason},
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=BulkActionType.STATUS_CHANGE,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={},
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/assign",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assign tickets",
)
async def bulk_assign(
    ticket_ids: List[str],
    assignee_id: str,
    assignee_type: str = "human",
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Bulk assign tickets to an agent.

    Convenience endpoint for reassignment.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=BulkActionType.REASSIGN.value,
            ticket_ids=ticket_ids,
            params={
                "assignee_id": assignee_id,
                "assignee_type": assignee_type,
                "reason": reason,
            },
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=BulkActionType.REASSIGN,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={},
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/tags",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk tag tickets",
)
async def bulk_tags(
    ticket_ids: List[str],
    tags: List[str],
    tag_action: str = "add",  # add, remove, replace
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Bulk add/remove/replace tags on tickets.

    tag_action:
    - add: Add tags to existing tags
    - remove: Remove specified tags
    - replace: Replace all tags with new ones
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=BulkActionType.TAG.value,
            ticket_ids=ticket_ids,
            params={"tags": tags, "tag_action": tag_action},
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=BulkActionType.TAG,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={},
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/priority",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk priority change",
)
async def bulk_priority(
    ticket_ids: List[str],
    priority: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Bulk change ticket priority.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=BulkActionType.PRIORITY.value,
            ticket_ids=ticket_ids,
            params={"priority": priority},
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=BulkActionType.PRIORITY,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={},
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/close",
    response_model=BulkActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk close tickets",
)
async def bulk_close(
    ticket_ids: List[str],
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Bulk close tickets.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    try:
        bulk_action, success_count, failure_count = service.execute_bulk_action(
            company_id=company_id,
            action_type=BulkActionType.CLOSE.value,
            ticket_ids=ticket_ids,
            params={"reason": reason},
            performed_by=user_id,
        )

        return BulkActionResponse(
            id=bulk_action.id,
            action_type=BulkActionType.CLOSE,
            success_count=success_count,
            failure_count=failure_count,
            undo_token=bulk_action.undo_token,
            result_summary={},
        )

    except BulkActionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/undo/{undo_token}",
    summary="Undo bulk action",
)
async def undo_bulk_action(
    undo_token: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Undo a bulk action within 24 hours.

    Uses the undo_token from the original bulk action response.
    """
    company_id = current_user.get("company_id")

    service = BulkActionService(db)

    try:
        bulk_action = service.undo_bulk_action(
            company_id=company_id,
            undo_token=undo_token,
        )

        return {
            "undone": True,
            "bulk_action_id": bulk_action.id,
            "action_type": bulk_action.action_type,
        }

    except BulkActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bulk action not found",
        )
    except BulkActionAlreadyUndoneError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk action already undone",
        )
    except BulkActionUndoExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Undo window expired (24 hours)",
        )


@router.get(
    "/history",
    summary="List bulk action history",
)
async def list_bulk_actions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    List bulk action history for the company.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = BulkActionService(db)

    bulk_actions, total = service.list_bulk_actions(
        company_id=company_id,
        limit=limit,
        offset=offset,
        action_type=action_type,
    )

    return {
        "items": [
            {
                "id": ba.id,
                "action_type": ba.action_type,
                "ticket_count": (
                    len(ba.ticket_ids.split(","))
                    if isinstance(ba.ticket_ids, str)
                    else len(ba.ticket_ids)
                ),
                "performed_by": ba.performed_by,
                "undone": ba.undone,
                "created_at": ba.created_at,
            }
            for ba in bulk_actions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{bulk_action_id}",
    summary="Get bulk action details",
)
async def get_bulk_action(
    bulk_action_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get detailed information about a bulk action including failures.
    """
    company_id = current_user.get("company_id")

    service = BulkActionService(db)

    bulk_action = service.get_bulk_action(company_id, bulk_action_id)

    if not bulk_action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bulk action not found",
        )

    failures = service.get_bulk_action_failures(company_id, bulk_action_id)

    import json

    ticket_ids = json.loads(bulk_action.ticket_ids) if bulk_action.ticket_ids else []

    return {
        "id": bulk_action.id,
        "action_type": bulk_action.action_type,
        "ticket_ids": ticket_ids,
        "performed_by": bulk_action.performed_by,
        "result_summary": bulk_action.result_summary,
        "undo_token": bulk_action.undo_token,
        "undone": bulk_action.undone,
        "created_at": bulk_action.created_at,
        "failures": [
            {
                "ticket_id": f.ticket_id,
                "error_message": f.error_message,
                "failure_reason": f.failure_reason,
            }
            for f in failures
        ],
    }
