"""
PARWA Ticket API - F-046 Ticket CRUD Endpoints (Day 26)

Implements F-046: Ticket CRUD API with:
- PS01: Out-of-plan scope check
- PS05: Duplicate detection
- PS07: Account suspended check
- BL05: Rate limiting
- BL06: Attachment validation
- BL07: PII scanning

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.exceptions import NotFoundError, AuthorizationError, ValidationError
from backend.app.services.ticket_service import TicketService
from backend.app.services.priority_service import PriorityService
from backend.app.services.category_service import CategoryService
from backend.app.services.tag_service import TagService
from backend.app.services.attachment_service import AttachmentService
from backend.app.services.pii_scan_service import PIIScanService
from backend.app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    TicketFilter,
    TicketStatusUpdate,
    TicketAssign,
    TicketStatusUpdateResponse,
    TicketAssignResponse,
    TicketBulkStatusUpdate,
    TicketBulkAssign,
    TicketBulkOperationResponse,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


# ── TICKET CRUD ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ticket",
)
async def create_ticket(
    request: Request,
    data: TicketCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Create a new ticket.

    F-046: Ticket creation with production handlers.
    PS01: Out-of-plan scope check.
    PS05: Duplicate detection.
    PS07: Account suspended check.
    BL05: Rate limiting.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    try:
        ticket = service.create_ticket(
            customer_id=data.customer_id,
            channel=data.channel,
            subject=data.subject,
            priority=data.priority,
            category=data.category,
            tags=data.tags,
            metadata_json=data.metadata_json,
            user_id=user_id,
        )

        return _ticket_to_response(ticket)

    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=TicketListResponse,
    summary="List tickets",
)
async def list_tickets(
    request: Request,
    # Filter parameters
    status: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    assigned_to: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    is_spam: Optional[bool] = Query(None),
    is_frozen: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List tickets with filters and pagination.

    F-046: Ticket listing with filtering.
    """
    company_id = current_user.get("company_id")

    service = TicketService(db, company_id)

    tickets, total = service.list_tickets(
        status=status,
        priority=priority,
        category=category,
        assigned_to=assigned_to,
        channel=channel,
        customer_id=customer_id,
        tags=tags,
        is_spam=is_spam,
        is_frozen=is_frozen,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return TicketListResponse(
        items=[_ticket_to_response(t) for t in tickets],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── BULK OPERATIONS (must come BEFORE /{ticket_id} routes) ────────────────────

@router.post(
    "/bulk/status",
    response_model=TicketBulkOperationResponse,
    summary="Bulk status update",
)
async def bulk_status_update(
    data: TicketBulkStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Bulk update ticket status.

    F-051: Bulk operations.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    success_count, failures = service.bulk_update_status(
        ticket_ids=data.ticket_ids,
        status=data.status,
        reason=data.reason,
        user_id=user_id,
    )

    return TicketBulkOperationResponse(
        success_count=success_count,
        failure_count=len(failures),
        total_requested=len(data.ticket_ids),
        failed_ids=failures,
    )


@router.post(
    "/bulk/assign",
    response_model=TicketBulkOperationResponse,
    summary="Bulk assign tickets",
)
async def bulk_assign(
    data: TicketBulkAssign,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Bulk assign tickets.

    F-051: Bulk operations.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    success_count, failures = service.bulk_assign(
        ticket_ids=data.ticket_ids,
        assignee_id=data.assignee_id,
        assignee_type=data.assignee_type,
        reason=data.reason,
        user_id=user_id,
    )

    return TicketBulkOperationResponse(
        success_count=success_count,
        failure_count=len(failures),
        total_requested=len(data.ticket_ids),
        failed_ids=failures,
    )


# ── DETECTION ENDPOINTS (must come BEFORE /{ticket_id} routes) ───────────────

@router.post(
    "/detect-priority",
    summary="Detect priority from text",
)
async def detect_priority(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Detect priority from text content.

    MF01: Priority auto-assignment.
    """
    company_id = current_user.get("company_id")

    body = await request.json()
    text = body.get("text", "")

    service = PriorityService(db, company_id)

    priority, confidence = service.detect_priority(text)

    return {
        "priority": priority,
        "confidence": confidence,
    }


@router.post(
    "/detect-category",
    summary="Detect category from text",
)
async def detect_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Detect category from text content.

    MF02: Category routing.
    """
    company_id = current_user.get("company_id")

    body = await request.json()
    subject = body.get("subject", "")
    message = body.get("message", "")
    metadata = body.get("metadata")

    service = CategoryService(db, company_id)

    category, confidence, all_scores = service.detect_category_advanced(
        subject=subject,
        message=message,
        metadata=metadata,
    )

    return {
        "category": category,
        "confidence": confidence,
        "all_scores": all_scores,
        "department": service.get_department(category),
    }


@router.post(
    "/scan-pii",
    summary="Scan text for PII",
)
async def scan_pii(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Scan text for PII.

    BL07: PII scanning.
    PS29: Sensitive data detection.
    """
    company_id = current_user.get("company_id")

    body = await request.json()
    text = body.get("text", "")
    scan_types = body.get("scan_types")

    service = PIIScanService(db, company_id)

    result = service.scan_and_redact(text, scan_types)

    return result


# ── TICKET DETAIL ROUTES (parameterized) ─────────────────────────────────────

@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket details",
)
async def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get a single ticket by ID.

    F-046: Ticket detail view.
    """
    company_id = current_user.get("company_id")

    service = TicketService(db, company_id)

    try:
        ticket = service.get_ticket(ticket_id)
        return _ticket_to_response(ticket)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket",
)
async def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Update ticket fields.

    F-046: Ticket update.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    try:
        ticket = service.update_ticket(
            ticket_id=ticket_id,
            priority=data.priority,
            category=data.category,
            tags=data.tags,
            status=data.status,
            assigned_to=data.assigned_to,
            subject=data.subject,
            user_id=user_id,
        )

        return _ticket_to_response(ticket)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete ticket",
)
async def delete_ticket(
    ticket_id: str,
    hard: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Dict:
    """Delete a ticket (soft delete by default).

    PS12: Soft delete preserves metadata for audit.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    try:
        service.delete_ticket(
            ticket_id=ticket_id,
            hard=hard,
            user_id=user_id,
        )
        return {"deleted": True, "ticket_id": ticket_id}

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ── STATUS MANAGEMENT ───────────────────────────────────────────────────────

@router.patch(
    "/{ticket_id}/status",
    response_model=TicketStatusUpdateResponse,
    summary="Update ticket status",
)
async def update_ticket_status(
    ticket_id: str,
    data: TicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Update ticket status with state machine validation.

    F-046: Status update with validation.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    try:
        # Get old status
        ticket = service.get_ticket(ticket_id)
        old_status = ticket.status

        # Update
        ticket = service.update_ticket(
            ticket_id=ticket_id,
            status=data.status,
            user_id=user_id,
            reason=data.reason,
        )

        return TicketStatusUpdateResponse(
            ticket_id=ticket_id,
            old_status=old_status,
            new_status=data.status,
            updated_at=ticket.updated_at,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ── ASSIGNMENT ──────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/assign",
    response_model=TicketAssignResponse,
    summary="Assign ticket",
)
async def assign_ticket(
    ticket_id: str,
    data: TicketAssign,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Assign a ticket to an agent.

    F-046: Ticket assignment.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketService(db, company_id)

    try:
        # Get old assignee
        ticket = service.get_ticket(ticket_id)
        previous_assignee = ticket.assigned_to

        # Assign
        ticket = service.assign_ticket(
            ticket_id=ticket_id,
            assignee_id=data.assignee_id,
            assignee_type=data.assignee_type,
            reason=data.reason,
            user_id=user_id,
        )

        return TicketAssignResponse(
            ticket_id=ticket_id,
            previous_assignee_id=previous_assignee,
            new_assignee_id=data.assignee_id,
            assignee_type=data.assignee_type,
            assigned_at=ticket.updated_at,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ── TAGS ────────────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/tags",
    response_model=TicketResponse,
    summary="Add tags to ticket",
)
async def add_tags(
    ticket_id: str,
    tags: List[str],
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Add tags to a ticket.

    MF03: Tag management.
    """
    company_id = current_user.get("company_id")

    service = TicketService(db, company_id)

    try:
        ticket = service.add_tags(ticket_id, tags)
        return _ticket_to_response(ticket)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete(
    "/{ticket_id}/tags/{tag}",
    response_model=TicketResponse,
    summary="Remove tag from ticket",
)
async def remove_tag(
    ticket_id: str,
    tag: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Remove a tag from a ticket.

    MF03: Tag management.
    """
    company_id = current_user.get("company_id")

    service = TicketService(db, company_id)

    try:
        ticket = service.remove_tag(ticket_id, tag)
        return _ticket_to_response(ticket)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ── ATTACHMENTS ─────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Upload attachment",
)
async def upload_attachment(
    ticket_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Upload an attachment to a ticket.

    BL06: Attachment validation.
    PS09: File size limits.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")
    plan_tier = current_user.get("plan_tier", "starter")

    # Get file from request
    form = await request.form()
    file = form.get("file")

    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    # Read file content
    content = await file.read()
    filename = file.filename or "attachment"

    service = AttachmentService(db, company_id, plan_tier)

    try:
        attachment = service.upload_attachment(
            ticket_id=ticket_id,
            filename=filename,
            file_content=content,
            uploaded_by=user_id,
        )

        return {
            "id": attachment.id,
            "filename": attachment.filename,
            "file_url": attachment.file_url,
            "file_size": attachment.file_size,
            "mime_type": attachment.mime_type,
            "created_at": attachment.created_at,
        }

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{ticket_id}/attachments",
    summary="List attachments",
)
async def list_attachments(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List attachments for a ticket.

    F-046: Attachment listing.
    """
    company_id = current_user.get("company_id")

    service = AttachmentService(db, company_id)

    attachments = service.get_attachments(ticket_id)

    return [
        {
            "id": a.id,
            "filename": a.filename,
            "file_url": a.file_url,
            "file_size": a.file_size,
            "mime_type": a.mime_type,
            "created_at": a.created_at,
        }
        for a in attachments
    ]


# ── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def _ticket_to_response(ticket: Any) -> TicketResponse:
    """Convert Ticket model to TicketResponse schema."""
    tags = []
    if ticket.tags:
        try:
            tags = json.loads(ticket.tags)
        except (json.JSONDecodeError, TypeError):
            tags = []

    metadata_json = {}
    if ticket.metadata_json:
        try:
            metadata_json = json.loads(ticket.metadata_json)
        except (json.JSONDecodeError, TypeError):
            metadata_json = {}

    plan_snapshot = {}
    if hasattr(ticket, 'plan_snapshot') and ticket.plan_snapshot:
        try:
            plan_snapshot = json.loads(ticket.plan_snapshot)
        except (json.JSONDecodeError, TypeError):
            plan_snapshot = {}

    now = datetime.utcnow()

    return TicketResponse(
        id=ticket.id,
        company_id=ticket.company_id,
        customer_id=ticket.customer_id,
        channel=ticket.channel,
        status=ticket.status,
        subject=ticket.subject,
        priority=ticket.priority,
        category=ticket.category,
        tags=tags,
        agent_id=ticket.agent_id,
        assigned_to=ticket.assigned_to,
        classification_intent=ticket.classification_intent,
        classification_type=ticket.classification_type,
        metadata_json=metadata_json,
        reopen_count=ticket.reopen_count or 0,
        frozen=ticket.frozen or False,
        parent_ticket_id=ticket.parent_ticket_id,
        duplicate_of_id=ticket.duplicate_of_id,
        is_spam=ticket.is_spam or False,
        awaiting_human=ticket.awaiting_human or False,
        awaiting_client=ticket.awaiting_client or False,
        escalation_level=ticket.escalation_level or 1,
        sla_breached=ticket.sla_breached or False,
        first_response_at=ticket.first_response_at,
        resolution_target_at=ticket.resolution_target_at,
        client_timezone=ticket.client_timezone,
        plan_snapshot=plan_snapshot,
        variant_version=ticket.variant_version,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        closed_at=ticket.closed_at,
    )
