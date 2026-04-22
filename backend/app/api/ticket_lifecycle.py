"""
Ticket Lifecycle API Endpoints (Day 32)

Endpoints for:
- Ticket escalation (PS02, PS03)
- Ticket reopen (PS04)
- Ticket freeze/thaw (PS07)
- Spam marking (PS15, MF21)
- Incident management (PS10)
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_tenant_context, require_roles
from app.services.ticket_lifecycle_service import TicketLifecycleService
from app.services.ticket_state_machine import TicketStateMachine, TransitionValidator
from app.services.stale_ticket_service import StaleTicketService
from app.services.incident_service import IncidentService, Incident
from app.services.spam_detection_service import SpamDetectionService
from database.models.core import User
from database.models.tickets import Ticket, TicketStatus


router = APIRouter(
    prefix="/tickets",
    tags=["Ticket Lifecycle"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


# ── Request/Response Schemas ───────────────────────────────────────────────────

class EscalateRequest(BaseModel):
    """Request to escalate a ticket."""
    reason: str = Field(..., description="Escalation reason")
    ai_summary: Optional[str] = Field(None, description="AI conversation summary")


class ReopenRequest(BaseModel):
    """Request to reopen a ticket."""
    reason: str = Field(..., description="Reason for reopening")


class FreezeRequest(BaseModel):
    """Request to freeze a ticket."""
    reason: str = Field(default="account_suspended", description="Reason for freezing")


class SpamMarkRequest(BaseModel):
    """Request to mark ticket as spam."""
    reason: str = Field(..., description="Reason for spam marking")


class SpamUnmarkRequest(BaseModel):
    """Request to unmark ticket as spam."""
    reason: str = Field(..., description="Reason for unmarking")


class IncidentCreateRequest(BaseModel):
    """Request to create an incident."""
    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Incident description")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    affected_services: Optional[List[str]] = Field(None, description="Affected services")
    master_ticket_id: Optional[str] = Field(None, description="Master ticket ID")


class IncidentUpdateRequest(BaseModel):
    """Request to update incident status."""
    status: str = Field(..., description="New status")
    message: Optional[str] = Field(None, description="Status update message")


class IncidentResolveRequest(BaseModel):
    """Request to resolve an incident."""
    resolution_summary: str = Field(..., description="Resolution summary")


class IncidentNotifyRequest(BaseModel):
    """Request to notify affected customers."""
    message: str = Field(..., description="Notification message")


class LinkTicketRequest(BaseModel):
    """Request to link a ticket to an incident."""
    ticket_id: str = Field(..., description="Ticket ID to link")


class AddAffectedCustomersRequest(BaseModel):
    """Request to add affected customers to incident."""
    customer_ids: List[str] = Field(..., description="Customer IDs to add")


# ── Ticket Lifecycle Endpoints ─────────────────────────────────────────────────

@router.post("/{ticket_id}/escalate")
async def escalate_ticket(
    ticket_id: str,
    request: EscalateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Manually escalate a ticket to human (PS02, PS03)."""
    lifecycle_service = TicketLifecycleService(db, tenant["company_id"])
    
    # Check if escalation is valid
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.company_id == tenant["company_id"],
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found"
        )
    
    can_escalate, error = TransitionValidator.validate_escalation(ticket)
    if not can_escalate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    result = lifecycle_service.handle_human_request(
        ticket_id=ticket_id,
        ai_summary=request.ai_summary or "",
        requested_by=current_user.id,
    )
    
    return {
        "success": True,
        "ticket_id": ticket_id,
        "new_status": result.status,
        "escalated": True,
    }


@router.post("/{ticket_id}/reopen")
async def reopen_ticket(
    ticket_id: str,
    request: ReopenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Reopen a closed/resolved ticket (PS04)."""
    lifecycle_service = TicketLifecycleService(db, tenant["company_id"])
    
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.company_id == tenant["company_id"],
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found"
        )
    
    can_reopen, error = TransitionValidator.validate_reopen(ticket)
    if not can_reopen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    try:
        result = lifecycle_service.reopen_ticket(
            ticket_id=ticket_id,
            reason=request.reason,
            reopened_by=current_user.id,
        )
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "new_status": result.status,
            "reopen_count": result.reopen_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{ticket_id}/freeze")
async def freeze_ticket(
    ticket_id: str,
    request: FreezeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Freeze a ticket (PS07)."""
    state_machine = TicketStateMachine(db, tenant["company_id"])
    
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.company_id == tenant["company_id"],
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found"
        )
    
    can_freeze, error = TransitionValidator.validate_freeze(ticket)
    if not can_freeze:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    try:
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.frozen,
            reason=request.reason,
            actor_id=current_user.id,
        )
        
        db.commit()
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": ticket.status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{ticket_id}/thaw")
async def thaw_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Thaw a frozen ticket (PS07)."""
    state_machine = TicketStateMachine(db, tenant["company_id"])
    
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.company_id == tenant["company_id"],
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found"
        )
    
    can_thaw, error = TransitionValidator.validate_thaw(ticket)
    if not can_thaw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    try:
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.open,
            reason="account_reactivated",
            actor_id=current_user.id,
        )
        
        db.commit()
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": ticket.status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{ticket_id}/spam")
async def mark_as_spam(
    ticket_id: str,
    request: SpamMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Mark a ticket as spam (PS15, MF21)."""
    spam_service = SpamDetectionService(db, tenant["company_id"])
    
    try:
        ticket = spam_service.mark_as_spam(
            ticket_id=ticket_id,
            reason=request.reason,
            marked_by=current_user.id,
        )
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "is_spam": ticket.is_spam,
            "status": ticket.status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{ticket_id}/spam")
async def unmark_as_spam(
    ticket_id: str,
    request: SpamUnmarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Remove spam marking from a ticket."""
    spam_service = SpamDetectionService(db, tenant["company_id"])
    
    try:
        ticket = spam_service.unmark_as_spam(
            ticket_id=ticket_id,
            reason=request.reason,
            unmarked_by=current_user.id,
        )
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "is_spam": ticket.is_spam,
            "status": ticket.status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{ticket_id}/transitions")
async def get_valid_transitions(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get valid status transitions for a ticket."""
    state_machine = TicketStateMachine(db, tenant["company_id"])
    
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.company_id == tenant["company_id"],
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found"
        )
    
    valid_transitions = state_machine.get_valid_transitions(ticket)
    
    return {
        "ticket_id": ticket_id,
        "current_status": ticket.status,
        "valid_transitions": [t.value for t in valid_transitions],
    }


# ── Stale Ticket Endpoints ───────────────────────────────────────────────────

@router.get("/stale")
async def get_stale_tickets(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get stale tickets."""
    stale_service = StaleTicketService(db, tenant["company_id"])
    
    stale_tickets = stale_service.detect_stale_tickets()
    
    return {
        "tickets": stale_tickets[offset:offset + limit],
        "total": len(stale_tickets),
        "statistics": stale_service.get_stale_statistics(),
    }


# ── Incident Endpoints ───────────────────────────────────────────────────────

incident_router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


@incident_router.post("")
async def create_incident(
    request: IncidentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Create a new incident (PS10)."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.create_incident(
            title=request.title,
            description=request.description,
            severity=request.severity,
            affected_services=request.affected_services,
            master_ticket_id=request.master_ticket_id,
            created_by=current_user.id,
        )
        
        return incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@incident_router.get("")
async def list_incidents(
    include_resolved: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """List active incidents."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    incidents = incident_service.get_active_incidents(include_resolved)
    
    return {
        "incidents": incidents,
        "banner": incident_service.get_incident_banner(),
        "statistics": incident_service.get_incident_statistics(),
    }


@incident_router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get incident by ID."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.get_incident(incident_id)
        
        # Get linked tickets
        linked_tickets = incident_service.get_linked_tickets(incident_id)
        
        return {
            **incident,
            "linked_tickets": [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "status": t.status,
                }
                for t in linked_tickets
            ],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@incident_router.put("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: IncidentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Update incident status."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.update_incident_status(
            incident_id=incident_id,
            new_status=request.status,
            message=request.message,
            updated_by=current_user.id,
        )
        
        return incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@incident_router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: IncidentResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Resolve an incident."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.resolve_incident(
            incident_id=incident_id,
            resolution_summary=request.resolution_summary,
            resolved_by=current_user.id,
        )
        
        return incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@incident_router.post("/{incident_id}/notify")
async def notify_incident_customers(
    incident_id: str,
    request: IncidentNotifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Notify affected customers about incident."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        result = incident_service.notify_affected_customers(
            incident_id=incident_id,
            message=request.message,
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@incident_router.post("/{incident_id}/link-ticket")
async def link_ticket_to_incident(
    incident_id: str,
    request: LinkTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Link a ticket to an incident."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.link_ticket(
            incident_id=incident_id,
            ticket_id=request.ticket_id,
        )
        
        return incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@incident_router.post("/{incident_id}/affected-customers")
async def add_affected_customers(
    incident_id: str,
    request: AddAffectedCustomersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Add affected customers to incident."""
    incident_service = IncidentService(db, tenant["company_id"])
    
    try:
        incident = incident_service.add_affected_customers(
            incident_id=incident_id,
            customer_ids=request.customer_ids,
        )
        
        return incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ── Spam Queue Endpoints ─────────────────────────────────────────────────────

spam_router = APIRouter(
    prefix="/spam",
    tags=["Spam Moderation"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


@spam_router.get("/queue")
async def get_spam_queue(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get spam queue for moderation."""
    spam_service = SpamDetectionService(db, tenant["company_id"])
    
    tickets, total = spam_service.get_spam_queue(limit, offset)
    
    return {
        "tickets": [
            {
                "id": t.id,
                "subject": t.subject,
                "spam_score": t.spam_score,
                "is_spam": t.is_spam,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
        "total": total,
        "statistics": spam_service.get_spam_statistics(),
    }


@spam_router.post("/analyze")
async def analyze_ticket_for_spam(
    subject: str = Query(...),
    content: str = Query(...),
    customer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Analyze content for spam indicators."""
    spam_service = SpamDetectionService(db, tenant["company_id"])
    
    result = spam_service.analyze_ticket(
        subject=subject,
        content=content,
        customer_id=customer_id,
    )
    
    return result


# Include sub-routers
router.include_router(incident_router)
router.include_router(spam_router)
