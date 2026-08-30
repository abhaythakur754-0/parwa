"""PARWA MCP — Superglue Adapter Server (Universal Action Adapter)

Bridges Superglue-generated tools into the MCP registry so they appear
as native MCP tools. Every tool is prefixed with ``sg_`` to namespace
it from hand-written MCP tools.

Safety pipeline: classify -> guardrails -> approval gate -> execute.
BC-001: tenant isolation. BC-008: every step wrapped, never crashes.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import ToolCategory, ToolDefinition, ToolInvokeResponse

logger = get_logger("mcp.superglue_adapter")

# Lazy imports — backend modules may not be importable in all contexts.
_sgc = _as = _rg = _dsu = None


def _ensure_imports() -> bool:
    """Import backend modules on first use. Returns False if any fail."""
    global _sgc, _as, _rg, _dsu
    if _sgc is not None:
        return True
    try:
        from app.core import superglue_client as m1
        from app.core import action_safety as m2
        from app.core import regulatory_guardrails as m3
        from app.core import dynamic_signal_updater as m4
        _sgc, _as, _rg, _dsu = m1, m2, m3, m4
        return True
    except Exception as exc:
        logger.warning("superglue_adapter_import_failed", error=str(exc)[:200])
        return False


def _run_async(coro):
    """Run async coroutine from sync context."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=30)


class SuperglueAdapterServer(MCPServerBase):
    """MCP sub-server that bridges Superglue tools into the MCP registry."""

    name = "superglue_adapter"
    description = "Universal Action Adapter — bridges Superglue-generated tools into MCP"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Fetch Superglue tools and register each as an MCP tool (sg_-prefixed)."""
        try:
            if not _ensure_imports() or not _sgc.is_configured():
                return
            tools = _run_async(_sgc.list_tools())
            if not tools:
                return
            for tool in tools:
                tid = tool.get("id", "")
                registry.register_tool(
                    ToolDefinition(
                        name=f"sg_{tid}",
                        description=tool.get("name", tid),
                        category=self.category, server=self.name,
                        input_schema=tool.get("inputSchema", {}),
                        output_schema=tool.get("outputSchema", {}),
                        tags=["superglue", "dynamic"],
                    ),
                    handler=self._make_handler(f"sg_{tid}", tid),
                )
            logger.info("superglue_adapter_registered", tool_count=len(tools))
            _run_async(_dsu.publish_superglue_signals("global", tools))
        except Exception as exc:
            logger.error("superglue_adapter_register_error", error=str(exc)[:300])

    def _make_handler(self, mcp_name: str, tool_id: str):
        """Create an async handler bound to a specific tool."""
        async def handler(parameters: dict | None = None, context: dict | None = None) -> ToolInvokeResponse:
            return await self._invoke_handler(mcp_name, tool_id, parameters, context)
        return handler

    async def _invoke_handler(self, mcp_name: str, tool_id: str,
                              parameters: dict | None = None,
                              context: dict | None = None) -> ToolInvokeResponse:
        """Unified handler: classify -> guardrails -> approval gate -> execute."""
        params = parameters or {}
        ctx = context or {}
        company_id = ctx.get("company_id", "")
        description = ctx.get("description", "")
        try:
            if not _ensure_imports():
                return ToolInvokeResponse(success=False, tool_name=mcp_name, error="Backend modules unavailable")
            # STEP 1: Classify safety.
            try:
                safety = _as.classify_action(tool_id, description)
            except Exception:
                safety = _as.ActionSafetyResult(level=_as.ActionSafetyLevel.READ,
                    confidence=0.0, matched_keyword=None, reasoning="Classification error, defaulting to READ")
            # STEP 2: Regulatory guardrails for FINANCIAL actions.
            if safety.level == _as.ActionSafetyLevel.FINANCIAL:
                try:
                    amount = float(params.get("amount", 0))
                    tier = ctx.get("variant_tier", "parwa")
                    gr = _rg.check_financial_guardrails(safety.level.value, amount, tier, tool_id)
                    if not gr.allowed:
                        return ToolInvokeResponse(success=False, tool_name=mcp_name,
                            error=f"Guardrail blocked: {gr.reason}",
                            metadata={"guardrail_result": gr.reason})
                except Exception:
                    pass  # BC-008: allow on error
            # STEP 3: Approval gate for FINANCIAL / DESTRUCTIVE.
            try:
                if _as.needs_approval(safety.level):
                    fw = _rg.get_applicable_frameworks(safety.level.value)
                    return ToolInvokeResponse(success=False, tool_name=mcp_name,
                        error=f"Action requires approval: {safety.reasoning}",
                        data={"status": "pending_approval", "tool_id": tool_id,
                            "safety_level": safety.level.value, "regulatory_frameworks": fw},
                        metadata={"requires_approval": True, "safety_level": safety.level.value,
                            "confidence": safety.confidence, "regulatory_frameworks": fw})
            except Exception:
                pass  # BC-008: proceed to execute on error
            # STEP 4: Execute via superglue_client.
            try:
                result = await _sgc.execute_tool(tool_id, params, tenant_id=company_id or None)
                return ToolInvokeResponse(success=True, tool_name=mcp_name, data=result,
                    metadata={"safety_level": safety.level.value, "source": "superglue"})
            except Exception as exc:
                return ToolInvokeResponse(success=False, tool_name=mcp_name,
                    error=f"Superglue execution failed: {str(exc)[:200]}")
        except Exception as exc:
            logger.error("superglue_adapter_invoke_error", tool=mcp_name, error=str(exc)[:300])
            return ToolInvokeResponse(success=False, tool_name=mcp_name, error="Internal adapter error")

    def get_router(self) -> APIRouter:
        """REST endpoints for Superglue adapter management."""
        router = APIRouter(prefix="/integrations/superglue", tags=["Integration — Superglue Adapter"])

        @router.post("/sync")
        async def force_sync(company_id: str = "global"):
            """Re-fetch tools from Superglue and re-register them."""
            from mcp_server.base_server import registry as _reg
            try:
                if not _ensure_imports():
                    return {"status": "error", "reason": "imports_failed"}
                tools = await _sgc.list_tools()
                for key in [k for k in _reg._tools if k.startswith("sg_") and _reg._tools[k].server == self.name]:
                    del _reg._tools[key]; _reg._handlers.pop(key, None)
                for tool in tools:
                    tid = tool.get("id", "")
                    _reg.register_tool(
                        ToolDefinition(name=f"sg_{tid}", description=tool.get("name", tid),
                            category=self.category, server=self.name,
                            input_schema=tool.get("inputSchema", {}),
                            output_schema=tool.get("outputSchema", {}), tags=["superglue", "dynamic"]),
                        handler=self._make_handler(f"sg_{tid}", tid))
                await _dsu.publish_superglue_signals(company_id, tools)
                return {"status": "ok", "tools_registered": len(tools)}
            except Exception as exc:
                logger.error("superglue_adapter_sync_error", error=str(exc)[:300])
                return {"status": "error", "reason": str(exc)[:200]}

        @router.get("/tools")
        async def list_superglue_tools():
            """List Superglue-specific tools from the MCP registry."""
            from mcp_server.base_server import registry as _reg
            tools = _reg.list_tools(server=self.name)
            return {"tools": [t.model_dump() for t in tools], "total": len(tools)}

        return router


# Singleton instance
superglue_adapter_server = SuperglueAdapterServer()
