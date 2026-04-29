"""
PARWA ReAct Tool — Ticket System  (F-157)

Exposes ticket/support-related actions to the ReAct agent:
- get_ticket          Fetch full details for a single ticket
- create_ticket       Create a new support ticket
- update_ticket       Update ticket status, priority, or assignee
- add_comment         Add a comment to a ticket thread
- list_tickets        List/search tickets with filtering
- get_ticket_history  Get the full audit trail for a ticket

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008).
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Mock data factories ────────────────────────────────────────────

_TICKET_STATUSES = ["open", "in_progress", "pending_customer", "resolved", "closed"]
_PRIORITIES = ["low", "medium", "high", "urgent"]
_CATEGORIES = [
    "billing",
    "technical",
    "account",
    "feature_request",
    "bug_report",
    "general",
]
_SUBJECTS = [
    "Cannot access my account",
    "Billing charge discrepancy",
    "Feature request: dark mode",
    "Integration not working with Salesforce",
    "How to export data",
    "Subscription upgrade question",
    "API rate limit error",
    "Dashboard loading slowly",
    "Need help with webhooks",
    "Password reset not working",
    "Two-factor authentication issue",
    "Custom domain setup",
    "Report generation timeout",
    "Missing data in analytics",
    "Team member permissions issue",
]


def _mock_ticket(
    ticket_id: str | None = None,
    company_id: str = "",
    status: str = "open",
    customer_id: str | None = None,
    subject: str | None = None,
) -> dict[str, Any]:
    """Generate a realistic mock support ticket."""
    tid = ticket_id or f"TKT-{uuid.uuid4().hex[:8].upper()}"
    cid = customer_id or f"CUST-{uuid.uuid4().hex[:6].upper()}"
    created = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 60),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    updated = created + timedelta(minutes=random.randint(5, 1440))

    return {
        "ticket_id": tid,
        "company_id": company_id,
        "customer_id": cid,
        "subject": subject or random.choice(_SUBJECTS),
        "description": "Customer reported an issue with their account. "
        "Needs investigation by the support team.",
        "status": status,
        "priority": random.choice(_PRIORITIES),
        "category": random.choice(_CATEGORIES),
        "assignee_id": (
            f"AGENT-{random.randint(1, 20):03d}" if status != "open" else None
        ),
        "assignee_name": (
            f"Agent {random.randint(1, 20)}" if status != "open" else None
        ),
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
        "resolved_at": (
            updated.isoformat() if status in ("resolved", "closed") else None
        ),
        "first_response_at": (
            (created + timedelta(minutes=random.randint(1, 60))).isoformat()
            if status in ("resolved", "closed", "in_progress")
            else None
        ),
        "satisfaction_rating": (
            random.randint(1, 5) if status in ("resolved", "closed") else None
        ),
        "tags": random.sample(
            ["bug", "urgent", "follow-up", "escalated", "vip", "recurring"],
            k=random.randint(0, 2),
        ),
    }


def _mock_comment(
    ticket_id: str,
    company_id: str,
    customer_id: str | None = None,
    is_agent: bool = True,
) -> dict[str, Any]:
    """Generate a mock comment on a ticket."""
    agent_responses = [
        "Thank you for reaching out. I'm looking into this now.",
        "I've investigated the issue and found the root cause. Here's what happened...",
        "Could you please provide more details about the steps you followed?",
        "I've escalated this to our engineering team for further investigation.",
        "This should now be resolved. Please confirm if you're still experiencing the issue.",
        "I've applied the fix. The changes should take effect within a few minutes.",
        "Let me check the logs for any related errors.",
    ]
    customer_comments = [
        "This is still not working. I've tried clearing my cache.",
        "Thanks, that fixed it!",
        "When can I expect a resolution?",
        "I'm still seeing the same error.",
        "Can you provide a workaround in the meantime?",
    ]

    ts = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 14),
        hours=random.randint(0, 23),
    )

    return {
        "comment_id": f"CMT-{uuid.uuid4().hex[:8].upper()}",
        "ticket_id": ticket_id,
        "company_id": company_id,
        "author_type": "agent" if is_agent else "customer",
        "author_id": (
            f"AGENT-{random.randint(1, 20):03d}"
            if is_agent
            else (customer_id or "unknown")
        ),
        "content": random.choice(agent_responses if is_agent else customer_comments),
        # Some agent comments are internal
        "internal": is_agent and random.random() > 0.7,
        "created_at": ts.isoformat(),
    }


def _mock_history_entry(
    ticket_id: str,
    field: str | None = None,
) -> dict[str, Any]:
    """Generate a mock ticket history / audit log entry."""
    fields = field or random.choice(["status", "priority", "assignee", "category"])
    transitions = {
        "status": (["open", "in_progress", "pending_customer", "resolved", "closed"]),
        "priority": (["low", "medium", "high", "urgent"]),
        "assignee": [f"AGENT-{i:03d}" for i in range(1, 21)],
        "category": _CATEGORIES,
    }
    options = transitions.get(fields, ["value_a", "value_b"])
    ts = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
    )

    return {
        "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
        "ticket_id": ticket_id,
        "field": fields,
        "old_value": random.choice(options) if fields != "status" else "open",
        "new_value": random.choice(options),
        "changed_by": f"AGENT-{random.randint(1, 20):03d}",
        "created_at": ts.isoformat(),
    }


# ── Tool Implementation ────────────────────────────────────────────


class TicketTool(BaseReactTool):
    """ReAct tool for Ticket System integration."""

    def __init__(self) -> None:
        self._tickets: dict[str, dict[str, Any]] = {}
        self._comments: dict[str, list[dict[str, Any]]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "ticket_system"

    @property
    def description(self) -> str:
        return (
            "Create tickets, update status, add comments, assign tickets, "
            "get ticket details, and view ticket history"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "get_ticket",
            "create_ticket",
            "update_ticket",
            "add_comment",
            "list_tickets",
            "get_ticket_history",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="get_ticket",
                    description="Fetch full details for a single ticket by ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "ticket_id": {
                                "type": "string",
                                "description": "Unique ticket identifier",
                            },
                        },
                        "required": ["ticket_id"],
                    },
                    required_params=["ticket_id"],
                    returns="Full ticket object with status, priority, assignee, and timestamps",
                ),
                ActionSchema(
                    name="create_ticket",
                    description="Create a new support ticket",
                    parameters={
                        "type": "object",
                        "properties": {
                            "subject": {
                                "type": "string",
                                "description": "Ticket subject / title",
                            },
                            "description": {
                                "type": "string",
                                "description": "Detailed issue description",
                            },
                            "customer_id": {
                                "type": "string",
                                "description": "Customer who opened the ticket",
                            },
                            "priority": {
                                "type": "string",
                                "description": "Priority: low, medium, high, urgent",
                            },
                            "category": {
                                "type": "string",
                                "description": "Category: billing, technical, account, feature_request, bug_report, general",
                            },
                            "tags": {
                                "type": "string",
                                "description": "Comma-separated tags",
                            },
                        },
                        "required": ["subject", "description"],
                    },
                    required_params=["subject", "description"],
                    returns="Created ticket object with ticket_id and timestamps",
                ),
                ActionSchema(
                    name="update_ticket",
                    description="Update ticket status, priority, assignee, or category",
                    parameters={
                        "type": "object",
                        "properties": {
                            "ticket_id": {
                                "type": "string",
                                "description": "Ticket to update",
                            },
                            "status": {
                                "type": "string",
                                "description": "New status: open, in_progress, pending_customer, resolved, closed",
                            },
                            "priority": {
                                "type": "string",
                                "description": "New priority: low, medium, high, urgent",
                            },
                            "assignee_id": {
                                "type": "string",
                                "description": "New assignee agent ID",
                            },
                            "category": {
                                "type": "string",
                                "description": "New category",
                            },
                        },
                        "required": ["ticket_id"],
                    },
                    required_params=["ticket_id"],
                    returns="Updated ticket object with changed fields",
                ),
                ActionSchema(
                    name="add_comment",
                    description="Add a comment to a ticket thread",
                    parameters={
                        "type": "object",
                        "properties": {
                            "ticket_id": {
                                "type": "string",
                                "description": "Ticket to comment on",
                            },
                            "content": {
                                "type": "string",
                                "description": "Comment content",
                            },
                            "author_id": {
                                "type": "string",
                                "description": "Author ID (agent or customer)",
                            },
                            "author_type": {
                                "type": "string",
                                "description": "agent or customer",
                            },
                            "internal": {
                                "type": "boolean",
                                "description": "Whether the comment is internal-only",
                            },
                        },
                        "required": ["ticket_id", "content"],
                    },
                    required_params=["ticket_id", "content"],
                    returns="Comment object with comment_id and timestamp",
                ),
                ActionSchema(
                    name="list_tickets",
                    description="List/search tickets with optional filtering",
                    parameters={
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "Filter by status",
                            },
                            "priority": {
                                "type": "string",
                                "description": "Filter by priority",
                            },
                            "assignee_id": {
                                "type": "string",
                                "description": "Filter by assignee",
                            },
                            "customer_id": {
                                "type": "string",
                                "description": "Filter by customer",
                            },
                            "category": {
                                "type": "string",
                                "description": "Filter by category",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max tickets (1-50)",
                                "default": 10,
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of ticket objects with pagination metadata",
                ),
                ActionSchema(
                    name="get_ticket_history",
                    description="Get the full audit trail / change history for a ticket",
                    parameters={
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "Ticket ID"},
                            "limit": {
                                "type": "integer",
                                "description": "Max history entries (1-100)",
                                "default": 20,
                            },
                        },
                        "required": ["ticket_id"],
                    },
                    required_params=["ticket_id"],
                    returns="List of history entries showing field changes and timestamps",
                ),
            ],
        )

    # ── Execution ───────────────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""

        # Simulate API latency
        await asyncio.sleep(random.uniform(0.02, 0.12))

        if action == "__health_check__":
            return ToolResult(
                success=True, error=None, data={"status": "ok"}, execution_time_ms=0
            )

        handler = {
            "get_ticket": self._get_ticket,
            "create_ticket": self._create_ticket,
            "update_ticket": self._update_ticket,
            "add_comment": self._add_comment,
            "list_tickets": self._list_tickets,
            "get_ticket_history": self._get_ticket_history,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {
                    ', '.join(
                        self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _get_ticket(self, company_id: str, **params: Any) -> ToolResult:
        """Fetch full ticket details."""
        ticket_id: str = params.get("ticket_id", "")

        if ticket_id in self._tickets:
            ticket = self._tickets[ticket_id]
            if ticket["company_id"] != company_id:
                return ToolResult(
                    success=False,
                    error=f"Ticket {ticket_id} not found in company scope",
                    data=None,
                    execution_time_ms=0,
                )
            # Include comment count
            ticket_copy = {**ticket}
            ticket_copy["comment_count"] = len(self._comments.get(ticket_id, []))
            return ToolResult(
                success=True, error=None, data=ticket_copy, execution_time_ms=0
            )

        ticket = _mock_ticket(ticket_id=ticket_id, company_id=company_id)
        self._tickets[ticket_id] = ticket
        ticket["comment_count"] = 0
        return ToolResult(success=True, error=None, data=ticket, execution_time_ms=0)

    async def _create_ticket(self, company_id: str, **params: Any) -> ToolResult:
        """Create a new support ticket."""
        subject: str = params.get("subject", "")
        description: str = params.get("description", "")
        customer_id: str | None = params.get("customer_id")
        priority: str | None = params.get("priority")
        category: str | None = params.get("category")
        raw_tags: str | None = params.get("tags")

        if not subject.strip():
            return ToolResult(
                success=False,
                error="Ticket subject is required",
                data=None,
                execution_time_ms=0,
            )

        if not description.strip():
            return ToolResult(
                success=False,
                error="Ticket description is required",
                data=None,
                execution_time_ms=0,
            )

        if priority and priority not in _PRIORITIES:
            return ToolResult(
                success=False,
                error=f"Invalid priority '{priority}'. Must be one of: {
                    ', '.join(_PRIORITIES)}",
                data=None,
                execution_time_ms=0,
            )

        if category and category not in _CATEGORIES:
            return ToolResult(
                success=False,
                error=f"Invalid category '{category}'. Must be one of: {
                    ', '.join(_CATEGORIES)}",
                data=None,
                execution_time_ms=0,
            )

        tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []
        now = datetime.now(timezone.utc).isoformat()

        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        ticket: dict[str, Any] = {
            "ticket_id": ticket_id,
            "company_id": company_id,
            "customer_id": customer_id or f"CUST-{uuid.uuid4().hex[:6].upper()}",
            "subject": subject.strip(),
            "description": description.strip(),
            "status": "open",
            "priority": priority or "medium",
            "category": category or "general",
            "assignee_id": None,
            "assignee_name": None,
            "tags": tags,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "first_response_at": None,
            "satisfaction_rating": None,
        }

        self._tickets[ticket_id] = ticket
        self._comments[ticket_id] = []
        self._history[ticket_id] = [
            {
                "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                "ticket_id": ticket_id,
                "field": "created",
                "old_value": None,
                "new_value": None,
                "changed_by": customer_id or "system",
                "created_at": now,
            }
        ]

        return ToolResult(
            success=True,
            error=None,
            data=ticket,
            execution_time_ms=0,
        )

    async def _update_ticket(self, company_id: str, **params: Any) -> ToolResult:
        """Update ticket fields."""
        ticket_id: str = params.get("ticket_id", "")

        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            ticket = _mock_ticket(ticket_id=ticket_id, company_id=company_id)
            self._tickets[ticket_id] = ticket

        if ticket["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Ticket {ticket_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        updatable: dict[str, tuple[str, list[str]]] = {
            "status": ("status", _TICKET_STATUSES),
            "priority": ("priority", _PRIORITIES),
            "category": ("category", _CATEGORIES),
            "assignee_id": ("assignee_id", []),
        }

        updated_fields: list[str] = []
        now = datetime.now(timezone.utc).isoformat()

        for param_key, (field_name, valid_values) in updatable.items():
            value = params.get(param_key)
            if value is None:
                continue

            if valid_values and value not in valid_values:
                return ToolResult(
                    success=False,
                    error=f"Invalid {param_key} '{value}'. "
                    f"Must be one of: {', '.join(valid_values)}",
                    data=None,
                    execution_time_ms=0,
                )

            old_value = ticket.get(field_name)
            ticket[field_name] = value
            updated_fields.append(param_key)

            # If assignee changed, also set assignee_name
            if param_key == "assignee_id":
                ticket["assignee_name"] = f"Agent {value.split('-')[-1]}"

            # Record in history
            if ticket_id not in self._history:
                self._history[ticket_id] = []
            self._history[ticket_id].append(
                {
                    "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                    "ticket_id": ticket_id,
                    "field": field_name,
                    "old_value": old_value,
                    "new_value": value,
                    "changed_by": params.get("updated_by", "system"),
                    "created_at": now,
                }
            )

        if not updated_fields:
            return ToolResult(
                success=False,
                error="No fields to update. Provide status, priority, assignee_id, or category.",
                data=None,
                execution_time_ms=0,
            )

        # Set resolved_at if status changed to resolved/closed
        if "status" in params and params["status"] in ("resolved", "closed"):
            ticket["resolved_at"] = now

        ticket["updated_at"] = now
        self._tickets[ticket_id] = ticket

        return ToolResult(
            success=True,
            error=None,
            data={
                "ticket_id": ticket_id,
                "updated_fields": updated_fields,
                "ticket": ticket,
            },
            execution_time_ms=0,
        )

    async def _add_comment(self, company_id: str, **params: Any) -> ToolResult:
        """Add a comment to a ticket."""
        ticket_id: str = params.get("ticket_id", "")
        content: str = params.get("content", "")
        author_id: str | None = params.get("author_id")
        author_type: str = params.get("author_type", "agent")
        is_internal: bool = params.get("internal", False)

        if not content.strip():
            return ToolResult(
                success=False,
                error="Comment content cannot be empty",
                data=None,
                execution_time_ms=0,
            )

        if author_type not in ("agent", "customer"):
            return ToolResult(
                success=False,
                error="author_type must be 'agent' or 'customer'",
                data=None,
                execution_time_ms=0,
            )

        # Ensure ticket exists
        if ticket_id not in self._tickets:
            ticket = _mock_ticket(ticket_id=ticket_id, company_id=company_id)
            self._tickets[ticket_id] = ticket

        ticket = self._tickets[ticket_id]
        if ticket["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Ticket {ticket_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        now = datetime.now(timezone.utc).isoformat()
        comment: dict[str, Any] = {
            "comment_id": f"CMT-{uuid.uuid4().hex[:8].upper()}",
            "ticket_id": ticket_id,
            "company_id": company_id,
            "author_type": author_type,
            "author_id": author_id
            or ("system" if author_type == "agent" else "unknown"),
            "content": content.strip(),
            "internal": is_internal,
            "created_at": now,
        }

        if ticket_id not in self._comments:
            self._comments[ticket_id] = []
        self._comments[ticket_id].append(comment)

        # Update ticket timestamp
        ticket["updated_at"] = now
        self._tickets[ticket_id] = ticket

        # Add to history
        if ticket_id not in self._history:
            self._history[ticket_id] = []
        self._history[ticket_id].append(
            {
                "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                "ticket_id": ticket_id,
                "field": "comment_added",
                "old_value": None,
                "new_value": comment["comment_id"],
                "changed_by": author_id or "system",
                "created_at": now,
            }
        )

        return ToolResult(
            success=True,
            error=None,
            data=comment,
            execution_time_ms=0,
        )

    async def _list_tickets(self, company_id: str, **params: Any) -> ToolResult:
        """List tickets with optional filtering."""
        status: str | None = params.get("status")
        priority: str | None = params.get("priority")
        assignee_id: str | None = params.get("assignee_id")
        customer_id: str | None = params.get("customer_id")
        category: str | None = params.get("category")
        limit: int = min(max(params.get("limit", 10), 1), 50)

        count = min(limit, 30)
        tickets: list[dict[str, Any]] = []
        for _ in range(count):
            st = status or random.choice(_TICKET_STATUSES)
            ticket = _mock_ticket(company_id=company_id, status=st)
            tickets.append(ticket)

        # Apply filters
        if priority:
            tickets = [t for t in tickets if t["priority"] == priority]
        if assignee_id:
            tickets = [t for t in tickets if t.get("assignee_id") == assignee_id]
        if customer_id:
            tickets = [t for t in tickets if t.get("customer_id") == customer_id]
        if category:
            tickets = [t for t in tickets if t.get("category") == category]

        # Store for later retrieval
        for t in tickets:
            self._tickets[t["ticket_id"]] = t

        return ToolResult(
            success=True,
            error=None,
            data={
                "tickets": tickets,
                "total": len(tickets),
                "limit": limit,
            },
            execution_time_ms=0,
        )

    async def _get_ticket_history(self, company_id: str, **params: Any) -> ToolResult:
        """Get full audit trail for a ticket."""
        ticket_id: str = params.get("ticket_id", "")
        limit: int = min(max(params.get("limit", 20), 1), 100)

        # Ensure ticket exists
        if ticket_id not in self._tickets:
            ticket = _mock_ticket(ticket_id=ticket_id, company_id=company_id)
            self._tickets[ticket_id] = ticket

        ticket = self._tickets[ticket_id]
        if ticket["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Ticket {ticket_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        # Return existing history or generate mock
        if ticket_id in self._history and self._history[ticket_id]:
            history = self._history[ticket_id]
        else:
            history = []
            for _ in range(min(limit, 10)):
                history.append(_mock_history_entry(ticket_id))
            # Sort newest first
            history.sort(key=lambda h: h["created_at"], reverse=True)
            self._history[ticket_id] = history

        return ToolResult(
            success=True,
            error=None,
            data={
                "ticket_id": ticket_id,
                "history_entries": history[:limit],
                "total_entries": len(history),
            },
            execution_time_ms=0,
        )
