"""
PARWA MCP Server — Production Entry Point

MCP (Model Context Protocol) server for external AI tool integrations.
Provides a standardized interface for connecting external AI models
and tools to the PARWA customer support platform.

This server acts as a "tool gateway" that allows PARWA to plug into
any client tool (Shopify, Stripe, GitHub, etc.) without writing
custom integration code for each.

Endpoints:
    GET  /health                        — Health check
    GET  /mcp/tools                     — List all available MCP tools
    POST /mcp/tools/{tool_name}/invoke  — Invoke a specific tool
    GET  /mcp/servers                   — List all registered sub-servers
    GET  /mcp/servers/{server_name}/tools — List tools from a specific server

Each sub-server also exposes its own REST endpoints:
    /knowledge/faq/*     — FAQ search
    /knowledge/rag/*     — RAG queries
    /knowledge/kb/*      — Knowledge base queries
    /integrations/email/*    — Email tools
    /integrations/voice/*    — Voice call tools
    /integrations/chat/*     — Chat messaging tools
    /integrations/ticketing/* — Ticketing tools
    /integrations/ecommerce/* — E-commerce tools
    /integrations/crm/*       — CRM tools
    /tools/analytics/*     — Analytics queries
    /tools/monitoring/*    — Monitoring status
    /tools/notification/*  — Notification delivery
    /tools/compliance/*    — Compliance checks
    /tools/sla/*           — SLA management
"""

import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx

# Ensure project root is on Python path so imports work
# both when running as `python -m mcp_server.main` and in Docker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "development")

from mcp_server.base_server import (
    MCPRegistry,
    MCPServerBase,
    configure_logging,
    get_logger,
    registry,
)
from mcp_server.config import get_settings
from mcp_server.models import (
    ErrorResponse,
    HealthResponse,
    ServerInfo,
    ServersListResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolsListResponse,
)

# Import all sub-servers (triggers their registration below)
from mcp_server.knowledge.faq_server import faq_server
from mcp_server.knowledge.rag_server import rag_server
from mcp_server.knowledge.kb_server import kb_server
from mcp_server.integrations.email_server import email_server
from mcp_server.integrations.voice_server import voice_server
from mcp_server.integrations.chat_server import chat_server
from mcp_server.integrations.ticketing_server import ticketing_server
from mcp_server.integrations.ecommerce_server import ecommerce_server
from mcp_server.integrations.crm_server import crm_server
from mcp_server.tools.analytics_server import analytics_server
from mcp_server.tools.monitoring_server import monitoring_server
from mcp_server.tools.notification_server import notification_server
from mcp_server.tools.compliance_server import compliance_server
from mcp_server.tools.sla_server import sla_server

# ── All sub-servers to register at startup ─────────────────────
ALL_SUB_SERVERS: list[MCPServerBase] = [
    # Knowledge
    faq_server,
    rag_server,
    kb_server,
    # Integrations
    email_server,
    voice_server,
    chat_server,
    ticketing_server,
    ecommerce_server,
    crm_server,
    # Tools
    analytics_server,
    monitoring_server,
    notification_server,
    compliance_server,
    sla_server,
]


# ═══════════════════════════════════════════════════════════════════
# Lifespan — startup / shutdown
# ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: register all sub-servers and tools.

    Startup:
    - Configure structured logging
    - Register all sub-servers and their tools into the global registry
    - Check backend connectivity

    Shutdown:
    - Log shutdown event
    """
    settings = get_settings()
    configure_logging(settings.ENVIRONMENT)
    logger = get_logger("lifespan")

    # ── Register all sub-servers ────────────────────────────────
    for server in ALL_SUB_SERVERS:
        try:
            server_info = server.get_server_info()
            registry.register_server(server_info)
            server.register_tools(registry)
            logger.info(
                "sub_server_registered",
                server=server.name,
                tools_registered=server_info.tool_count,
            )
        except Exception as exc:
            logger.error(
                "sub_server_registration_failed",
                server=server.name,
                error=str(exc),
            )

    # ── Check backend connectivity ──────────────────────────────
    backend_reachable = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.BACKEND_URL}/health")
            backend_reachable = resp.status_code == 200
    except Exception as exc:
        logger.warning(
            "backend_unreachable",
            backend_url=settings.BACKEND_URL,
            error=str(exc),
        )

    # ── Store settings on app state ─────────────────────────────
    app.state.settings = settings
    app.state.start_time = time.time()
    app.state.backend_reachable = backend_reachable

    logger.info(
        "mcp_startup",
        environment=settings.ENVIRONMENT,
        version="1.0.0",
        servers_registered=registry.total_servers,
        tools_registered=registry.total_tools,
        backend_reachable=backend_reachable,
    )

    yield

    logger.info("mcp_shutdown")


# ═══════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="PARWA MCP Server",
    description="Model Context Protocol server for external AI tool integrations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ── CORS Middleware ────────────────────────────────────────────

# M-23 FIX: Never fall back to ["*"] — fail closed with empty list
# so that all cross-origin requests are rejected when origins are misconfigured.
try:
    _settings = get_settings()
    _cors_origins = _settings.cors_origin_list
    if not _cors_origins:
        from mcp_server.base_server import get_logger as _get_logger
        _get_logger("cors").warning(
            "cors_origin_list is empty — CORS will deny all cross-origin requests"
        )
        _cors_origins = []
except Exception:
    _cors_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── C-04: MCP Auth Token Enforcement Middleware ────────────────

# Paths that bypass MCP auth (health checks)
_MCP_AUTH_SKIP_PATHS = {"/health", "/"}

from starlette.middleware.base import BaseHTTPMiddleware


class MCPAuthTokenMiddleware(BaseHTTPMiddleware):
    """Enforces MCP_AUTH_TOKEN on all endpoints except /health and /.

    Validates the Bearer token from the Authorization header against
    the configured MCP_AUTH_TOKEN. In development mode (no token set),
    all requests are allowed through with a warning.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and root endpoints
        if request.url.path in _MCP_AUTH_SKIP_PATHS:
            return await call_next(request)

        settings = get_settings()
        expected_token = settings.MCP_AUTH_TOKEN

        # If no token configured, allow in non-production (dev convenience)
        if not expected_token:
            if settings.ENVIRONMENT == "production":
                return JSONResponse(
                    status_code=500,
                    content={"error": "MCP_AUTH_TOKEN not configured in production"},
                )
            # Development: allow without token but log warning
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "details": "Missing or invalid Authorization header. Use: Bearer <token>",
                },
            )

        provided_token = auth_header[7:]

        # Constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(provided_token, expected_token):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        return await call_next(request)


app.add_middleware(MCPAuthTokenMiddleware)


# ── Exception Handlers ─────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all uncaught exceptions — structured JSON, no stack traces."""
    logger = get_logger("error_handler")
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            }
        ).model_dump(),
    )


# ═══════════════════════════════════════════════════════════════════
# MCP Protocol Endpoints
# ═══════════════════════════════════════════════════════════════════


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: Request):
    """Health check endpoint for Docker container monitoring."""
    settings = request.app.state.settings
    start_time = getattr(request.app.state, "start_time", time.time())
    backend_reachable = getattr(request.app.state, "backend_reachable", None)

    return HealthResponse(
        status="healthy",
        service="parwa-mcp",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        uptime_seconds=time.time() - start_time,
        registered_servers=registry.total_servers,
        registered_tools=registry.total_tools,
        backend_reachable=backend_reachable,
    )


@app.get("/", tags=["System"])
async def root(request: Request):
    """Root endpoint with service information."""
    return {
        "service": "PARWA MCP Server",
        "version": "1.0.0",
        "servers": registry.total_servers,
        "tools": registry.total_tools,
        "docs": "/health",
    }


@app.get("/mcp/tools", response_model=ToolsListResponse, tags=["MCP Protocol"])
async def list_tools(
    category: ToolCategory | None = None,
    server: str | None = None,
):
    """List all available MCP tools.

    Optionally filter by category (knowledge, integration, tool)
    or by server name.
    """
    tools = registry.list_tools(category=category, server=server)
    categories = list(set(t.category.value for t in registry.list_tools()))

    return ToolsListResponse(
        tools=tools,
        total=len(tools),
        categories=categories,
    )


@app.post("/mcp/tools/{tool_name}/invoke", response_model=ToolInvokeResponse, tags=["MCP Protocol"])
async def invoke_tool(tool_name: str, request: ToolInvokeRequest):
    """Invoke a specific MCP tool by name.

    The request body can override the tool_name from the URL path.
    The tool handler receives parameters and context, and returns
    a structured response with data or error.
    """
    logger = get_logger("mcp.invoke")

    # Look up the tool and handler
    tool = registry.get_tool(tool_name)
    handler = registry.get_handler(tool_name)

    if not tool:
        logger.warning("tool_not_found", tool_name=tool_name)
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=f"Tool '{tool_name}' not found",
        )

    if not handler:
        logger.warning("tool_no_handler", tool_name=tool_name)
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=f"Tool '{tool_name}' has no invocation handler",
        )

    # Merge parameters: URL tool_name takes precedence
    merged_params = {**request.parameters}
    if request.tool_name and request.tool_name != tool_name:
        merged_params["_original_tool_name"] = request.tool_name

    logger.info("tool_invoked", tool_name=tool_name)

    try:
        result = await handler(
            parameters=merged_params,
            context=request.context,
        )
        return result
    except Exception as exc:
        logger.error(
            "tool_invocation_error",
            tool_name=tool_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=f"Tool invocation failed: {str(exc)}",
        )


@app.get("/mcp/servers", response_model=ServersListResponse, tags=["MCP Protocol"])
async def list_servers():
    """List all registered MCP sub-servers."""
    servers = registry.list_servers()
    return ServersListResponse(
        servers=servers,
        total=len(servers),
    )


@app.get(
    "/mcp/servers/{server_name}/tools",
    response_model=ToolsListResponse,
    tags=["MCP Protocol"],
)
async def list_server_tools(server_name: str):
    """List tools registered under a specific sub-server."""
    server = registry.get_server(server_name)
    if not server:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error={
                    "code": "NOT_FOUND",
                    "message": f"Server '{server_name}' not found",
                    "details": None,
                }
            ).model_dump(),
        )

    tools = registry.list_tools(server=server_name)
    return ToolsListResponse(
        tools=tools,
        total=len(tools),
        categories=[server.category.value],
    )


# ═══════════════════════════════════════════════════════════════════
# Include Sub-server Routers
# ═══════════════════════════════════════════════════════════════════

# Knowledge sub-servers
app.include_router(faq_server.get_router())
app.include_router(rag_server.get_router())
app.include_router(kb_server.get_router())

# Integration sub-servers
app.include_router(email_server.get_router())
app.include_router(voice_server.get_router())
app.include_router(chat_server.get_router())
app.include_router(ticketing_server.get_router())
app.include_router(ecommerce_server.get_router())
app.include_router(crm_server.get_router())

# Tool sub-servers
app.include_router(analytics_server.get_router())
app.include_router(monitoring_server.get_router())
app.include_router(notification_server.get_router())
app.include_router(compliance_server.get_router())
app.include_router(sla_server.get_router())


# ═══════════════════════════════════════════════════════════════════
# Direct Run
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "mcp_server.main:app",
        host=settings.MCP_SERVER_HOST,
        port=settings.MCP_SERVER_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
