"""
PARWA Ticket Notes API - Internal Note Endpoints (Day 27)

Implements internal note endpoints for ticket collaboration.

Endpoints:
- POST   /api/v1/tickets/:id/notes          — Create internal note
- GET    /api/v1/tickets/:id/notes          — List notes
- PUT    /api/v1/tickets/:id/notes/:nid     — Edit note
- DELETE /api/v1/tickets/:id/notes/:nid     — Delete note
- PATCH  /api/v1/tickets/:id/notes/:nid/pin — Pin/unpin note
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_company_id, require_roles
from app.services.internal_note_service import InternalNoteService
from app.exceptions import NotFoundError, ValidationError, AuthorizationError
from app.core.event_emitter import emit_event


router = APIRouter(
    prefix="/tickets",
    tags=["tickets", "notes"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


# ── Request/Response Schemas ───────────────────────────────────────────────

class NoteCreate(BaseModel):
    """Create note request."""
    content: str = Field(..., min_length=1, max_length=50000)
    is_pinned: bool = Field(default=False)


class NoteUpdate(BaseModel):
    """Update note request."""
    content: Optional[str] = Field(None, min_length=1, max_length=50000)


class NoteResponse(BaseModel):
    """Note response."""
    id: str
    ticket_id: str
    author_id: str
    content: str
    is_pinned: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NoteListResponse(BaseModel):
    """Paginated note list response."""
    notes: List[NoteResponse]
    total: int
    page: int
    page_size: int


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/notes",
    response_model=NoteResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_note(
    ticket_id: str,
    request: NoteCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Create an internal note on a ticket.

    Internal notes are only visible to agents, not to customers.
    They can be pinned for visibility.
    """
    service = InternalNoteService(db, company_id)

    try:
        note = service.create_note(
            ticket_id=ticket_id,
            author_id=current_user.get("id"),
            content=request.content,
            is_pinned=request.is_pinned,
        )

        # Emit event for real-time updates
        await emit_event(
            event_type="ticket:note_added",
            company_id=company_id,
            data={
                "ticket_id": ticket_id,
                "note_id": note.id,
                "author_id": note.author_id,
            },
        )

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticket_id}/notes", response_model=NoteListResponse)
async def list_notes(
    ticket_id: str,
    pinned_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    order: str = Query(default="desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """List internal notes for a ticket.

    Returns notes with pinned notes appearing first.
    Use pinned_only=True to get only pinned notes.
    """
    service = InternalNoteService(db, company_id)

    try:
        notes, total = service.list_notes(
            ticket_id=ticket_id,
            pinned_only=pinned_only,
            page=page,
            page_size=page_size,
            order=order,
        )

        return NoteListResponse(
            notes=[
                NoteResponse(
                    id=n.id,
                    ticket_id=n.ticket_id,
                    author_id=n.author_id,
                    content=n.content,
                    is_pinned=n.is_pinned,
                    created_at=n.created_at,
                )
                for n in notes
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    ticket_id: str,
    note_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get a single internal note by ID."""
    service = InternalNoteService(db, company_id)

    try:
        note = service.get_note(ticket_id, note_id)

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{ticket_id}/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    ticket_id: str,
    note_id: str,
    request: NoteUpdate,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Edit an internal note.

    Only the author can edit their own notes.
    Admins can use force=True to bypass this check.
    """
    service = InternalNoteService(db, company_id)

    try:
        note = service.update_note(
            ticket_id=ticket_id,
            note_id=note_id,
            content=request.content,
            user_id=current_user.get("id"),
            force=force,
        )

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{ticket_id}/notes/{note_id}",
               status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_note(
    ticket_id: str,
    note_id: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Delete an internal note.

    Only the author can delete their own notes.
    Admins can use force=True to bypass this check.
    """
    service = InternalNoteService(db, company_id)

    try:
        service.delete_note(
            ticket_id=ticket_id,
            note_id=note_id,
            user_id=current_user.get("id"),
            force=force,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/{ticket_id}/notes/{note_id}/pin", response_model=NoteResponse)
async def toggle_pin_note(
    ticket_id: str,
    note_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Toggle pin status of an internal note.

    Pinned notes appear at the top of the notes list.
    Maximum 5 pinned notes per ticket.
    """
    service = InternalNoteService(db, company_id)

    try:
        note = service.toggle_pin(
            ticket_id=ticket_id,
            note_id=note_id,
            user_id=current_user.get("id"),
        )

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/notes/{note_id}/pin", response_model=NoteResponse)
async def pin_note(
    ticket_id: str,
    note_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Pin an internal note."""
    service = InternalNoteService(db, company_id)

    try:
        note = service.pin_note(
            ticket_id=ticket_id,
            note_id=note_id,
            user_id=current_user.get("id"),
        )

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{ticket_id}/notes/{note_id}/pin", response_model=NoteResponse)
async def unpin_note(
    ticket_id: str,
    note_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Unpin an internal note."""
    service = InternalNoteService(db, company_id)

    try:
        note = service.unpin_note(
            ticket_id=ticket_id,
            note_id=note_id,
            user_id=current_user.get("id"),
        )

        return NoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_at=note.created_at,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
