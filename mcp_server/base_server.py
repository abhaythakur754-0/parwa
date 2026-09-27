"""
PARWA MCP Server — Base Server

Provides the core MCP (Model Context Protocol) server infrastructure:
- Tool registry (register, discover, invoke)
- Sub-server registry
- Shared logging configuration

All sub-servers inherit from MCPServerBase and register their tools
at startup. The main FastAPI app collects all routers and the global
tool registry provides the MCP protocol endpoints.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

import structlog
from fastapi import APIRouter

from mcp_server.models import (
    ServerInfo,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
    ToolStatus,
)

# Type alias for tool handler functions
ToolHandler = Callable[..., Coroutine[Any, Any, ToolInvokeResponse]]


class MCPRegistry:
    """Global registry for all MCP tools and sub-servers.

    Thread-safe singleton that holds tool definitions and server info.
    Used by the main app to serve MCP protocol endpoints.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._servers: dict[str, ServerInfo] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._start_time: float = time.time()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    def register_tool(
        self,
        tool: ToolDefinition,
        handler: ToolHandler | None = None,
    ) -> None:
        """Register a tool and its invocation handler."""
        self._tools[tool.name] = tool
        if handler is not None:
            self._handlers[tool.name] = handler
        # Update server tool count
        if tool.server in self._servers:
            self._servers[tool.server].tool_count = len(
                [t for t in self._tools.values() if t.server == tool.server]
            )

    def register_server(self, server: ServerInfo) -> None:
        """Register a sub-server."""
        self._servers[server.name] = server

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(tool_name)

    def get_handler(self, tool_name: str) -> ToolHandler | None:
        """Get a tool's invocation handler."""
        return self._handlers.get(tool_name)

    def list_tools(
        self,
        category: ToolCategory | None = None,
        server: str | None = None,
    ) -> list[ToolDefinition]:
        """List tools, optionally filtered by category or server."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if server:
            tools = [t for t in tools if t.server == server]
        return tools

    def list_servers(self) -> list[ServerInfo]:
        """List all registered sub-servers."""
        return list(self._servers.values())

    def get_server(self, server_name: str) -> ServerInfo | None:
        """Get a server by name."""
        return self._servers.get(server_name)

    @property
    def total_tools(self) -> int:
        return len(self._tools)

    @property
    def total_servers(self) -> int:
        return len(self._servers)


class MCPServerBase(ABC):
    """Base class for all MCP sub-servers.

    Sub-servers inherit from this class, define their tools in
    register_tools(), and expose a FastAPI router via get_router().

    Example::

        class FAQServer(MCPServerBase):
            name = "faq_server"
            description = "FAQ knowledge queries"

            def register_tools(self, registry: MCPRegistry) -> None:
                registry.register_tool(
                    ToolDefinition(name="faq_search", ...),
                    handler=self.handle_faq_search,
                )

            def get_router(self) -> APIRouter:
                router = APIRouter(prefix="/knowledge/faq", tags=["FAQ"])
                @router.post("/search")
                async def search(req: FAQSearchRequest):
                    ...
                return router
    """

    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.TOOL
    version: str = "1.0.0"

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define a 'name' class attribute")

    @abstractmethod
    def register_tools(self, registry: MCPRegistry) -> None:
        """Register all tools provided by this sub-server.

        Called once at application startup. Sub-classes must
        register their ToolDefinition instances and handlers.
        """
        ...

    def get_router(self) -> APIRouter:
        """Return the FastAPI router for this sub-server's endpoints.

        Override to add custom REST endpoints beyond the MCP protocol.
        The default returns an empty router.
        """
        return APIRouter()

    def get_server_info(self) -> ServerInfo:
        """Get the ServerInfo for this sub-server."""
        return ServerInfo(
            name=self.name,
            description=self.description,
            category=self.category,
            version=self.version,
        )


# ═══════════════════════════════════════════════════════════════════
# Logging Configuration (mirrors backend/app/logger.py)
# ═══════════════════════════════════════════════════════════════════


def _add_env_info(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add environment info to log events."""
    event_dict["environment"] = os.getenv("ENVIRONMENT", "unknown")
    event_dict["service"] = "parwa-mcp"
    return event_dict


def configure_logging(environment: str = "development") -> None:
    """Configure structlog based on environment."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _add_env_info,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    level = logging.DEBUG if environment != "production" else logging.INFO
    root_logger.setLevel(level)


def get_logger(name: str) -> Any:
    """Get a bound structlog logger with module name."""
    return structlog.get_logger(name)


# ═══════════════════════════════════════════════════════════════════
# Global Registry Singleton
# ═══════════════════════════════════════════════════════════════════

# Global registry instance — all sub-servers register into this
registry = MCPRegistry()
