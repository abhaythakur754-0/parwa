"""
PARWA Phase 5 — Tickets API

Endpoints for ticket management in the Command Center:
- List tickets with filtering and pagination
- Get ticket details with AI action trail
- View ticket conversation/messages
- Ticket statistics for dashboard

CRITICAL RULES:
- BC-001: company_id from JWT/header
- BC-008: Never crash
- All tickets scoped to company_id
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_company_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TicketMessage(BaseModel):
    id: str
    sender: str = Field(..., description="customer | ai | agent | system")
    content: str
    timestamp: str
    channel: str = "email"
    metadata: dict = {}


class AIAction(BaseModel):
    id: str
    action_type: str = Field(..., description="refund, cancel_order, send_email, crm_update, etc.")
    description: str
    status: str = Field(..., description="executed | pending | undone | denied")
    variant: str = "parwa"
    timestamp: str
    can_undo: bool = False
    can_approve: bool = False
    result: Optional[dict] = None


class TicketDetail(BaseModel):
    id: str
    subject: str
    status: str = Field(..., description="open | in_progress | resolved | closed")
    priority: str = Field(..., description="low | normal | high | urgent")
    channel: str = "email"
    customer_id: str = ""
    customer_name: str = ""
    customer_email: str = ""
    variant_tier: str = "parwa"
    created_at: str
    updated_at: str
    message_count: int = 0
    ai_actions: list[AIAction] = []
    sentiment: str = "neutral"
    tags: list[str] = []


class TicketListItem(BaseModel):
    id: str
    subject: str
    status: str
    priority: str
    channel: str
    customer_name: str
    variant_tier: str
    created_at: str
    updated_at: str
    ai_action_count: int = 0
    sentiment: str = "neutral"


class TicketListResponse(BaseModel):
    tickets: list[TicketListItem]
    total: int
    page: int
    per_page: int


class TicketStatsResponse(BaseModel):
    total_tickets: int = 0
    open_tickets: int = 0
    in_progress: int = 0
    resolved: int = 0
    by_channel: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    avg_resolution_hours: float = 0.0
    ai_actions_today: int = 0
    pending_approvals: int = 0


# ---------------------------------------------------------------------------
# In-memory ticket data (production would use DB)
# ---------------------------------------------------------------------------

_company_tickets: dict[str, list[dict]] = {}


def _seed_tickets(company_id: str) -> list[dict]:
    """Seed sample tickets for a company."""
    if company_id in _company_tickets:
        return _company_tickets[company_id]

    now = datetime.now(timezone.utc).isoformat()
    tickets = [
        {
            "id": "tkt-501",
            "subject": "Refund request for order #ORD-4521",
            "status": "in_progress",
            "priority": "high",
            "channel": "email",
            "customer_id": "cust-101",
            "customer_name": "Alice Johnson",
            "customer_email": "alice@example.com",
            "variant_tier": "parwa",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-1", "sender": "customer", "content": "I want a refund for order #ORD-4521. The product was defective.", "timestamp": now, "channel": "email", "metadata": {}},
                {"id": "msg-2", "sender": "ai", "content": "I've found your order #ORD-4521 for $29.99. I can process a refund for you right away.", "timestamp": now, "channel": "email", "metadata": {}},
                {"id": "msg-3", "sender": "ai", "content": "Refund of $29.99 has been processed. You should see it in 3-5 business days.", "timestamp": now, "channel": "email", "metadata": {}},
            ],
            "ai_actions": [
                {"id": "act-501", "action_type": "refund", "description": "Refunded $29.99 for order #ORD-4521", "status": "executed", "variant": "parwa", "timestamp": now, "can_undo": True, "can_approve": False, "result": {"refund_id": "ref-001", "amount": 29.99}},
                {"id": "act-502", "action_type": "send_email", "description": "Sent refund confirmation to alice@example.com", "status": "executed", "variant": "parwa", "timestamp": now, "can_undo": True, "can_approve": False},
            ],
            "sentiment": "frustrated",
            "tags": ["refund", "defective-product"],
        },
        {
            "id": "tkt-502",
            "subject": "Order tracking request",
            "status": "resolved",
            "priority": "normal",
            "channel": "chat",
            "customer_id": "cust-102",
            "customer_name": "Bob Smith",
            "customer_email": "bob@example.com",
            "variant_tier": "parwa",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-4", "sender": "customer", "content": "Where is my order? It's been 5 days.", "timestamp": now, "channel": "chat", "metadata": {}},
                {"id": "msg-5", "sender": "ai", "content": "Let me look up your order. I found order #ORD-3890 — it's currently in transit with tracking number TRK-123456789. Expected delivery: tomorrow.", "timestamp": now, "channel": "chat", "metadata": {}},
            ],
            "ai_actions": [
                {"id": "act-503", "action_type": "lookup_order", "description": "Looked up order #ORD-3890 status", "status": "executed", "variant": "parwa", "timestamp": now, "can_undo": False, "can_approve": False},
            ],
            "sentiment": "neutral",
            "tags": ["order-tracking"],
        },
        {
            "id": "tkt-503",
            "subject": "Subscription cancellation request",
            "status": "open",
            "priority": "high",
            "channel": "email",
            "customer_id": "cust-103",
            "customer_name": "Carol Davis",
            "customer_email": "carol@example.com",
            "variant_tier": "mini",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-6", "sender": "customer", "content": "I want to cancel my subscription immediately.", "timestamp": now, "channel": "email", "metadata": {}},
            ],
            "ai_actions": [
                {"id": "act-504", "action_type": "cancel_subscription", "description": "Cancel subscription recommended for cust-103", "status": "pending", "variant": "mini", "timestamp": now, "can_undo": False, "can_approve": True},
            ],
            "sentiment": "angry",
            "tags": ["cancellation", "subscription"],
        },
        {
            "id": "tkt-504",
            "subject": "CRM update needed",
            "status": "resolved",
            "priority": "low",
            "channel": "webhook",
            "customer_id": "cust-104",
            "customer_name": "Dan Wilson",
            "customer_email": "dan@example.com",
            "variant_tier": "high",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-7", "sender": "system", "content": "Shopify order created for Dan Wilson — order #ORD-5500", "timestamp": now, "channel": "webhook", "metadata": {"provider": "shopify", "event": "order.created"}},
            ],
            "ai_actions": [
                {"id": "act-505", "action_type": "crm_update", "description": "Updated CRM contact: Dan Wilson (HubSpot)", "status": "executed", "variant": "high", "timestamp": now, "can_undo": True, "can_approve": False},
            ],
            "sentiment": "neutral",
            "tags": ["crm", "shopify"],
        },
        {
            "id": "tkt-505",
            "subject": "Voice call — delivery delay complaint",
            "status": "closed",
            "priority": "urgent",
            "channel": "voice",
            "customer_id": "cust-106",
            "customer_name": "Frank Lee",
            "customer_email": "frank@example.com",
            "variant_tier": "high",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-8", "sender": "customer", "content": "[Voice transcript] My delivery is 3 days late and I'm very frustrated.", "timestamp": now, "channel": "voice", "metadata": {"call_sid": "CA-test-001", "duration": 272}},
                {"id": "msg-9", "sender": "ai", "content": "I'm sorry about the delay. Let me check the status and arrange expedited shipping.", "timestamp": now, "channel": "voice", "metadata": {}},
            ],
            "ai_actions": [
                {"id": "act-506", "action_type": "voice_call", "description": "Voice call with customer regarding delivery delay", "status": "executed", "variant": "high", "timestamp": now, "can_undo": False, "can_approve": False},
                {"id": "act-507", "action_type": "update_shipping", "description": "Updated shipping to expedited for order #ORD-7723", "status": "executed", "variant": "high", "timestamp": now, "can_undo": True, "can_approve": False},
            ],
            "sentiment": "angry",
            "tags": ["voice", "delivery", "escalated"],
        },
        {
            "id": "tkt-506",
            "subject": "How do I change my plan?",
            "status": "open",
            "priority": "normal",
            "channel": "chat",
            "customer_id": "cust-107",
            "customer_name": "Grace Kim",
            "customer_email": "grace@example.com",
            "variant_tier": "parwa",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"id": "msg-10", "sender": "customer", "content": "How do I upgrade from PARWA Standard to PARWA High?", "timestamp": now, "channel": "chat", "metadata": {}},
            ],
            "ai_actions": [],
            "sentiment": "neutral",
            "tags": ["plan-change"],
        },
    ]

    _company_tickets[company_id] = tickets
    return tickets


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=TicketStatsResponse)
def get_ticket_stats(
    company_id: str = Depends(get_current_company_id),
):
    """Get ticket statistics for the dashboard."""
    try:
        tickets = _seed_tickets(company_id)

        by_channel: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for t in tickets:
            ch = t.get("channel", "unknown")
            by_channel[ch] = by_channel.get(ch, 0) + 1
            pr = t.get("priority", "normal")
            by_priority[pr] = by_priority.get(pr, 0) + 1

        return TicketStatsResponse(
            total_tickets=len(tickets),
            open_tickets=sum(1 for t in tickets if t["status"] == "open"),
            in_progress=sum(1 for t in tickets if t["status"] == "in_progress"),
            resolved=sum(1 for t in tickets if t["status"] in ("resolved", "closed")),
            by_channel=by_channel,
            by_priority=by_priority,
            avg_resolution_hours=4.2,
            ai_actions_today=sum(len(t.get("ai_actions", [])) for t in tickets),
            pending_approvals=sum(
                1 for t in tickets
                for a in t.get("ai_actions", [])
                if a["status"] == "pending"
            ),
        )
    except Exception as exc:
        logger.error("get_ticket_stats failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get stats") from exc


@router.get("/", response_model=TicketListResponse)
def list_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    channel: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    company_id: str = Depends(get_current_company_id),
):
    """List tickets with filtering and pagination."""
    try:
        tickets = _seed_tickets(company_id)

        # Apply filters
        filtered = tickets
        if status_filter:
            filtered = [t for t in filtered if t["status"] == status_filter]
        if channel:
            filtered = [t for t in filtered if t["channel"] == channel]
        if priority:
            filtered = [t for t in filtered if t["priority"] == priority]
        if search:
            search_lower = search.lower()
            filtered = [
                t for t in filtered
                if search_lower in t["subject"].lower()
                or search_lower in t["customer_name"].lower()
            ]

        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page

        items = [
            TicketListItem(
                id=t["id"],
                subject=t["subject"],
                status=t["status"],
                priority=t["priority"],
                channel=t["channel"],
                customer_name=t["customer_name"],
                variant_tier=t["variant_tier"],
                created_at=t["created_at"],
                updated_at=t["updated_at"],
                ai_action_count=len(t.get("ai_actions", [])),
                sentiment=t.get("sentiment", "neutral"),
            )
            for t in filtered[start:end]
        ]

        return TicketListResponse(
            tickets=items,
            total=total,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("list_tickets failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list tickets") from exc


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket_detail(
    ticket_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Get ticket details with AI action trail."""
    try:
        tickets = _seed_tickets(company_id)
        ticket = next((t for t in tickets if t["id"] == ticket_id), None)

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return TicketDetail(
            id=ticket["id"],
            subject=ticket["subject"],
            status=ticket["status"],
            priority=ticket["priority"],
            channel=ticket["channel"],
            customer_id=ticket["customer_id"],
            customer_name=ticket["customer_name"],
            customer_email=ticket["customer_email"],
            variant_tier=ticket["variant_tier"],
            created_at=ticket["created_at"],
            updated_at=ticket["updated_at"],
            message_count=len(ticket.get("messages", [])),
            ai_actions=[
                AIAction(
                    id=a["id"],
                    action_type=a["action_type"],
                    description=a["description"],
                    status=a["status"],
                    variant=a.get("variant", "parwa"),
                    timestamp=a["timestamp"],
                    can_undo=a.get("can_undo", False),
                    can_approve=a.get("can_approve", False),
                    result=a.get("result"),
                )
                for a in ticket.get("ai_actions", [])
            ],
            sentiment=ticket.get("sentiment", "neutral"),
            tags=ticket.get("tags", []),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_ticket_detail failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get ticket") from exc


@router.get("/{ticket_id}/messages", response_model=list[TicketMessage])
def get_ticket_messages(
    ticket_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Get messages for a ticket."""
    try:
        tickets = _seed_tickets(company_id)
        ticket = next((t for t in tickets if t["id"] == ticket_id), None)

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return [
            TicketMessage(
                id=m["id"],
                sender=m["sender"],
                content=m["content"],
                timestamp=m["timestamp"],
                channel=m.get("channel", "email"),
                metadata=m.get("metadata", {}),
            )
            for m in ticket.get("messages", [])
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_ticket_messages failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get messages") from exc
