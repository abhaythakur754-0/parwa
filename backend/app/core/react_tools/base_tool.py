"""
PARWA ReAct Tool Base Classes  (F-157)

Provides the base framework for ReAct (Reasoning + Acting) tool adapters.
Each tool wraps an external system API and exposes discrete *actions*
that the LLM agent can invoke.

This module is imported by both the registry (__init__.py) and individual
tool modules to avoid circular imports.

GAP-004: Every execute() call is wrapped in asyncio.wait_for(timeout=10)
         and limited by asyncio.Semaphore(5). MAX_RETRIES=1.
BC-001:  All tool executions are scoped to company_id.
BC-008:  Tools never crash — always return a ToolResult.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Data Classes ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationResult:
    """Result of parameter validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    missing_params: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Structured result returned by every tool action."""
    success: bool
    error: str | None
    data: dict | list | None
    execution_time_ms: int
    action: str = ""
    tool_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to plain dict for JSON responses."""
        return {
            "success": self.success,
            "error": self.error,
            "data": self.data,
            "execution_time_ms": self.execution_time_ms,
            "action": self.action,
            "tool_name": self.tool_name,
        }


@dataclass
class ActionSchema:
    """JSON Schema descriptor for a single tool action."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    required_params: list[str]
    returns: str


@dataclass
class ToolSchema:
    """JSON Schema descriptor for a complete tool."""
    tool_name: str
    description: str
    actions: list[ActionSchema]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "description": self.description,
            "actions": [
                {
                    "name": a.name,
                    "description": a.description,
                    "parameters": a.parameters,
                    "required_params": a.required_params,
                    "returns": a.returns,
                }
                for a in self.actions
            ],
        }


@dataclass
class ToolCall:
    """A single tool execution request for parallel batching."""
    tool_name: str
    action: str
    company_id: str
    params: dict[str, Any] = field(default_factory=dict)


# ── Base Tool ──────────────────────────────────────────────────────


class BaseReactTool(ABC):
    """
    Base class for all ReAct tool adapters.

    GAP-004: All execute() calls use asyncio.wait_for() with 10 s timeout
    and are limited by a class-level Semaphore(5).
    BC-001:  Every action is scoped to *company_id*.
    BC-008:  execute() never raises — returns ToolResult on any failure.
    """

    EXECUTION_TIMEOUT: int = 10  # seconds — GAP-004
    MAX_RETRIES: int = 1
    MAX_CONCURRENT: int = 5

    _semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # ── Abstract interface ───────────────────────────────────────

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
    @abstractmethod
    def actions(self) -> list[str]:
        """List of action names this tool supports."""
        ...

    @abstractmethod
    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """
        Subclass-specific execution logic.

        Implementations should validate *action* and *params* before
        performing any I/O. Must return a ToolResult.
        """
        ...

    # ── Public API ──────────────────────────────────────────────

    async def execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """
        Execute a tool action with timeout and concurrency limits.

        GAP-004: Wraps _do_execute in asyncio.wait_for(timeout=10).
        Semaphore(5) limits concurrent executions per tool class.
        MAX_RETRIES=1 means one retry on transient failure.
        """
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(1, self.MAX_RETRIES + 2):
                start = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        self._do_execute(action, company_id, **params),
                        timeout=self.EXECUTION_TIMEOUT,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    result.execution_time_ms = elapsed_ms
                    result.action = action
                    result.tool_name = self.name
                    if attempt > 1:
                        logger.info(
                            "Tool %s action %s succeeded on attempt %d",
                            self.name,
                            action,
                            attempt,
                        )
                    return result
                except asyncio.TimeoutError:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    last_error = None
                    logger.warning(
                        "Tool %s action %s timed out after %dms (attempt %d)",
                        self.name,
                        action,
                        elapsed_ms,
                        attempt,
                    )
                    if attempt == self.MAX_RETRIES + 1:
                        return ToolResult(
                            success=False,
                            error=f"Tool execution timed out after {self.EXECUTION_TIMEOUT}s",
                            data=None,
                            execution_time_ms=elapsed_ms,
                            action=action,
                            tool_name=self.name,
                        )
                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    last_error = exc
                    logger.warning(
                        "Tool %s action %s failed: %s (attempt %d)",
                        self.name,
                        action,
                        exc,
                        attempt,
                    )
                    if attempt == self.MAX_RETRIES + 1:
                        return ToolResult(
                            success=False,
                            error=str(exc),
                            data=None,
                            execution_time_ms=elapsed_ms,
                            action=action,
                            tool_name=self.name,
                        )
        # Unreachable, but satisfy type-checkers
        return ToolResult(
            success=False,
            error="Unexpected execution path",
            data=None,
            execution_time_ms=0,
            action=action,
            tool_name=self.name,
        )

    # ── Validation ──────────────────────────────────────────────

    def validate_params(self, action: str, params: dict[str, Any]) -> ValidationResult:
        """
        Validate parameters against the action's schema.

        Returns a ValidationResult with details about missing or
        invalid parameters.
        """
        schema = self.get_schema()
        action_schema = None
        for a in schema.actions:
            if a.name == action:
                action_schema = a
                break

        if action_schema is None:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown action: {action}"],
            )

        errors: list[str] = []
        missing: list[str] = []

        for rp in action_schema.required_params:
            if rp not in params or params[rp] is None:
                missing.append(rp)

        if missing:
            errors.append(f"Missing required parameters: {', '.join(missing)}")

        # Validate types via JSON Schema "type" hints
        param_defs = action_schema.parameters.get("properties", {})
        for key, value in params.items():
            if key in param_defs and value is not None:
                expected = param_defs[key].get("type", "")
                if expected == "string" and not isinstance(value, str):
                    errors.append(f"Parameter '{key}' must be a string")
                elif expected == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter '{key}' must be an integer")
                elif expected == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter '{key}' must be a number")
                elif expected == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter '{key}' must be a boolean")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            missing_params=missing,
        )

    # ── Schema ──────────────────────────────────────────────────

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Return the full JSON Schema descriptor for this tool."""
        ...

    # ── Health ──────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verify that the tool's backing service is reachable."""
        try:
            result = await asyncio.wait_for(
                self._do_execute(
                    "__health_check__",
                    company_id="__system__",
                ),
                timeout=5,
            )
            return result.success
        except Exception:
            return False
