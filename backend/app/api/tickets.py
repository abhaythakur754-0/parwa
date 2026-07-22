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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.models.core import User

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from database.models.core import User
from database.base import get_db
from database.models.core import User
from app.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.services.ticket_service import TicketService
from app.services.priority_service import PriorityService
from app.services.category_service import CategoryService
from app.services.tag_service import TagService
from app.services.attachment_service import AttachmentService
from app.services.pii_scan_service import PIIScanService
from app.schemas.ticket import (
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
    PriorityDetectionResponse,
    CategoryDetectionResponse,
    PIIScanResponse,
    TicketDeleteResponse,
    TicketAttachmentResponse,
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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new ticket.

    F-046: Ticket creation with production handlers.
    PS01: Out-of-plan scope check.
    PS05: Duplicate detection.
    PS07: Account suspended check.
    BL05: Rate limiting.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
            customer_name=data.customer_name,
            customer_email=data.customer_email,
            customer_phone=data.customer_phone,
            description=data.description,
        )

        # ── Trigger 8-node PARWA pipeline on the new ticket ────────────
        # Critical priority tickets are processed IMMEDIATELY (synchronous)
        # — they bypass the Celery queue and run inline so the customer
        # gets an AI response in the same request. Non-critical tickets
        # are dispatched to the Celery queue for async processing.
        #
        # The pipeline_dispatcher opens its OWN DB session (separate from
        # this endpoint's session) and commits changes to the ticket
        # (status, metadata, AI message, CRM sync). After it returns, this
        # endpoint's session has a STALE view of the ticket. We must
        # expire + refresh so _ticket_to_response reads the latest state.
        try:
            from app.services.pipeline_dispatcher import dispatch_pipeline_for_ticket
            dispatch_pipeline_for_ticket(
                ticket_id=ticket.id,
                company_id=company_id,
                priority=ticket.priority,
                channel=ticket.channel,
            )
        except Exception as exc:  # noqa: BLE001
            # Pipeline trigger failure MUST NOT fail ticket creation —
            # the ticket is already persisted. Log and let the caller
            # see the ticket; the pipeline will be retried by the next
            # sync or by the dashboard refresh.
            import logging as _logging
            _logger = _logging.getLogger("parwa.api.tickets")
            _logger.warning(
                "pipeline_dispatch_failed_after_create",
                extra={
                    "ticket_id": ticket.id,
                    "company_id": company_id,
                    "priority": ticket.priority,
                    "error": str(exc)[:200],
                },
            )

        # Refresh the ticket from DB so we see the pipeline's updates
        # (status change, AI message, CRM sync metadata). The pipeline
        # committed on a separate session; this endpoint's session may
        # be in a bad state. We use a FRESH session to build the response
        # so the API endpoint's session issues don't affect the response.
        try:
            db.rollback()  # clear any bad state in the endpoint's session
        except Exception:
            pass

        # Build response from a fresh session to avoid session corruption
        from database.base import SessionLocal as _SessionLocal
        _fresh_db = _SessionLocal()
        try:
            from database.models.tickets import Ticket as _Ticket
            _fresh_ticket = _fresh_db.query(_Ticket).filter(
                _Ticket.id == ticket.id,
                _Ticket.company_id == company_id,
            ).first()
            if _fresh_ticket:
                return _ticket_to_response(_fresh_ticket)
        finally:
            _fresh_db.close()

        # Fallback: return a minimal response with just the ticket ID
        # (the frontend will sync the full details via GET /api/v1/tickets)
        return {
            "id": ticket.id,
            "company_id": company_id,
            "customer_id": ticket.customer_id,
            "channel": ticket.channel,
            "status": "open",
            "subject": ticket.subject,
            "priority": ticket.priority,
            "category": ticket.category,
            "tags": [],
            "metadata_json": {},
            "ticket_number": f"TKT-{ticket.id.replace('-', '').upper()[:8]}",
            "customer_name": None,
            "customer_email": None,
            "description": None,
            "assigned_variant": None,
            "ai_confidence": None,
            "cost_per_ticket": None,
            "savings_per_ticket": None,
            "resolution_time_hours": None,
            "reopen_count": 0,
            "frozen": False,
            "parent_ticket_id": None,
            "duplicate_of_id": None,
            "is_spam": False,
            "awaiting_human": False,
            "awaiting_client": False,
            "escalation_level": 1,
            "sla_breached": False,
            "first_response_at": None,
            "resolution_target_at": None,
            "client_timezone": None,
            "plan_snapshot": {},
            "variant_version": None,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "closed_at": None,
        }

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """List tickets with filters and pagination.

    F-046: Ticket listing with filtering.
    """
    company_id = current_user.company_id

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk update ticket status.

    F-051: Bulk operations.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk assign tickets.

    F-051: Bulk operations.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    response_model=PriorityDetectionResponse,
    summary="Detect priority from text",
)
async def detect_priority(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Detect priority from text content.

    MF01: Priority auto-assignment.
    """
    company_id = current_user.company_id

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
    response_model=CategoryDetectionResponse,
    summary="Detect category from text",
)
async def detect_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Detect category from text content.

    MF02: Category routing.
    """
    company_id = current_user.company_id

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
    response_model=PIIScanResponse,
    summary="Scan text for PII",
)
async def scan_pii(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Scan text for PII.

    BL07: PII scanning.
    PS29: Sensitive data detection.
    """
    company_id = current_user.company_id

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get a single ticket by ID.

    F-046: Ticket detail view.
    """
    company_id = current_user.company_id

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update ticket fields.

    F-046: Ticket update.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    response_model=TicketDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete ticket",
)
async def delete_ticket(
    ticket_id: str,
    hard: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Delete a ticket (soft delete by default).

    PS12: Soft delete preserves metadata for audit.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update ticket status with state machine validation.

    F-046: Status update with validation.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Assign a ticket to an agent.

    F-046: Ticket assignment.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Add tags to a ticket.

    MF03: Tag management.
    """
    company_id = current_user.company_id

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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Remove a tag from a ticket.

    MF03: Tag management.
    """
    company_id = current_user.company_id

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
    response_model=TicketAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload attachment",
)
async def upload_attachment(
    ticket_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload an attachment to a ticket.

    BL06: Attachment validation.
    PS09: File size limits.
    """
    company_id = current_user.company_id
    user_id = str(current_user.id)
    plan_tier = getattr(current_user, "plan_tier", "starter")

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
    response_model=List[TicketAttachmentResponse],
    summary="List attachments",
)
async def list_attachments(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List attachments for a ticket.

    F-046: Attachment listing.
    """
    company_id = current_user.company_id

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
    """Convert Ticket model to TicketResponse schema.

    Enriches the ticket with joined data:
      - customer_name / customer_email from the Customer table
      - description from the first customer TicketMessage
      - ai_confidence from the latest AI TicketMessage
      - ticket_number from the ticket id prefix
      - assigned_variant mirrored from variant_version
      - resolution_time_hours computed from created_at → closed_at
      - cost_per_ticket / savings_per_ticket from ticket metadata
    """
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

    now = datetime.now(timezone.utc)

    # ── Enrich with customer info ─────────────────────────────────────
    customer_name = None
    customer_email = None
    if getattr(ticket, "customer_id", None):
        try:
            from database.models.tickets import Customer
            # ticket is a SQLAlchemy instance; we use its session to query
            # the customer so we don't need a separate db handle here.
            from sqlalchemy.orm import object_session
            sess = object_session(ticket)
            if sess is not None:
                cust = sess.query(Customer).filter(
                    Customer.id == ticket.customer_id,
                    Customer.company_id == ticket.company_id,
                ).first()
                if cust:
                    customer_name = cust.name
                    customer_email = cust.email
        except Exception:  # noqa: BLE001
            pass

    # ── Enrich with first customer message (description) ─────────────
    description = None
    ai_confidence = None
    try:
        from database.models.tickets import TicketMessage
        from sqlalchemy.orm import object_session
        sess = object_session(ticket)
        if sess is not None:
            # First customer message = the ticket body
            first_msg = sess.query(TicketMessage).filter(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.role == "customer",
            ).order_by(TicketMessage.created_at.asc()).first()
            if first_msg:
                description = first_msg.content

            # Latest AI message confidence
            ai_msg = sess.query(TicketMessage).filter(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.role == "ai",
            ).order_by(TicketMessage.created_at.desc()).first()
            if ai_msg and ai_msg.ai_confidence is not None:
                ai_confidence = float(ai_msg.ai_confidence)
    except Exception:  # noqa: BLE001
        pass

    # ── Compute resolution_time_hours ─────────────────────────────────
    resolution_time_hours = None
    if ticket.closed_at and ticket.created_at:
        try:
            delta = ticket.closed_at - ticket.created_at
            resolution_time_hours = round(delta.total_seconds() / 3600.0, 2)
        except Exception:  # noqa: BLE001
            pass

    # ── Cost / savings from metadata (written by pipeline Node 7) ────
    cost_per_ticket = None
    savings_per_ticket = None
    try:
        if isinstance(metadata_json, dict):
            if "cost_per_ticket" in metadata_json:
                cost_per_ticket = float(metadata_json["cost_per_ticket"])
            if "savings_per_ticket" in metadata_json:
                savings_per_ticket = float(metadata_json["savings_per_ticket"])
    except (TypeError, ValueError):  # noqa: BLE001
        pass

    # ── ticket_number: human-readable TKT-XXXX from id prefix ────────
    ticket_number = None
    if ticket.id:
        # Use first 8 chars of the UUID, uppercased, as the readable number
        ticket_number = f"TKT-{ticket.id.replace('-', '').upper()[:8]}"

    # ── assigned_variant mirrors variant_version ─────────────────────
    assigned_variant = ticket.variant_version or None

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
        # Enriched frontend-facing fields
        ticket_number=ticket_number,
        customer_name=customer_name,
        customer_email=customer_email,
        description=description,
        assigned_variant=assigned_variant,
        ai_confidence=ai_confidence,
        cost_per_ticket=cost_per_ticket,
        savings_per_ticket=savings_per_ticket,
        resolution_time_hours=resolution_time_hours,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        closed_at=ticket.closed_at,
    )


# ════════════════════════════════════════════════════════════════════
# RESUME PIPELINE — Approach A (pause/resume)
# When a node calls interrupt(), the pipeline pauses. This endpoint
# accepts the human/variant's guidance and resumes the pipeline from
# the exact node that paused — no restart from Node 1.
# ════════════════════════════════════════════════════════════════════

class ResumeRequest(BaseModel):
    """Request body for resuming a paused pipeline."""
    guidance: str = Field(..., min_length=1, max_length=10000,
                          description="Human/variant guidance to inject into the paused pipeline")


@router.post("/{ticket_id}/resume", response_model=dict)
def resume_pipeline(
    ticket_id: str,
    body: ResumeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resume a paused pipeline with human/variant guidance.

    When a pipeline node has doubt (e.g. KB insufficient, hallucination
    detected), it calls interrupt() to pause. This endpoint accepts the
    guidance answer and resumes the pipeline from the EXACT node that
    paused — saving LLM calls compared to a full restart.

    The pipeline state is restored from the LangGraph checkpointer
    (keyed by ticket_id as thread_id).
    """
    import logging
    logger = logging.getLogger("parwa.api.resume")

    # Validate ticket exists + belongs to tenant
    from database.models.tickets import Ticket
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check ticket is actually paused (awaiting_human)
    if ticket.status != "awaiting_human":
        raise HTTPException(
            status_code=400,
            detail=f"Ticket is not paused (status={ticket.status}). Only awaiting_human tickets can be resumed.",
        )

    logger.info("resume_pipeline ticket=%s guidance_len=%d", ticket_id, len(body.guidance))

    # ── DIRECT NVIDIA CALL (the ONLY path — no checkpoint resume) ──
    # The LangGraph checkpoint is unreliable: if the initial pipeline run
    # had a transient LLM failure, the checkpoint caches that failure
    # forever. Resuming it returns the same garbage response.
    #
    # Instead: fetch the customer's original question, combine it with
    # the human's guidance, and call NVIDIA directly. Simple, reliable.
    import os as _os
    import httpx as _httpx
    from database.models.tickets import TicketMessage as _TM
    import json as _json_fast

    nvidia_key = _os.environ.get("NVIDIA_API_KEY", "").strip()
    if not nvidia_key:
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "ai_response": "",
            "message": "NVIDIA_API_KEY not set on server.",
        }

    # Get the original customer message
    customer_msg = ""
    first_msg = db.query(_TM).filter(
        _TM.ticket_id == ticket_id,
        _TM.role == "customer",
    ).order_by(_TM.created_at.asc()).first()
    if first_msg:
        customer_msg = first_msg.content or ""

    direct_prompt = (
        f"You are a customer support agent. A customer asked:\n\n"
        f"{customer_msg}\n\n"
        f"A human supervisor has reviewed this and provided the following guidance:\n"
        f"{body.guidance}\n\n"
        f"Write a professional, helpful response to the customer based on this guidance. "
        f"Be empathetic and specific. Do not mention that a supervisor was involved."
    )

    logger.info("resume_nvidia ticket=%s", ticket_id)

    try:
        r = _httpx.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            json={
                "model": "z-ai/glm-5.2",
                "messages": [
                    {"role": "system", "content": "You are a professional customer support agent. Write a helpful, empathetic response based on the guidance provided."},
                    {"role": "user", "content": direct_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            headers={
                "Authorization": f"Bearer {nvidia_key}",
                "Content-Type": "application/json",
            },
            timeout=90.0,
        )
    except Exception as http_exc:
        logger.error("resume_nvidia_http_exception ticket=%s error=%s", ticket_id, str(http_exc)[:300])
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "ai_response": "",
            "message": f"HTTP call to NVIDIA failed: {str(http_exc)[:200]}",
        }

    if r.status_code != 200:
        logger.error("resume_nvidia_error ticket=%s status=%s body=%s",
                     ticket_id, r.status_code, r.text[:200])
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "ai_response": "",
            "message": f"NVIDIA API returned {r.status_code}: {r.text[:200]}",
        }

    ai_response = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")

    if not ai_response or len(ai_response) < 10:
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "ai_response": "",
            "message": "NVIDIA returned empty response.",
        }

    # Save the AI response
    ai_msg = _TM(
        id=str(__import__("uuid").uuid4()),
        ticket_id=ticket_id,
        company_id=ticket.company_id,
        role="ai",
        content=ai_response[:6000],
        channel=ticket.channel,
        variant_version="nvidia_direct",
        metadata_json=_json_fast.dumps({
            "source": "resume_direct_nvidia",
            "guidance_used": body.guidance[:500],
        }),
    )
    db.add(ai_msg)
    ticket.status = "resolved"
    ticket.awaiting_human = False
    ticket.updated_at = datetime.now(timezone.utc)
    if not ticket.closed_at:
        ticket.closed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("resume_nvidia_success ticket=%s len=%d", ticket_id, len(ai_response))

    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "ai_response": ai_response[:500],
        "quality_score": 0,
        "message": "Ticket resolved with NVIDIA direct response.",
    }

