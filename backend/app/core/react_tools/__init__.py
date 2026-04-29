"""
PARWA ReAct Tool Integrations — F-157

Provides the registry and all tool implementations for the ReAct
(Reasoning + Acting) pattern. Each tool wraps an external system API
and exposes discrete *actions* the LLM agent can invoke.

Architecture
------------
- BaseReactTool   — abstract base with timeout, semaphore, validation  (base.py)
- ToolResult      — structured result dataclass                         (base.py)
- ToolSchema      — JSON Schema descriptor for a tool                  (base.py)
- ActionSchema    — JSON Schema descriptor for a single action         (base.py)
- ReActToolRegistry — singleton registry for lookup, listing, execution
- OrderTool       — order management actions
- BillingTool     — billing & subscription actions
- CRMTool         — CRM & customer actions
- TicketTool      — support ticket actions

GAP-004: Every execute() call is wrapped in asyncio.wait_for(timeout=10)
         and limited by asyncio.Semaphore(5). MAX_RETRIES=1.
BC-001:  All tool executions are scoped to company_id.
BC-008:  Tools never crash — always return a ToolResult.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# Base classes (no circular import — base.py has no deps on other tool modules)
from .base import (
    ActionSchema,
    BaseReactTool,
    ToolCall,
    ToolResult,
    ToolSchema,
    ValidationResult,
)

# Tool implementations
from .order_tool import OrderTool
from .billing_tool import BillingTool
from .crm_tool import CRMTool
from .ticket_tool import TicketTool

logger = logging.getLogger(__name__)


# ── Registry ───────────────────────────────────────────────────────


class ReActToolRegistry:
    """
    Registry for all available ReAct tools.

    Supports tool lookup, listing, single/parallel execution,
    and schema introspection.

    BC-001: All executions require company_id.
    BC-008: execute_tool never raises.
    """

    MAX_PARALLEL: int = 3

    def __init__(self) -> None:
        self._tools: dict[str, BaseReactTool] = {}
        self._initialized = False

    # ── Registration ────────────────────────────────────────────

    async def register_tool(self, tool: BaseReactTool) -> None:
        """Register a tool instance by its *name*."""
        self._tools[tool.name] = tool
        logger.info(
            "Registered ReAct tool: %s (%d actions)",
            tool.name,
            len(tool.actions),
        )

    def register_tool_sync(self, tool: BaseReactTool) -> None:
        """Synchronous convenience wrapper for register_tool."""
        self._tools[tool.name] = tool
        logger.info(
            "Registered ReAct tool: %s (%d actions)",
            tool.name,
            len(tool.actions),
        )

    # ── Query ───────────────────────────────────────────────────

    async def get_tool(self, tool_name: str) -> BaseReactTool | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(tool_name)

    async def list_tools(self) -> list[ToolSchema]:
        """Return schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def get_available_actions(self) -> dict[str, list[str]]:
        """Return {tool_name: [action1, action2, ...]} for all tools."""
        return {name: tool.actions for name, tool in self._tools.items()}

    # ── Execution ───────────────────────────────────────────────

    async def execute_tool(
        self,
        tool_name: str,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """
        Execute a single tool action by name.

        BC-008: Returns a ToolResult (never raises).
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                data=None,
                execution_time_ms=0,
                action=action,
                tool_name=tool_name,
            )

        if action not in tool.actions:
            return ToolResult(
                success=False,
                error=f"Unknown action '{action}' for tool '{tool_name}'. "
                f"Available: {', '.join(tool.actions)}",
                data=None,
                execution_time_ms=0,
                action=action,
                tool_name=tool_name,
            )

        validation = tool.validate_params(action, params)
        if not validation.is_valid:
            return ToolResult(
                success=False,
                error=f"Validation failed: {'; '.join(validation.errors)}",
                data={
                    "missing_params": validation.missing_params,
                },
                execution_time_ms=0,
                action=action,
                tool_name=tool_name,
            )

        return await tool.execute(action, company_id, **params)

    async def execute_parallel(
        self,
        calls: list[ToolCall],
    ) -> list[ToolResult]:
        """
        Execute multiple tool calls concurrently (max 3 at a time).

        Each call is independently safe — failures do not affect
        other calls.
        """

        async def _safe_execute(call: ToolCall) -> ToolResult:
            try:
                return await self.execute_tool(
                    tool_name=call.tool_name,
                    action=call.action,
                    company_id=call.company_id,
                    **call.params,
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected error in parallel execution for %s/%s",
                    call.tool_name,
                    call.action,
                )
                return ToolResult(
                    success=False,
                    error=f"Unexpected error: {exc}",
                    data=None,
                    execution_time_ms=0,
                    action=call.action,
                    tool_name=call.tool_name,
                )

        # Limit concurrency to MAX_PARALLEL
        semaphore = asyncio.Semaphore(self.MAX_PARALLEL)

        async def _limited_execute(call: ToolCall) -> ToolResult:
            async with semaphore:
                return await _safe_execute(call)

        tasks = [_limited_execute(call) for call in calls]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    # ── Initialisation ──────────────────────────────────────────

    async def initialize_defaults(self) -> None:
        """Register all default PARWA tool implementations."""
        if self._initialized:
            return
        await self.register_tool(OrderTool())
        await self.register_tool(BillingTool())
        await self.register_tool(CRMTool())
        await self.register_tool(TicketTool())
        self._initialized = True
        logger.info(
            "ReActToolRegistry initialised with %d tools",
            len(self._tools),
        )

    def initialize_defaults_sync(self) -> None:
        """Synchronous convenience wrapper for initialize_defaults."""
        if self._initialized:
            return
        self.register_tool_sync(OrderTool())
        self.register_tool_sync(BillingTool())
        self.register_tool_sync(CRMTool())
        self.register_tool_sync(TicketTool())
        self._initialized = True
        logger.info(
            "ReActToolRegistry initialised with %d tools (sync)",
            len(self._tools),
        )


# ── Module-level singleton ────────────────────────────────────────

default_registry = ReActToolRegistry()

__all__ = [
    # Base classes
    "BaseReactTool",
    "ReActToolRegistry",
    # Data classes
    "ToolResult",
    "ToolSchema",
    "ActionSchema",
    "ValidationResult",
    "ToolCall",
    # Tool implementations
    "OrderTool",
    "BillingTool",
    "CRMTool",
    "TicketTool",
    # Singleton
    "default_registry",
]
