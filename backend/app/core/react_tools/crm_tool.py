"""
PARWA ReAct Tool — CRM Integration  (F-157)

Exposes CRM-related actions to the ReAct agent:
- get_customer            Fetch full customer profile
- search_customers        Search customers by name, email, or phone
- update_customer         Update customer fields (name, email, phone, tier)
- get_interaction_history Get all interactions for a customer
- add_note                Attach a note to a customer record
- get_customer_stats      Get aggregate stats for a customer

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

_FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fatima", "George",
    "Hannah", "Ivan", "Julia", "Kevin", "Liam", "Maya", "Nathan",
    "Olivia", "Priya", "Quinn", "Raj", "Sophie", "Tyler",
]
_LAST_NAMES = [
    "Anderson", "Brown", "Chen", "Davis", "Eriksson", "Fernandez",
    "Gupta", "Huang", "Ibrahim", "Johnson", "Kim", "Lopez",
    "Martinez", "Nguyen", "Patel", "Quinn", "Robinson", "Singh",
    "Tanaka", "Williams",
]
_TIERS = ["free", "starter", "professional", "enterprise"]
_CHANNELS = ["email", "chat", "phone", "in_app", "social"]
_COUNTRIES = ["US", "CA", "GB", "DE", "FR", "AU", "JP", "IN", "BR", "MX"]


def _mock_customer(
    customer_id: str | None = None,
    company_id: str = "",
    name: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Generate a realistic mock customer record."""
    cid = customer_id or f"CUST-{uuid.uuid4().hex[:8].upper()}"
    first = name.split()[0] if name else random.choice(_FIRST_NAMES)
    last = name.split()[-1] if name and " " in name else random.choice(_LAST_NAMES)
    domain = random.choice(["gmail.com", "outlook.com", "company.io", "example.com"])
    local = f"{first.lower()}.{last.lower()}"

    created = datetime.now(timezone.utc) - timedelta(
        days=random.randint(30, 1000),
    )
    last_active = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
    )

    return {
        "customer_id": cid,
        "company_id": company_id,
        "name": f"{first} {last}",
        "first_name": first,
        "last_name": last,
        "email": email or f"{local}@{domain}",
        "phone": f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "tier": random.choice(_TIERS),
        "status": "active",
        "country": random.choice(_COUNTRIES),
        "created_at": created.isoformat(),
        "last_active_at": last_active.isoformat(),
        "lifetime_value": round(random.uniform(50, 15000), 2),
        "total_orders": random.randint(0, 50),
        "tags": random.sample(["vip", "churned", "new", "enterprise", "high-value", "support-frequent"], k=random.randint(1, 3)),
    }


def _mock_interactions(customer_id: str, company_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Generate mock interaction history."""
    interactions: list[dict[str, Any]] = []
    subjects = [
        "Billing inquiry",
        "Feature request",
        "Technical support",
        "Account settings",
        "Plan upgrade question",
        "Integration help",
        "Bug report",
        "Cancellation concern",
    ]
    for i in range(min(limit, 10)):
        ts = datetime.now(timezone.utc) - timedelta(
            days=random.randint(1, 90),
            hours=random.randint(0, 23),
        )
        interactions.append({
            "interaction_id": f"INT-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": customer_id,
            "company_id": company_id,
            "channel": random.choice(_CHANNELS),
            "subject": random.choice(subjects),
            "direction": random.choice(["inbound", "outbound"]),
            "status": random.choice(["open", "closed", "pending"]),
            "created_at": ts.isoformat(),
            "agent_id": f"AGENT-{random.randint(1, 20)}" if random.random() > 0.3 else None,
            "summary": f"Customer {random.choice(['asked about', 'reported', 'requested', 'discussed'])} {random.choice(subjects).lower()}",
        })
    return interactions


# ── Tool Implementation ────────────────────────────────────────────


class CRMTool(BaseReactTool):
    """ReAct tool for CRM system integration."""

    def __init__(self) -> None:
        self._customers: dict[str, dict[str, Any]] = {}
        self._notes: dict[str, list[dict[str, Any]]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "crm_integration"

    @property
    def description(self) -> str:
        return (
            "Look up customers, update records, get interaction history, "
            "manage contacts, and view customer statistics"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "get_customer",
            "search_customers",
            "update_customer",
            "get_interaction_history",
            "add_note",
            "get_customer_stats",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="get_customer",
                    description="Fetch full customer profile by ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Unique customer identifier"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Full customer object with contact info, tier, tags, and metadata",
                ),
                ActionSchema(
                    name="search_customers",
                    description="Search customers by name, email, phone, or tag",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (name, email, or phone)"},
                            "tag": {"type": "string", "description": "Filter by tag"},
                            "tier": {"type": "string", "description": "Filter by tier: free, starter, professional, enterprise"},
                            "limit": {"type": "integer", "description": "Max results (1-50)", "default": 10},
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of matching customer summaries",
                ),
                ActionSchema(
                    name="update_customer",
                    description="Update customer fields such as name, email, phone, or tier",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer to update"},
                            "name": {"type": "string", "description": "New full name"},
                            "email": {"type": "string", "description": "New email address"},
                            "phone": {"type": "string", "description": "New phone number"},
                            "tier": {"type": "string", "description": "New tier: free, starter, professional, enterprise"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Updated customer object with changed fields",
                ),
                ActionSchema(
                    name="get_interaction_history",
                    description="Get all interactions (calls, chats, emails) for a customer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer ID"},
                            "limit": {"type": "integer", "description": "Max interactions (1-50)", "default": 10},
                            "channel": {"type": "string", "description": "Filter by channel: email, chat, phone, in_app, social"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="List of interaction records with timestamps and summaries",
                ),
                ActionSchema(
                    name="add_note",
                    description="Attach a note to a customer record",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer to annotate"},
                            "content": {"type": "string", "description": "Note content"},
                            "author": {"type": "string", "description": "Note author name or ID"},
                            "tags": {"type": "string", "description": "Comma-separated tags for the note"},
                        },
                        "required": ["customer_id", "content"],
                    },
                    required_params=["customer_id", "content"],
                    returns="Note object with note_id and timestamp",
                ),
                ActionSchema(
                    name="get_customer_stats",
                    description="Get aggregate statistics for a customer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer ID"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Stats object with LTV, order count, interaction count, and engagement score",
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
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "get_customer": self._get_customer,
            "search_customers": self._search_customers,
            "update_customer": self._update_customer,
            "get_interaction_history": self._get_interaction_history,
            "add_note": self._add_note,
            "get_customer_stats": self._get_customer_stats,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {', '.join(self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _get_customer(self, company_id: str, **params: Any) -> ToolResult:
        """Fetch full customer profile."""
        customer_id: str = params.get("customer_id", "")

        if customer_id in self._customers:
            cust = self._customers[customer_id]
            if cust["company_id"] != company_id:
                return ToolResult(
                    success=False,
                    error=f"Customer {customer_id} not found in company scope",
                    data=None,
                    execution_time_ms=0,
                )
            return ToolResult(success=True, error=None, data=cust, execution_time_ms=0)

        cust = _mock_customer(customer_id=customer_id, company_id=company_id)
        self._customers[customer_id] = cust
        return ToolResult(success=True, error=None, data=cust, execution_time_ms=0)

    async def _search_customers(self, company_id: str, **params: Any) -> ToolResult:
        """Search customers by various criteria."""
        query: str = params.get("query", "").lower().strip()
        tag: str | None = params.get("tag")
        tier: str | None = params.get("tier")
        limit: int = min(max(params.get("limit", 10), 1), 50)

        # Generate mock results
        results: list[dict[str, Any]] = []
        for _ in range(min(limit, 20)):
            cust = _mock_customer(company_id=company_id)
            results.append(cust)

        # Apply filters
        if query:
            results = [
                c for c in results
                if query in c["name"].lower()
                or query in c["email"].lower()
                or query in c.get("phone", "")
            ]
        if tag:
            results = [c for c in results if tag in c.get("tags", [])]
        if tier:
            results = [c for c in results if c.get("tier") == tier]

        # Store for later retrieval
        for c in results:
            self._customers[c["customer_id"]] = c

        return ToolResult(
            success=True,
            error=None,
            data={
                "customers": results,
                "total": len(results),
                "query": query or None,
            },
            execution_time_ms=0,
        )

    async def _update_customer(self, company_id: str, **params: Any) -> ToolResult:
        """Update customer fields."""
        customer_id: str = params.get("customer_id", "")

        cust = self._customers.get(customer_id)
        if cust is None:
            cust = _mock_customer(customer_id=customer_id, company_id=company_id)
            self._customers[customer_id] = cust

        if cust["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Customer {customer_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        updatable = {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "tier": "tier",
        }

        updated_fields: list[str] = []
        for param_key, field_name in updatable.items():
            value = params.get(param_key)
            if value is not None:
                cust[field_name] = value
                updated_fields.append(param_key)
                # Also update first/last name if name changed
                if param_key == "name" and isinstance(value, str) and " " in value:
                    parts = value.split(maxsplit=1)
                    cust["first_name"] = parts[0]
                    cust["last_name"] = parts[-1]

        if not updated_fields:
            return ToolResult(
                success=False,
                error="No fields to update. Provide name, email, phone, or tier.",
                data=None,
                execution_time_ms=0,
            )

        # Validate tier
        if "tier" in params and params["tier"] not in _TIERS:
            return ToolResult(
                success=False,
                error=f"Invalid tier '{params['tier']}'. Must be one of: {', '.join(_TIERS)}",
                data=None,
                execution_time_ms=0,
            )

        cust["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._customers[customer_id] = cust

        return ToolResult(
            success=True,
            error=None,
            data={
                "customer_id": customer_id,
                "updated_fields": updated_fields,
                "customer": cust,
            },
            execution_time_ms=0,
        )

    async def _get_interaction_history(self, company_id: str, **params: Any) -> ToolResult:
        """Get interaction history for a customer."""
        customer_id: str = params.get("customer_id", "")
        limit: int = min(max(params.get("limit", 10), 1), 50)
        channel: str | None = params.get("channel")

        interactions = _mock_interactions(customer_id, company_id, limit=limit)

        if channel:
            interactions = [i for i in interactions if i["channel"] == channel]

        interactions = interactions[:limit]

        return ToolResult(
            success=True,
            error=None,
            data={
                "customer_id": customer_id,
                "interactions": interactions,
                "total": len(interactions),
            },
            execution_time_ms=0,
        )

    async def _add_note(self, company_id: str, **params: Any) -> ToolResult:
        """Attach a note to a customer record."""
        customer_id: str = params.get("customer_id", "")
        content: str = params.get("content", "")
        author: str | None = params.get("author")
        raw_tags: str | None = params.get("tags")

        if not content.strip():
            return ToolResult(
                success=False,
                error="Note content cannot be empty",
                data=None,
                execution_time_ms=0,
            )

        tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []

        note: dict[str, Any] = {
            "note_id": f"NOTE-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": customer_id,
            "company_id": company_id,
            "content": content.strip(),
            "author": author or "system",
            "tags": tags,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if customer_id not in self._notes:
            self._notes[customer_id] = []
        self._notes[customer_id].append(note)

        return ToolResult(
            success=True,
            error=None,
            data=note,
            execution_time_ms=0,
        )

    async def _get_customer_stats(self, company_id: str, **params: Any) -> ToolResult:
        """Get aggregate statistics for a customer."""
        customer_id: str = params.get("customer_id", "")

        cust = self._customers.get(customer_id)
        if cust is None:
            cust = _mock_customer(customer_id=customer_id, company_id=company_id)
            self._customers[customer_id] = cust

        if cust["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Customer {customer_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        interactions = _mock_interactions(customer_id, company_id, limit=20)
        notes = self._notes.get(customer_id, [])

        # Engagement score (simple heuristic)
        interaction_count = len(interactions)
        days_since_active = max(
            (datetime.now(timezone.utc) - datetime.fromisoformat(cust["last_active_at"])).days,
            0,
        )
        engagement = max(100 - days_since_active, 0) + min(interaction_count * 5, 50)

        return ToolResult(
            success=True,
            error=None,
            data={
                "customer_id": customer_id,
                "name": cust["name"],
                "tier": cust["tier"],
                "lifetime_value": cust["lifetime_value"],
                "total_orders": cust["total_orders"],
                "interaction_count": interaction_count,
                "note_count": len(notes),
                "engagement_score": min(engagement, 100),
                "days_since_last_active": days_since_active,
                "tags": cust.get("tags", []),
                "account_age_days": (
                    datetime.now(timezone.utc) - datetime.fromisoformat(cust["created_at"])
                ).days,
            },
            execution_time_ms=0,
        )
