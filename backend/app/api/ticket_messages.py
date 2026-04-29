"""
PARWA Ticket Messages API - Message Endpoints (Day 27)

Implements F-047: Message/Conversation endpoints

Endpoints:
- POST   /api/v1/tickets/:id/messages       — Add message
- GET    /api/v1/tickets/:id/messages       — List messages
- GET    /api/v1/tickets/:id/messages/:mid  — Get single message
- PUT    /api/v1/tickets/:id/messages/:mid  — Edit message
- DELETE /api/v1/tickets/:id/messages/:mid  — Delete message
- POST   /api/v1/tickets/:id/messages/:mid/redact — Redact message
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.api.deps import get_company_id, get_current_user, get_db, require_roles
from app.core.event_emitter import emit_event
from app.exceptions import NotFoundError, ValidationError
from app.services.message_service import MessageService
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/tickets",
    tags=["tickets", "messages"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


# ── Request/Response Schemas ───────────────────────────────────────────────


class AttachmentSchema(BaseModel):
    """Attachment metadata."""

    filename: str
    file_url: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class MessageCreate(BaseModel):
    """Create message request."""

    role: str = Field(..., description="Message role: customer, agent, system, ai")
    content: str = Field(..., min_length=1, max_length=100000)
    channel: str = Field(..., description="Communication channel")
    is_internal: bool = Field(default=False)
    metadata_json: Optional[Dict[str, Any]] = None
    attachments: Optional[List[AttachmentSchema]] = None
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    variant_version: Optional[str] = None


class MessageUpdate(BaseModel):
    """Update message request."""

    content: Optional[str] = Field(None, min_length=1, max_length=100000)
    metadata_json: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Message response."""

    id: str
    ticket_id: str
    role: str
    content: str
    channel: str
    is_internal: bool
    is_redacted: bool
    ai_confidence: Optional[float]
    variant_version: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Paginated message list response."""

    messages: List[MessageResponse]
    total: int
    page: int
    page_size: int


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post(
    "/{ticket_id}/messages",
    response_model=MessageResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_message(
    ticket_id: str,
    request: MessageCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Add a message to a ticket.

    Creates a new message on the ticket. Messages are displayed in the
    ticket conversation thread.
    """
    service = MessageService(db, company_id)

    try:
        message = service.create_message(
            ticket_id=ticket_id,
            role=request.role,
            content=request.content,
            channel=request.channel,
            is_internal=request.is_internal,
            metadata_json=request.metadata_json,
            attachments=(
                [a.model_dump() for a in request.attachments]
                if request.attachments
                else None
            ),
            user_id=current_user.get("id"),
            ai_confidence=request.ai_confidence,
            variant_version=request.variant_version,
        )

        # Emit event for real-time updates
        await emit_event(
            event_type="ticket:message_added",
            company_id=company_id,
            data={
                "ticket_id": ticket_id,
                "message_id": message.id,
                "role": message.role,
            },
        )

        return MessageResponse(
            id=message.id,
            ticket_id=message.ticket_id,
            role=message.role,
            content=message.content,
            channel=message.channel,
            is_internal=message.is_internal,
            is_redacted=message.is_redacted,
            ai_confidence=(
                float(message.ai_confidence) if message.ai_confidence else None
            ),
            variant_version=message.variant_version,
            created_at=message.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticket_id}/messages", response_model=MessageListResponse)
async def list_messages(
    ticket_id: str,
    include_internal: bool = Query(default=False),
    role: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    order: str = Query(default="asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """List messages for a ticket.

    Returns paginated messages in chronological order by default.
    Internal notes are excluded unless include_internal=True.
    """
    service = MessageService(db, company_id)

    try:
        messages, total = service.list_messages(
            ticket_id=ticket_id,
            include_internal=include_internal,
            role=role,
            page=page,
            page_size=page_size,
            order=order,
        )

        return MessageListResponse(
            messages=[
                MessageResponse(
                    id=m.id,
                    ticket_id=m.ticket_id,
                    role=m.role,
                    content=m.content,
                    channel=m.channel,
                    is_internal=m.is_internal,
                    is_redacted=m.is_redacted,
                    ai_confidence=float(m.ai_confidence) if m.ai_confidence else None,
                    variant_version=m.variant_version,
                    created_at=m.created_at,
                )
                for m in messages
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    ticket_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get a single message by ID."""
    service = MessageService(db, company_id)

    try:
        message = service.get_message(ticket_id, message_id)

        return MessageResponse(
            id=message.id,
            ticket_id=message.ticket_id,
            role=message.role,
            content=message.content,
            channel=message.channel,
            is_internal=message.is_internal,
            is_redacted=message.is_redacted,
            ai_confidence=(
                float(message.ai_confidence) if message.ai_confidence else None
            ),
            variant_version=message.variant_version,
            created_at=message.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{ticket_id}/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    ticket_id: str,
    message_id: str,
    request: MessageUpdate,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Edit a message.

    Messages can only be edited within 5 minutes of creation.
    Only the author can edit (enforced at API level).
    Admins can use force=True to bypass the edit window.
    """
    service = MessageService(db, company_id)

    try:
        message = service.update_message(
            ticket_id=ticket_id,
            message_id=message_id,
            content=request.content,
            metadata_json=request.metadata_json,
            user_id=current_user.get("id"),
            force=force,
        )

        return MessageResponse(
            id=message.id,
            ticket_id=message.ticket_id,
            role=message.role,
            content=message.content,
            channel=message.channel,
            is_internal=message.is_internal,
            is_redacted=message.is_redacted,
            ai_confidence=(
                float(message.ai_confidence) if message.ai_confidence else None
            ),
            variant_version=message.variant_version,
            created_at=message.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{ticket_id}/messages/{message_id}", status_code=http_status.HTTP_204_NO_CONTENT
)
async def delete_message(
    ticket_id: str,
    message_id: str,
    hard: bool = Query(default=False),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Delete a message.

    By default, performs soft delete (replaces content with "[DELETED]").
    Use hard=True for permanent deletion (GDPR).
    """
    service = MessageService(db, company_id)

    try:
        service.delete_message(
            ticket_id=ticket_id,
            message_id=message_id,
            user_id=current_user.get("id"),
            hard=hard,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{ticket_id}/messages/{message_id}/redact", response_model=MessageResponse
)
async def redact_message(
    ticket_id: str,
    message_id: str,
    reason: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Redact a message (GDPR/PS12).

    Replaces content with "[REDACTED]" and marks as redacted.
    This is irreversible.
    """
    service = MessageService(db, company_id)

    try:
        message = service.redact_message(
            ticket_id=ticket_id,
            message_id=message_id,
            reason=reason,
            user_id=current_user.get("id"),
        )

        return MessageResponse(
            id=message.id,
            ticket_id=message.ticket_id,
            role=message.role,
            content=message.content,
            channel=message.channel,
            is_internal=message.is_internal,
            is_redacted=message.is_redacted,
            ai_confidence=(
                float(message.ai_confidence) if message.ai_confidence else None
            ),
            variant_version=message.variant_version,
            created_at=message.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/attachments", response_model=List[AttachmentSchema])
async def list_attachments(
    ticket_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """List all attachments for a ticket."""
    service = MessageService(db, company_id)

    try:
        attachments = service.get_attachments(ticket_id)

        return [
            AttachmentSchema(
                filename=a.filename,
                file_url=a.file_url,
                file_size=a.file_size,
                mime_type=a.mime_type,
            )
            for a in attachments
        ]

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
