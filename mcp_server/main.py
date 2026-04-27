"""
PARWA MCP Server — Production Implementation

MCP (Model Context Protocol) server for external AI tool integrations.
Provides a standardized JSON-RPC 2.0 interface for connecting external AI
models and tools to the PARWA customer support platform.

Built on FastAPI with Server-Sent Events (SSE) transport for MCP protocol.
Implements the MCP specification directly without the FastMCP SDK wrapper,
giving full control over the message pipeline, error handling, and middleware.

MCP Protocol Flow:
    1. Client POSTs a JSON-RPC request to /sse or /messages
    2. Server processes the request and streams the response via SSE
    3. Tool calls are proxied to the PARWA backend via authenticated HTTP

Endpoints:
    GET  /health                — Health check (no auth required)
    GET  /                      — Service info + available tools (no auth required)
    GET  /tools                 — List all MCP tools with JSON schemas (no auth required)
    POST /sse                   — SSE endpoint — accepts JSON-RPC, streams MCP responses
    POST /messages              — Alternative JSON-RPC endpoint (returns plain JSON)
    POST /tools/{tool_name}     — Execute a specific tool by name

Tools exposed:
    create_ticket            — Create a support ticket
    search_tickets           — Search tickets by query / status / priority
    get_ticket               — Get a single ticket by ID
    list_agents              — List AI agents with optional status filter
    get_knowledge_base       — Search the knowledge base
    get_dashboard_metrics    — Retrieve dashboard KPIs

Environment variables:
    MCP_PORT             — Server port (default: 8080)
    BACKEND_URL          — Parwa backend URL (default: http://localhost:8000)
    MCP_API_KEY          — API key for auth (empty = disabled)
    MCP_CORS_ORIGINS     — Comma-separated allowed origins (default: *)
    MCP_REQUEST_TIMEOUT  — Backend request timeout in seconds (default: 30)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Ensure project root is on Python path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "production")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("parwa.mcp")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Configuration via environment variables
# ---------------------------------------------------------------------------
MCP_PORT = int(os.environ.get("MCP_PORT", "8080"))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
CORS_ORIGINS_RAW = os.environ.get("MCP_CORS_ORIGINS", "*")
REQUEST_TIMEOUT = float(os.environ.get("MCP_REQUEST_TIMEOUT", "30"))
MCP_SERVER_VERSION = "1.0.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()]

if not MCP_API_KEY:
    logger.warning(
        "MCP_API_KEY is not set. Authentication is DISABLED. "
        "Set MCP_API_KEY to enable API-key authentication."
    )

# ═══════════════════════════════════════════════════════════════════════════
# Shared HTTP client for backend calls
# ═══════════════════════════════════════════════════════════════════════════
_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Lazy-initialised async HTTP client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=10.0),
        )
    return _http_client


async def close_http_client():
    """Close the shared HTTP client (called on shutdown)."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ═══════════════════════════════════════════════════════════════════════════
# JSON Schema definitions for MCP tools
# ═══════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "create_ticket": {
        "name": "create_ticket",
        "description": (
            "Create a new support ticket in PARWA. Use this tool when a customer "
            "reports an issue, asks a question, or needs help. The ticket will be "
            "automatically triaged and routed to an available AI agent or human agent."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Brief summary of the issue (max 500 chars).",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the support request.",
                },
                "customer_email": {
                    "type": "string",
                    "description": "Email of the customer submitting the ticket.",
                    "format": "email",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "default": "medium",
                    "description": "Ticket priority level.",
                },
                "channel": {
                    "type": "string",
                    "enum": ["email", "chat", "phone", "social", "api"],
                    "default": "email",
                    "description": "Channel the ticket was received on.",
                },
            },
            "required": ["subject", "description", "customer_email"],
        },
    },
    "search_tickets": {
        "name": "search_tickets",
        "description": (
            "Search and filter support tickets in PARWA. Use this tool to find "
            "existing tickets by keyword, filter by status or priority, or list "
            "recent tickets. Useful for checking if a similar issue has already "
            "been reported."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "default": "",
                    "description": (
                        "Free-text search across subject and description. "
                        "Empty string returns all tickets."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "pending", "resolved", "closed"],
                    "description": "Optional filter by ticket status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Optional filter by ticket priority.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Max number of results to return.",
                },
            },
            "required": ["query"],
        },
    },
    "get_ticket": {
        "name": "get_ticket",
        "description": (
            "Get full details of a specific support ticket by ID. Use this tool "
            "when you need to see the complete information about a ticket, "
            "including conversation history, status, assigned agent, and metadata."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The unique identifier of the ticket (UUID or integer string).",
                },
            },
            "required": ["ticket_id"],
        },
    },
    "list_agents": {
        "name": "list_agents",
        "description": (
            "List AI agents in the PARWA workforce. Use this tool to see which "
            "AI agents are available, their current workload, capabilities, and "
            "status. Filter by status to find active or idle agents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "idle", "offline", "training"],
                    "description": "Optional filter by agent status.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                    "description": "Max number of results to return.",
                },
            },
            "required": [],
        },
    },
    "get_knowledge_base": {
        "name": "get_knowledge_base",
        "description": (
            "Search the PARWA knowledge base for relevant articles. Use this tool "
            "to find help articles, FAQs, troubleshooting guides, and product "
            "documentation. This helps answer customer questions by retrieving "
            "relevant knowledge base content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for knowledge base articles.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 5,
                    "description": "Max number of articles to return.",
                },
            },
            "required": ["query"],
        },
    },
    "get_dashboard_metrics": {
        "name": "get_dashboard_metrics",
        "description": (
            "Retrieve PARWA dashboard metrics and KPIs. Use this tool to get an "
            "overview of support performance, ticket volume, agent efficiency, "
            "customer satisfaction, SLA compliance, or financial metrics for a "
            "given time period."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "last_7_days", "last_30_days", "last_90_days"],
                    "default": "7d",
                    "description": "Time period for metrics.",
                },
                "metrics_type": {
                    "type": "string",
                    "enum": ["overview", "tickets", "agents", "customers", "sla"],
                    "default": "overview",
                    "description": "Type of metrics to retrieve.",
                },
            },
            "required": [],
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Valid enum value sets (for validation before calling backend)
# ═══════════════════════════════════════════════════════════════════════════

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_STATUSES = {"open", "in_progress", "pending", "resolved", "closed"}
VALID_CHANNELS = {"email", "chat", "phone", "social", "api"}
VALID_AGENT_STATUSES = {"active", "idle", "offline", "training"}
VALID_PERIODS = {"today", "7d", "last_7_days", "30d", "last_30_days", "90d", "last_90_days"}
VALID_METRICS_TYPES = {"overview", "tickets", "agents", "customers", "sla"}

# Normalize period aliases to backend-friendly values
PERIOD_ALIASES = {
    "7d": "last_7_days",
    "30d": "last_30_days",
    "90d": "last_90_days",
}


# ═══════════════════════════════════════════════════════════════════════════
# Helper: call the main Parwa backend via HTTP
# ═══════════════════════════════════════════════════════════════════════════

async def _backend_request(
    method: str,
    path: str,
    *,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
    tenant_id: Optional[str] = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Parwa backend.

    Forwards the MCP_API_KEY so the backend can identify the calling tenant
    or service account. Errors are caught and returned in a structured dict
    so tool handlers can always return a valid MCP text result.
    """
    headers: dict[str, str] = {
        "X-API-Key": MCP_API_KEY,
        "Content-Type": "application/json",
    }
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    client = await get_http_client()
    try:
        resp = await client.request(
            method,
            path,
            json=json_data,
            params=params,
            headers=headers,
        )
        if resp.status_code >= 500:
            logger.error("Backend %s %s returned %s", method, path, resp.status_code)
            return {
                "success": False,
                "error": f"Backend returned HTTP {resp.status_code}",
                "detail": resp.text[:500],
            }
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            return {
                "success": False,
                "error": data.get("detail", data.get("error", f"HTTP {resp.status_code}")),
                "status_code": resp.status_code,
            }
        return {"success": True, "data": data}
    except httpx.ConnectError:
        return {"success": False, "error": "Cannot connect to Parwa backend. Is it running?"}
    except httpx.TimeoutException:
        return {"success": False, "error": "Backend request timed out."}
    except Exception as exc:
        logger.exception("Unexpected backend error")
        return {"success": False, "error": f"Unexpected error: {exc}"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool handler functions
# ═══════════════════════════════════════════════════════════════════════════

async def _tool_create_ticket(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: create_ticket — Create a new support ticket."""
    subject = arguments.get("subject", "")
    description = arguments.get("description", "")
    customer_email = arguments.get("customer_email", "")
    priority = arguments.get("priority", "medium")
    channel = arguments.get("channel", "email")

    # Validate required fields
    if not subject or not subject.strip():
        return {"success": False, "error": "'subject' is required and cannot be empty."}
    if not description or not description.strip():
        return {"success": False, "error": "'description' is required and cannot be empty."}
    if not customer_email or "@" not in customer_email:
        return {"success": False, "error": "'customer_email' is required and must be a valid email."}

    # Validate enum values
    priority = priority.lower()
    if priority not in VALID_PRIORITIES:
        return {
            "success": False,
            "error": f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}",
        }
    channel = channel.lower()
    if channel not in VALID_CHANNELS:
        return {
            "success": False,
            "error": f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}",
        }

    payload = {
        "subject": subject.strip()[:500],
        "description": description.strip(),
        "customer_email": customer_email.strip().lower(),
        "priority": priority,
        "channel": channel,
    }

    result = await _backend_request("POST", "/api/v1/tickets", json_data=payload)

    if result["success"]:
        ticket = result["data"]
        return {
            "success": True,
            "ticket_id": ticket.get("id", ticket.get("ticket_id")),
            "status": ticket.get("status", "open"),
            "priority": ticket.get("priority", priority),
            "subject": ticket.get("subject", subject),
            "message": "Ticket created successfully",
        }
    return {"success": False, "error": result["error"]}


async def _tool_search_tickets(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: search_tickets — Search and filter tickets."""
    query = arguments.get("query", "")
    status = arguments.get("status")
    priority = arguments.get("priority")
    limit = arguments.get("limit", 10)

    # Validate optional enum values
    if status and status.lower() not in VALID_STATUSES:
        return {
            "success": False,
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        }
    if priority and priority.lower() not in VALID_PRIORITIES:
        return {
            "success": False,
            "error": f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}",
        }

    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 100)}
    if query:
        params["q"] = query
    if status:
        params["status"] = status.lower()
    if priority:
        params["priority"] = priority.lower()

    result = await _backend_request("GET", "/api/v1/tickets", params=params)

    if result["success"]:
        data = result["data"]
        tickets = data if isinstance(data, list) else data.get("items", data.get("tickets", [data]))
        total = data.get("total", len(tickets)) if isinstance(data, dict) else len(tickets)
        return {"success": True, "total": total, "returned": len(tickets), "tickets": tickets}
    return {"success": False, "error": result["error"]}


async def _tool_get_ticket(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: get_ticket — Get full details of a ticket."""
    ticket_id = arguments.get("ticket_id", "")

    if not ticket_id or not str(ticket_id).strip():
        return {"success": False, "error": "'ticket_id' is required and cannot be empty."}

    result = await _backend_request("GET", f"/api/v1/tickets/{str(ticket_id).strip()}")

    if result["success"]:
        return {"success": True, "ticket": result["data"]}
    return {"success": False, "error": result["error"]}


async def _tool_list_agents(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: list_agents — List AI agents."""
    status = arguments.get("status")
    limit = arguments.get("limit", 20)

    if status and status.lower() not in VALID_AGENT_STATUSES:
        return {
            "success": False,
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_AGENT_STATUSES))}",
        }

    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 200)}
    if status:
        params["status"] = status.lower()

    result = await _backend_request("GET", "/api/v1/agents", params=params)

    if result["success"]:
        data = result["data"]
        agents = data if isinstance(data, list) else data.get("items", data.get("agents", [data]))
        return {"success": True, "total": len(agents), "agents": agents}
    return {"success": False, "error": result["error"]}


async def _tool_get_knowledge_base(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: get_knowledge_base — Search knowledge base."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)

    if not query or not query.strip():
        return {"success": False, "error": "'query' is required and cannot be empty."}

    params: dict[str, Any] = {"q": query.strip(), "limit": min(max(int(limit), 1), 50)}
    result = await _backend_request("GET", "/api/v1/knowledge-base/search", params=params)

    if result["success"]:
        data = result["data"]
        articles = data if isinstance(data, list) else data.get("items", data.get("articles", [data]))
        return {"success": True, "total": len(articles), "articles": articles}
    return {"success": False, "error": result["error"]}


async def _tool_get_dashboard_metrics(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handler: get_dashboard_metrics — Get dashboard KPIs."""
    period = arguments.get("period", "7d")
    metrics_type = arguments.get("metrics_type", "overview")

    # Normalize period aliases
    period = PERIOD_ALIASES.get(period.lower(), period.lower())
    if period not in VALID_PERIODS:
        return {
            "success": False,
            "error": f"Invalid period '{period}'. Must be one of: {', '.join(sorted(VALID_PERIODS))}",
        }

    if metrics_type.lower() not in VALID_METRICS_TYPES:
        return {
            "success": False,
            "error": f"Invalid metrics_type '{metrics_type}'. Must be one of: {', '.join(sorted(VALID_METRICS_TYPES))}",
        }

    params: dict[str, Any] = {"period": period, "type": metrics_type.lower()}
    result = await _backend_request("GET", "/api/v1/dashboard/metrics", params=params)

    if result["success"]:
        return {
            "success": True,
            "period": period,
            "metrics_type": metrics_type,
            "metrics": result["data"],
        }
    return {"success": False, "error": result["error"]}


# ═══════════════════════════════════════════════════════════════════════════
# Tool dispatch registry
# ═══════════════════════════════════════════════════════════════════════════

TOOL_HANDLERS: Dict[
    str,
    Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
] = {
    "create_ticket": _tool_create_ticket,
    "search_tickets": _tool_search_tickets,
    "get_ticket": _tool_get_ticket,
    "list_agents": _tool_list_agents,
    "get_knowledge_base": _tool_get_knowledge_base,
    "get_dashboard_metrics": _tool_get_dashboard_metrics,
}


# ═══════════════════════════════════════════════════════════════════════════
# MCP Protocol: JSON-RPC 2.0 message handling
# ═══════════════════════════════════════════════════════════════════════════

def _make_jsonrpc_response(
    request_id: Any,
    result: Optional[Any] = None,
    error: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 response object."""
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def _make_jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    return _make_jsonrpc_response(
        request_id,
        error={"code": code, "message": message},
    )


def _make_mcp_tool_result(
    content: Optional[str] = None,
    is_error: bool = False,
) -> dict[str, Any]:
    """Build an MCP tool result content structure."""
    return {
        "content": [
            {
                "type": "text",
                "text": content or "",
            }
        ],
        "isError": is_error,
    }


async def handle_mcp_request(
    method: str,
    params: Optional[dict[str, Any]],
    request_id: Any,
) -> dict[str, Any]:
    """Process an MCP JSON-RPC request and return a response dict.

    Supports:
        - initialize         — MCP session initialization
        - tools/list         — List available tools
        - tools/call         — Execute a specific tool
        - notifications/initialized — Client notification (no response needed)
    """
    start_time = time.monotonic()

    # --- initialize ---
    if method == "initialize":
        logger.info("MCP initialize request (id=%s)", request_id)
        result = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": "PARWA",
                "version": MCP_SERVER_VERSION,
            },
        }
        elapsed = (time.monotonic() - start_time) * 1000
        logger.info("MCP initialize completed in %.1fms", elapsed)
        return _make_jsonrpc_response(request_id, result=result)

    # --- tools/list ---
    if method == "tools/list":
        logger.info("MCP tools/list request (id=%s)", request_id)
        tools_list = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
            for tool in TOOL_DEFINITIONS.values()
        ]
        result = {"tools": tools_list}
        elapsed = (time.monotonic() - start_time) * 1000
        logger.info("MCP tools/list returned %d tools in %.1fms", len(tools_list), elapsed)
        return _make_jsonrpc_response(request_id, result=result)

    # --- tools/call ---
    if method == "tools/call":
        if not params or "name" not in params:
            return _make_jsonrpc_error(request_id, -32602, "Missing required 'name' parameter in tools/call")

        tool_name = params["name"]
        arguments = params.get("arguments", {})

        logger.info("MCP tools/call: %s (id=%s)", tool_name, request_id)

        # Look up handler
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            available = ", ".join(sorted(TOOL_HANDLERS.keys()))
            return _make_jsonrpc_error(
                request_id,
                -32601,
                f"Unknown tool '{tool_name}'. Available tools: {available}",
            )

        # Execute tool handler
        try:
            tool_result = await handler(arguments if isinstance(arguments, dict) else {})
        except Exception as exc:
            logger.exception("Tool %s raised an exception", tool_name)
            mcp_result = _make_mcp_tool_result(
                content=json.dumps({"success": False, "error": f"Internal error: {exc}"}),
                is_error=True,
            )
            elapsed = (time.monotonic() - start_time) * 1000
            logger.info("MCP tools/call %s FAILED in %.1fms", tool_name, elapsed)
            return _make_jsonrpc_response(request_id, result=mcp_result)

        # Format result
        is_error = not tool_result.get("success", False)
        content_text = json.dumps(tool_result, indent=2, default=str)
        mcp_result = _make_mcp_tool_result(content=content_text, is_error=is_error)

        elapsed = (time.monotonic() - start_time) * 1000
        logger.info(
            "MCP tools/call %s completed in %.1fms (success=%s)",
            tool_name,
            elapsed,
            not is_error,
        )
        return _make_jsonrpc_response(request_id, result=mcp_result)

    # --- ping ---
    if method == "ping":
        return _make_jsonrpc_response(request_id, result={})

    # --- Unknown method ---
    return _make_jsonrpc_error(
        request_id,
        -32601,
        f"Method not found: {method}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic models for direct tool execution endpoint
# ═══════════════════════════════════════════════════════════════════════════

class ToolExecutionRequest(BaseModel):
    """Request body for POST /tools/{tool_name}."""
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments matching the tool's input schema.",
    )


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request body."""
    jsonrpc: str = Field(default="2.0", pattern="^2\\.0$")
    method: str = Field(description="JSON-RPC method name")
    params: Optional[dict[str, Any]] = Field(default=None, description="Method parameters")
    id: Optional[Any] = Field(default=None, description="Request ID for correlation")


# ═══════════════════════════════════════════════════════════════════════════
# ASGI Middleware: API key authentication
# ═══════════════════════════════════════════════════════════════════════════

PUBLIC_PATHS = {
    "/health",
    "/",
    "/tools",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates X-API-Key on protected endpoints.

    Public paths (health, root, tools listing, docs) are exempt.
    When MCP_API_KEY is empty, authentication is disabled entirely.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths
        is_public = (
            path in PUBLIC_PATHS
            or path.startswith("/docs/")
            or path.startswith("/openapi")
            or path.startswith("/redoc")
        )
        if is_public:
            return await call_next(request)

        # Allow OPTIONS preflight (CORS will handle it)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Enforce API key if configured
        if MCP_API_KEY:
            api_key = request.headers.get("x-api-key", "")
            if not api_key or api_key != MCP_API_KEY:
                logger.warning(
                    "Auth failed: missing or invalid X-API-Key from %s",
                    request.client.host if request.client else "unknown",
                )
                return JSONResponse(
                    {"error": "Unauthorized", "detail": "Missing or invalid X-API-Key header."},
                    status_code=401,
                )

        return await call_next(request)


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="PARWA MCP Server",
    version=MCP_SERVER_VERSION,
    description=(
        "Model Context Protocol (MCP) server exposing PARWA customer-support "
        "capabilities as tools for AI assistants and LLM integrations.\n\n"
        "## Transport\n"
        "- **SSE**: POST to `/sse` with a JSON-RPC 2.0 body; responses stream back as Server-Sent Events.\n"
        "- **Direct JSON**: POST to `/messages` for plain JSON-RPC responses.\n"
        "- **REST**: POST to `/tools/{tool_name}` for simple tool execution.\n\n"
        "## Authentication\n"
        "Set the `MCP_API_KEY` environment variable to enable API-key authentication. "
        "Pass the key via the `X-API-Key` header.\n\n"
        "## Tools\n"
        "Six MCP tools are available: `create_ticket`, `search_tickets`, `get_ticket`, "
        "`list_agents`, `get_knowledge_base`, `get_dashboard_metrics`."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth middleware
app.add_middleware(APIKeyAuthMiddleware)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    logger.info(
        "PARWA MCP Server starting up (port=%d, backend=%s, auth=%s)",
        MCP_PORT,
        BACKEND_URL,
        "ENABLED" if MCP_API_KEY else "DISABLED",
    )


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("PARWA MCP Server shutting down...")
    await close_http_client()


# ═══════════════════════════════════════════════════════════════════════════
# Public endpoints (no auth required)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker container / load balancer monitoring.

    Verifies backend connectivity and returns degraded status if the main
    Parwa backend is unreachable.
    """
    backend_ok = False
    backend_latency_ms = None
    try:
        client = await get_http_client()
        t0 = time.monotonic()
        resp = await client.get("/health", timeout=5.0)
        backend_latency_ms = round((time.monotonic() - t0) * 1000, 1)
        backend_ok = resp.status_code == 200
    except Exception:
        pass

    status = "healthy" if backend_ok else "degraded"
    return {
        "status": status,
        "service": "parwa-mcp",
        "version": MCP_SERVER_VERSION,
        "protocol": MCP_PROTOCOL_VERSION,
        "backend": {
            "status": "connected" if backend_ok else "unreachable",
            "url": BACKEND_URL,
            "latency_ms": backend_latency_ms,
        },
        "tools_count": len(TOOL_DEFINITIONS),
    }


@app.get("/", tags=["System"])
async def root_info():
    """Service info and endpoint directory. Also lists available tools summary."""
    tools_summary = [
        {"name": t["name"], "description": t["description"]}
        for t in TOOL_DEFINITIONS.values()
    ]
    return {
        "service": "PARWA MCP Server",
        "version": MCP_SERVER_VERSION,
        "protocol": "MCP (Model Context Protocol)",
        "protocol_version": MCP_PROTOCOL_VERSION,
        "transport": "SSE + REST",
        "endpoints": {
            "health": "GET /health",
            "root": "GET /",
            "tools_list": "GET /tools",
            "sse_stream": "POST /sse",
            "messages": "POST /messages",
            "tool_execute": "POST /tools/{tool_name}",
            "docs": "GET /docs",
        },
        "tools_count": len(TOOL_DEFINITIONS),
        "tools": tools_summary,
        "backend_url": BACKEND_URL,
        "authentication": "enabled" if MCP_API_KEY else "disabled",
    }


@app.get("/tools", tags=["MCP Tools"])
async def list_tools():
    """List all available MCP tools with their full JSON Schema definitions.

    This is a REST endpoint for tool discovery without initiating an MCP session.
    For the MCP protocol version, send a `tools/list` JSON-RPC request to `/sse`.
    """
    return {
        "tools": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
            for tool in TOOL_DEFINITIONS.values()
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# SSE endpoint — MCP protocol over Server-Sent Events
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/sse", tags=["MCP Protocol"])
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol communication.

    Accepts a JSON-RPC 2.0 request in the POST body and streams the
    response back as a Server-Sent Event. Supports batch requests
    (array of JSON-RPC messages).

    Request body must be a JSON-RPC 2.0 message:
    ```json
    {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "my-client", "version": "1.0"}
        }
    }
    ```
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON body. Expected a JSON-RPC 2.0 request."},
            status_code=400,
        )

    # Handle batch requests
    if isinstance(body, list):
        requests = body
    else:
        requests = [body]

    async def event_generator():
        for req in requests:
            # Validate JSON-RPC structure
            method = req.get("method")
            params = req.get("params")
            req_id = req.get("id")

            if not method:
                error_resp = _make_jsonrpc_error(
                    req_id, -32600, "Invalid Request: missing 'method' field"
                )
                yield f"data: {json.dumps(error_resp)}\n\n"
                continue

            # Process the MCP request
            response = await handle_mcp_request(method, params, req_id)

            # Stream as SSE
            yield f"data: {json.dumps(response)}\n\n"

        # Send final [DONE] marker
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# JSON-RPC endpoint (plain HTTP, non-streaming)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/messages", tags=["MCP Protocol"])
async def messages_endpoint(body: JsonRpcRequest):
    """Plain JSON-RPC 2.0 endpoint for MCP protocol communication.

    Accepts a single JSON-RPC request and returns a plain JSON response.
    Use this when SSE streaming is not needed (e.g., simple tool calls,
    testing, or clients that don't support SSE).
    """
    response = await handle_mcp_request(body.method, body.params, body.id)
    return JSONResponse(response)


# ═══════════════════════════════════════════════════════════════════════════
# Direct tool execution endpoint (REST-style)
# ═══════════════════════════════════════════════════════════════════════════

@app.post(
    "/tools/{tool_name}",
    tags=["MCP Tools"],
    responses={
        400: {"description": "Invalid arguments"},
        401: {"description": "Unauthorized — missing or invalid X-API-Key"},
        404: {"description": "Tool not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def execute_tool(tool_name: str, body: ToolExecutionRequest = ToolExecutionRequest()):
    """Execute a specific MCP tool by name.

    This is a REST-style alternative to the JSON-RPC `tools/call` method.
    Pass tool arguments in the request body matching the tool's input schema.

    Example:
    ```bash
    curl -X POST http://localhost:8080/tools/create_ticket \\
        -H "Content-Type: application/json" \\
        -H "X-API-Key: your-key" \\
        -d '{"arguments": {"subject": "Login issue", "description": "Cannot log in", "customer_email": "user@example.com"}}'
    ```
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        available = ", ".join(sorted(TOOL_HANDLERS.keys()))
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Tool not found",
                "tool": tool_name,
                "available_tools": available,
            },
        )

    try:
        result = await handler(body.arguments if isinstance(body.arguments, dict) else {})
    except Exception as exc:
        logger.exception("Direct tool execution %s failed", tool_name)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Internal error executing tool '{tool_name}': {exc}",
            },
        )

    is_error = not result.get("success", False)
    status_code = 200 if not is_error else 422
    return JSONResponse(result, status_code=status_code)


# ═══════════════════════════════════════════════════════════════════════════
# Global exception handler
# ═══════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler returning structured error responses."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        {
            "error": "Internal Server Error",
            "detail": str(exc) if os.environ.get("ENVIRONMENT") != "production" else "An unexpected error occurred.",
        },
        status_code=500,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting PARWA MCP Server on port %d (backend: %s)",
        MCP_PORT,
        BACKEND_URL,
    )
    if MCP_API_KEY:
        logger.info("API key authentication is ENABLED")
    else:
        logger.warning("API key authentication is DISABLED")

    uvicorn.run(
        "mcp_server.main:app",
        host="0.0.0.0",
        port=MCP_PORT,
        log_level="info",
        loop="uvloop" if sys.platform != "win32" else "asyncio",
    )
