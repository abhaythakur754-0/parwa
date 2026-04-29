"""
PARWA ReAct Tools — Tool Registry for ReAct Technique (P4.3)

Implements the 4 required tools for the ReAct (Reasoning + Acting) pattern:
1. knowledge_base_search — Search knowledge base for relevant information
2. customer_lookup — Look up customer details and history
3. ticket_history_search — Search past ticket history
4. order_status_check — Check order/shipping status

Each tool has:
- name: str (unique identifier)
- description: str (what the tool does, used by LLM)
- parameters_schema: dict (JSON Schema for parameters)
- execute(company_id, params, db) -> dict (tool execution result)

BC-001: All tool executions are scoped to company_id.
BC-008: Tools never crash — always return a result dict.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# ── Base Tool ──────────────────────────────────────────────────────


class BaseTool(ABC):
    """Base class for all ReAct tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used by the LLM and registry."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @property
    def parameters_schema(self) -> dict:
        """JSON Schema for tool parameters. Override in subclasses."""
        return {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(
        self,
        company_id: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute the tool scoped to *company_id*.

        Returns a dict with ``"success"`` and either ``"data"`` or ``"error"``.
        BC-008: must never raise — wrap everything in try/except at the
        registry level, but tools should also be defensive.
        """
        ...


# ── Tool 1: Knowledge Base Search ─────────────────────────────────


class KnowledgeBaseSearchTool(BaseTool):
    """Search the company's knowledge base for relevant articles."""

    @property
    def name(self) -> str:
        return "knowledge_base_search"

    @property
    def description(self) -> str:
        return "Search the company's knowledge base for relevant articles and documents"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for the knowledge base",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        company_id: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        query: str = params.get("query", "")
        max_results: int = min(params.get("max_results", 5), 20)

        db = kwargs.get("db")
        if db is not None:
            try:
                from database.models.knowledge_base import KnowledgeBaseArticle

                rows = (
                    db.query(KnowledgeBaseArticle)
                    .filter(
                        KnowledgeBaseArticle.company_id == company_id,
                        KnowledgeBaseArticle.content.ilike(f"%{query}%"),
                    )
                    .limit(max_results)
                    .all()
                )
                results = [
                    {"id": r.id, "title": r.title, "snippet": (r.content or "")[:200]}
                    for r in rows
                ]
            except Exception:
                results = []
        else:
            results = []

        return {
            "success": True,
            "tool": self.name,
            "data": {
                "query": query,
                "results": results,
                "total": len(results),
            },
        }


# ── Tool 2: Customer Lookup ───────────────────────────────────────


class CustomerLookupTool(BaseTool):
    """Look up customer details including contact info, tier, and status."""

    @property
    def name(self) -> str:
        return "customer_lookup"

    @property
    def description(self) -> str:
        return (
            "Look up customer details including contact info, "
            "subscription tier, and account status"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Unique identifier of the customer",
                },
            },
            "required": ["customer_id"],
        }

    async def execute(
        self,
        company_id: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        customer_id: str = params.get("customer_id", "")

        db = kwargs.get("db")
        customer_data = {
            "customer_id": customer_id,
            "name": None,
            "email": None,
            "tier": None,
            "status": None,
        }
        if db is not None and customer_id:
            try:
                from database.models.tickets import Customer

                row = (
                    db.query(Customer)
                    .filter(
                        Customer.id == customer_id, Customer.company_id == company_id
                    )
                    .first()
                )
                if row is not None:
                    customer_data.update(
                        {
                            "name": getattr(row, "name", None),
                            "email": getattr(row, "email", None),
                            "tier": getattr(row, "tier", None),
                            "status": getattr(row, "status", None),
                        }
                    )
            except Exception:
                pass

        return {
            "success": True,
            "tool": self.name,
            "data": customer_data,
        }


# ── Tool 3: Ticket History Search ─────────────────────────────────


class TicketHistorySearchTool(BaseTool):
    """Search past ticket history for patterns and similar issues."""

    @property
    def name(self) -> str:
        return "ticket_history_search"

    @property
    def description(self) -> str:
        return (
            "Search past ticket history for patterns, "
            "similar issues, and resolution approaches"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant past tickets",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tickets to return (1-20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        company_id: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        query: str = params.get("query", "")
        limit: int = min(params.get("limit", 5), 20)

        db = kwargs.get("db")
        tickets = []
        if db is not None and query:
            try:
                from database.models.tickets import Ticket

                pattern = f"%{query}%"
                rows = (
                    db.query(Ticket)
                    .filter(
                        Ticket.company_id == company_id,
                        Ticket.subject.ilike(pattern),
                    )
                    .order_by(Ticket.created_at.desc())
                    .limit(limit)
                    .all()
                )
                tickets = [
                    {
                        "id": r.id,
                        "subject": r.subject,
                        "status": r.status,
                        "created_at": (
                            r.created_at.isoformat() if r.created_at else None
                        ),
                    }
                    for r in rows
                ]
            except Exception:
                pass

        return {
            "success": True,
            "tool": self.name,
            "data": {
                "query": query,
                "tickets": tickets,
                "total": len(tickets),
            },
        }


# ── Tool 4: Order Status Check ────────────────────────────────────


class OrderStatusCheckTool(BaseTool):
    """Check the current status of an order."""

    @property
    def name(self) -> str:
        return "order_status_check"

    @property
    def description(self) -> str:
        return (
            "Check the current status of an order including shipping, "
            "delivery, and payment status"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Unique identifier of the order",
                },
            },
            "required": ["order_id"],
        }

    async def execute(
        self,
        company_id: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        order_id: str = params.get("order_id", "")

        db = kwargs.get("db")
        order_data = {
            "order_id": order_id,
            "status": None,
            "tracking_number": None,
            "estimated_delivery": None,
        }
        if db is not None and order_id:
            try:
                from database.models.orders import Order

                row = (
                    db.query(Order)
                    .filter(Order.id == order_id, Order.company_id == company_id)
                    .first()
                )
                if row is not None:
                    order_data.update(
                        {
                            "status": getattr(row, "status", None),
                            "tracking_number": getattr(row, "tracking_number", None),
                            "estimated_delivery": (
                                row.estimated_delivery.isoformat()
                                if getattr(row, "estimated_delivery", None)
                                else None
                            ),
                        }
                    )
            except Exception:
                pass

        return {
            "success": True,
            "tool": self.name,
            "data": order_data,
        }


# ── Tool Registry ─────────────────────────────────────────────────


class ToolRegistry:
    """
    Registry for ReAct tools.

    Provides lookup, listing, and safe execution of registered tools.
    BC-008: ``execute_tool`` never crashes — unknown tools and runtime
    exceptions are caught and returned as error dicts.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    # ── Mutation ────────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance by its *name*."""
        self._tools[tool.name] = tool

    # ── Query ───────────────────────────────────────────────────

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a tool by name, or *None* if not registered."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Return all registered tool instances."""
        return list(self._tools.values())

    def get_tool_descriptions(self) -> str:
        """Return formatted tool descriptions for LLM prompt injection."""
        descriptions: list[str] = []
        for tool in self._tools.values():
            descriptions.append(
                f"- {tool.name}: {tool.description}\n"
                f"  Parameters: {json.dumps(tool.parameters_schema)}"
            )
        return "\n".join(descriptions)

    # ── Execution ───────────────────────────────────────────────

    async def execute_tool(
        self,
        name: str,
        company_id: str,
        params: dict,
        timeout: float = 30.0,
        **kwargs,
    ) -> dict:
        """
        Execute a registered tool by *name*.

        BC-008: Returns an error dict instead of raising on unknown
        tools or runtime failures.

        F-157: Wraps execution in asyncio.wait_for with a configurable
        timeout (default 30 s) to prevent indefinite hangs.
        """
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            return await asyncio.wait_for(
                tool.execute(company_id, params, **kwargs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": (f"Tool '{name}' timed out after {timeout:.1f}s"),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(exc)}",
            }


# ── Default Registry (module-level singleton) ────────────────────

default_tool_registry = ToolRegistry()
default_tool_registry.register(KnowledgeBaseSearchTool())
default_tool_registry.register(CustomerLookupTool())
default_tool_registry.register(TicketHistorySearchTool())
default_tool_registry.register(OrderStatusCheckTool())
