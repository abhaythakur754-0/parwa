"""
PARWA MCP Base Server.

Abstract base class for all Model Context Protocol servers.
Provides common functionality for tool registration, routing,
health checks, and parameter validation.

CRITICAL: This is the foundation for ALL MCP servers in Week 8.
All servers must inherit from BaseMCPServer.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime, timezone
from enum import Enum
import asyncio
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class MCPServerState(Enum):
    """MCP Server state enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ToolDefinition:
    """
    Definition of an MCP tool.

    Attributes:
        name: Tool name (unique within server)
        description: Tool description for AI understanding
        parameters_schema: JSON schema for parameters
        handler: Async function to handle tool calls
    """
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: Callable[..., Awaitable[Dict[str, Any]]]


class ToolResult(BaseModel):
    """
    Result from an MCP tool execution.

    Attributes:
        success: Whether the tool call succeeded
        data: Result data if successful
        error: Error message if failed
        execution_time_ms: Time taken to execute
    """
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = Field(default=0.0)

    model_config = ConfigDict(
        use_enum_values=True
    )


class MCPServerConfig(BaseModel):
    """
    Configuration for MCP Server.

    Attributes:
        name: Server name
        version: Server version
        max_response_time_ms: Maximum allowed response time (default 2000ms)
        rate_limit_per_minute: Maximum tool calls per minute (default 100)
        enable_logging: Whether to log all tool calls
    """
    name: str = Field(default="unknown")
    version: str = Field(default="1.0.0")
    max_response_time_ms: int = Field(default=2000, ge=100, le=10000)
    rate_limit_per_minute: int = Field(default=100, ge=1, le=1000)
    enable_logging: bool = Field(default=True)

    model_config = ConfigDict(
        use_enum_values=True
    )


class BaseMCPServer(ABC):
    """
    Abstract base class for all MCP servers.

    Provides:
    - Server lifecycle management (start/stop)
    - Tool registration and routing
    - Parameter validation
    - Health checks
    - Rate limiting
    - Response time tracking

    All MCP servers must inherit from this class and implement
    the _register_tools() method to define their available tools.

    Example:
        class MyServer(BaseMCPServer):
            def _register_tools(self) -> None:
                self.register_tool(
                    name="my_tool",
                    description="Does something",
                    parameters_schema={"type": "object", "properties": {}},
                    handler=self._handle_my_tool
                )

            async def _handle_my_tool(self, params: dict) -> dict:
                return {"result": "success"}
    """

    DEFAULT_TIMEOUT = 2.0  # 2 seconds max response time

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize MCP server.

        Args:
            name: Server name (used in logging and health checks)
            config: Optional configuration dictionary
        """
        self._name = name
        self._config = MCPServerConfig(
            name=name,
            **(config or {})
        )
        self._state = MCPServerState.STOPPED
        self._tools: Dict[str, ToolDefinition] = {}
        self._start_time: Optional[datetime] = None
        self._tool_call_count = 0
        self._error_count = 0
        self._total_response_time_ms = 0.0
        self._last_minute_calls: List[float] = []  # Timestamps for rate limiting

        # Register tools defined by subclass
        self._register_tools()

        logger.info({
            "event": "mcp_server_created",
            "server": self._name,
            "tools_registered": len(self._tools),
        })

    @property
    def name(self) -> str:
        """Get server name."""
        return self._name

    @property
    def state(self) -> MCPServerState:
        """Get current server state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._state == MCPServerState.RUNNING

    @property
    def tools(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    @abstractmethod
    def _register_tools(self) -> None:
        """
        Register all tools for this server.

        Subclasses must implement this method to register
        their available tools using self.register_tool().

        Example:
            def _register_tools(self) -> None:
                self.register_tool(
                    name="search",
                    description="Search for items",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    },
                    handler=self._handle_search
                )
        """
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> None:
        """
        Register a tool with the server.

        Args:
            name: Tool name (must be unique within server)
            description: Tool description for AI understanding
            parameters_schema: JSON schema for parameter validation
            handler: Async function to handle tool calls

        Raises:
            ValueError: If tool name already registered
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")

        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler
        )

        logger.debug({
            "event": "tool_registered",
            "server": self._name,
            "tool": name,
        })

    async def start(self) -> None:
        """
        Start the MCP server.

        Sets state to RUNNING and records start time.

        Raises:
            Exception: If startup fails
        """
        if self._state == MCPServerState.RUNNING:
            logger.warning({
                "event": "server_already_running",
                "server": self._name,
            })
            return

        self._state = MCPServerState.STARTING

        try:
            # Subclasses can override _on_start for custom initialization
            await self._on_start()

            self._state = MCPServerState.RUNNING
            self._start_time = datetime.now(timezone.utc)

            logger.info({
                "event": "mcp_server_started",
                "server": self._name,
                "tools_available": list(self._tools.keys()),
            })

        except Exception as e:
            self._state = MCPServerState.ERROR
            self._error_count += 1

            logger.error({
                "event": "mcp_server_start_failed",
                "server": self._name,
                "error": str(e),
            })
            raise

    async def _on_start(self) -> None:
        """
        Hook for custom startup logic.

        Override in subclasses to perform custom initialization
        such as connecting to external services.
        """
        pass

    async def stop(self) -> None:
        """
        Stop the MCP server gracefully.

        Sets state to STOPPED and clears start time.
        """
        if self._state == MCPServerState.STOPPED:
            return

        self._state = MCPServerState.STOPPING

        try:
            await self._on_stop()
        except Exception as e:
            logger.error({
                "event": "mcp_server_stop_error",
                "server": self._name,
                "error": str(e),
            })
        finally:
            self._state = MCPServerState.STOPPED
            self._start_time = None

            logger.info({
                "event": "mcp_server_stopped",
                "server": self._name,
            })

    async def _on_stop(self) -> None:
        """
        Hook for custom shutdown logic.

        Override in subclasses to perform custom cleanup
        such as closing connections.
        """
        pass

    async def handle_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> ToolResult:
        """
        Handle a tool call by routing to the appropriate handler.

        Args:
            tool_name: Name of the tool to call
            params: Parameters for the tool

        Returns:
            ToolResult with success status and data or error

        Raises:
            ValueError: If tool not found or params invalid
        """
        start_time = time.time()

        # Check if server is running
        if not self.is_running:
            return ToolResult(
                success=False,
                error="Server is not running",
                execution_time_ms=0.0
            )

        # Check rate limit
        if not self._check_rate_limit():
            return ToolResult(
                success=False,
                error="Rate limit exceeded",
                execution_time_ms=0.0
            )

        # Find tool
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                execution_time_ms=0.0
            )

        # Validate parameters
        validation_error = self._validate_params(params, tool.parameters_schema)
        if validation_error:
            return ToolResult(
                success=False,
                error=validation_error,
                execution_time_ms=0.0
            )

        # Execute tool
        try:
            # Log tool call if enabled
            if self._config.enable_logging:
                logger.info({
                    "event": "mcp_tool_call",
                    "server": self._name,
                    "tool": tool_name,
                    "params_keys": list(params.keys()),
                })

            # Call handler with timeout
            result = await asyncio.wait_for(
                tool.handler(params),
                timeout=self._config.max_response_time_ms / 1000
            )

            execution_time = (time.time() - start_time) * 1000

            # Update stats
            self._tool_call_count += 1
            self._total_response_time_ms += execution_time
            self._last_minute_calls.append(time.time())

            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=execution_time
            )

        except asyncio.TimeoutError:
            self._error_count += 1
            execution_time = (time.time() - start_time) * 1000

            logger.error({
                "event": "mcp_tool_timeout",
                "server": self._name,
                "tool": tool_name,
                "timeout_ms": self._config.max_response_time_ms,
            })

            return ToolResult(
                success=False,
                error=f"Tool call timed out after {self._config.max_response_time_ms}ms",
                execution_time_ms=execution_time
            )

        except Exception as e:
            self._error_count += 1
            execution_time = (time.time() - start_time) * 1000

            logger.error({
                "event": "mcp_tool_error",
                "server": self._name,
                "tool": tool_name,
                "error": str(e),
            })

            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )

    def _validate_params(
        self,
        params: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """
        Validate parameters against JSON schema.

        Args:
            params: Parameters to validate
            schema: JSON schema to validate against

        Returns:
            Error message if validation fails, None if valid
        """
        if not schema:
            return None

        # Check required fields
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in params:
                return f"Missing required parameter: {field}"

        # Check parameter types (basic validation)
        for key, value in params.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get("type")

                if expected_type:
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    expected_python_type = type_map.get(expected_type)
                    if expected_python_type and not isinstance(value, expected_python_type):
                        return f"Parameter '{key}' must be of type {expected_type}"

        return None

    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit is exceeded.

        Returns:
            True if within limit, False if exceeded
        """
        current_time = time.time()

        # Remove calls older than 1 minute
        self._last_minute_calls = [
            ts for ts in self._last_minute_calls
            if current_time - ts < 60
        ]

        # Check if under limit
        return len(self._last_minute_calls) < self._config.rate_limit_per_minute

    async def health_check(self) -> Dict[str, Any]:
        """
        Return server health status.

        Returns:
            Health status dictionary with:
            - healthy: bool
            - state: str
            - uptime_seconds: float
            - tool_call_count: int
            - error_count: int
            - average_response_time_ms: float
            - tools: list of available tools
        """
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        avg_response_time = 0.0
        if self._tool_call_count > 0:
            avg_response_time = self._total_response_time_ms / self._tool_call_count

        return {
            "healthy": self._state == MCPServerState.RUNNING,
            "state": self._state.value,
            "server": self._name,
            "version": self._config.version,
            "uptime_seconds": uptime,
            "tool_call_count": self._tool_call_count,
            "error_count": self._error_count,
            "average_response_time_ms": avg_response_time,
            "tools": self.tools,
            "rate_limit_remaining": (
                self._config.rate_limit_per_minute - len(self._last_minute_calls)
            ),
        }

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema dictionary or None if not found
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        }

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for all registered tools.

        Returns:
            List of tool schema dictionaries
        """
        return [
            self.get_tool_schema(name)
            for name in self.tools
        ]
