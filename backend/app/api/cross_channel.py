"""
PARWA Cross-Channel API — Phase 8 Endpoints

Exposes the CrossChannelService via FastAPI endpoints:
- POST /cross-channel/resolve — Resolve customer from any channel
- GET /cross-channel/thread/{customer_id} — Unified conversation thread
- GET /cross-channel/context/{customer_id} — AI context across channels
- GET /cross-channel/related/{customer_id} — Find related tickets

BC-001: All endpoints are tenant-scoped via auth middleware.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from database.models.core import User
from app.services.cross_channel_service import CrossChannelService


router = APIRouter(prefix="/cross-channel", tags=["cross-channel"])


# ── REQUEST MODELS ────────────────────────────────────────────────────────


class ChannelResolveRequest(BaseModel):
    """Request to resolve a customer from a channel identifier."""
    channel_type: str = Field(
        ...,
        description="Channel type: email, chat, sms, voice, whatsapp, etc."
    )
    identifier: str = Field(
        ...,
        description="Customer identifier on that channel (email, phone, handle)"
    )
    channel_data: Optional[dict] = Field(
        None,
        description="Optional metadata about the channel interaction"
    )
    auto_create: bool = Field(
        True,
        description="Create new customer if no match found"
    )


# ── ENDPOINTS ─────────────────────────────────────────────────────────────


@router.post(
    "/resolve",
    summary="Resolve customer identity from channel",
)
async def resolve_from_channel(
    data: ChannelResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Resolve customer identity from a channel-specific identifier.

    When a new message comes in from any channel (email, chat, SMS, voice),
    use this endpoint to identify the customer across all channels.

    If the customer has previously contacted from a different channel,
    this will match them and return the unified identity.
    """
    company_id = current_user.company_id
    service = CrossChannelService(db, company_id)

    try:
        result = service.resolve_from_channel(
            channel_type=data.channel_type,
            identifier=data.identifier,
            channel_data=data.channel_data,
            auto_create=data.auto_create,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "IDENTITY_RESOLUTION_FAILED",
                    "message": str(exc)[:200],
                }
            },
        )


@router.get(
    "/thread/{customer_id}",
    summary="Get unified conversation thread",
)
async def get_unified_thread(
    customer_id: str,
    include_closed: bool = Query(False, description="Include closed tickets"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get a unified conversation thread for a customer across ALL channels.

    Returns all tickets and messages as a single timeline, regardless of
    which channel they came through (email, chat, SMS, voice, social).

    This is the "single customer view" that Phase 8 requires.
    """
    company_id = current_user.company_id
    service = CrossChannelService(db, company_id)

    try:
        return service.get_unified_thread(
            customer_id=customer_id,
            include_closed=include_closed,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CUSTOMER_NOT_FOUND",
                    "message": str(exc)[:200],
                }
            },
        )


@router.get(
    "/context/{customer_id}",
    summary="Get AI context across channels",
)
async def get_cross_channel_context(
    customer_id: str,
    max_recent_messages: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get AI context that carries across channels for a customer.

    This provides the AI with:
    - Customer profile and all linked channels
    - Recent conversation history across ALL channels
    - Active issues/topics from other channels
    - Customer sentiment and interaction patterns

    This context gets injected into the AI's system prompt when
    handling a new ticket from any channel.
    """
    company_id = current_user.company_id
    service = CrossChannelService(db, company_id)

    try:
        return service.get_cross_channel_context(
            customer_id=customer_id,
            max_recent_messages=max_recent_messages,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CUSTOMER_NOT_FOUND",
                    "message": str(exc)[:200],
                }
            },
        )


@router.get(
    "/related/{customer_id}",
    summary="Find related tickets across channels",
)
async def find_related_tickets(
    customer_id: str,
    subject: Optional[str] = Query(None, description="Match subject"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Find tickets from other channels that might be related.

    When a new ticket comes in on one channel, use this to find
    existing tickets on other channels about the same issue.
    """
    company_id = current_user.company_id
    service = CrossChannelService(db, company_id)

    try:
        return {
            "related_tickets": service.find_related_tickets(
                customer_id=customer_id,
                subject=subject,
            )
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CUSTOMER_NOT_FOUND",
                    "message": str(exc)[:200],
                }
            },
        )
