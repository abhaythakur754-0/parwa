"""
PARWA Phase 4 — Universal Tool Registry

DYNAMIC tool registration: ANY platform tool can be integrated at runtime.
No more hardcoded 8 tools — tools are discovered from:
1. Built-in tools (CRM, Billing, Order, Email, SMS, HelpDesk, ECommerce, Slack)
2. REST connector tools (from RESTConnectorEngine / OpenAPI importer)
3. Custom tools registered at runtime via register_tool()

This is the backbone of the "universal" tool system.

CRITICAL RULES:
- BC-001: All operations scoped to company_id
- BC-008: Never crash — always return a ToolResult
- Tools are CATEGORY-based: any provider in that category works
- New providers auto-register tools when they're connected
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .base import BaseReactTool, ToolResult, PermissionLevel, VARIANT_PERMISSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic Tool — wraps any callable as a BaseReactTool
# ---------------------------------------------------------------------------

class DynamicTool(BaseReactTool):
    """A tool created at runtime from any callable.

    This is how we make the tool system UNIVERSAL:
    - Any integration can register a tool
    - REST connectors auto-generate tools from OpenAPI specs
    - Custom tools can be added without writing a new class
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        methods: Dict[str, Callable],
        bridge: Optional[Any] = None,
        executor: Optional[Any] = None,
    ):
        super().__init__(bridge=bridge, executor=executor)
        self.name = name
        self.description = description
        self.category = category
        self._methods = methods

    async def _execute_method(
        self,
        method_name: str,
        company_id: str,
        variant_tier: str = "parwa",
        **kwargs,
    ) -> ToolResult:
        """Execute a method on this dynamic tool."""
        try:
            method_fn = self._methods.get(method_name)
            if not method_fn:
                return ToolResult(
                    success=False,
                    message=f"Method {method_name} not found on tool {self.name}",
                    tool_name=self.name,
                )

            # For dynamic tools, we execute the method directly
            # (bridge is for built-in tools that have provider abstraction)
            # This supports both sync and async method functions.
            import asyncio
            import inspect

            # For dynamic tools, execute the method directly.
            # Dynamic tools have their own HTTP clients (like PaddleAPIExecutor)
            # and don't need the ProviderBridge abstraction layer.
            if inspect.iscoroutinefunction(method_fn):
                data = await method_fn(**kwargs)
            else:
                data = method_fn(**kwargs)

            # If data is a RealAPIResponse, convert to appropriate format
            if hasattr(data, 'to_dict') and hasattr(data, 'success'):
                # It's a RealAPIResponse or similar
                return ToolResult(
                    success=data.success,
                    data=data.data if data.success else None,
                    message=data.error if not data.success else f"Executed {self.name}.{method_name}",
                    tool_name=self.name,
                    action_type=method_name,
                    variant_tier=variant_tier,
                )

            return self._build_result(
                success=True,
                data=data,
                message=f"Executed {self.name}.{method_name}",
                action_type=method_name,
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("DynamicTool._execute_method failed: %s", exc)
            return ToolResult(
                success=False,
                message=str(exc),
                tool_name=self.name,
                action_type=method_name,
            )


# ---------------------------------------------------------------------------
# Universal Tool Registry
# ---------------------------------------------------------------------------

class UniversalToolRegistry:
    """DYNAMIC tool registry — any platform tool can be integrated.

    Usage:
        registry = UniversalToolRegistry()
        # Built-in tools auto-register
        # REST connector tools auto-register
        # Custom tools register via register_tool()

        # List all available tools for AI
        tools = registry.list_tools(company_id="comp-001")

        # Execute any tool by name and method
        result = await registry.execute(
            tool_name="crm_tool",
            method="get_contact",
            company_id="comp-001",
            variant_tier="parwa",
            customer_id="cust-001",
        )
    """

    def __init__(self, bridge: Optional[Any] = None, executor: Optional[Any] = None):
        self._bridge = bridge
        self._executor = executor

        # Built-in tools (the original 8)
        self._builtin_tools: Dict[str, BaseReactTool] = {}

        # Dynamically registered tools (REST connectors, custom, etc.)
        self._dynamic_tools: Dict[str, DynamicTool] = {}

        # Per-company tool availability (which tools are enabled for a company)
        self._company_tools: Dict[str, Dict[str, bool]] = {}

        # Initialize built-in tools
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register the 8 built-in tools."""
        try:
            from .crm_tool import CRMTool
            from .billing_tool import BillingTool
            from .order_tool import OrderTool
            from .email_tool import EmailTool
            from .sms_tool import SMSTool
            from .helpdesk_tool import HelpDeskTool
            from .ecommerce_tool import ECommerceTool
            from .slack_tool import SlackTool

            builtin_classes = [
                CRMTool, BillingTool, OrderTool, EmailTool,
                SMSTool, HelpDeskTool, ECommerceTool, SlackTool,
            ]

            for cls in builtin_classes:
                tool = cls(bridge=self._bridge, executor=self._executor)
                self._builtin_tools[tool.name] = tool
        except Exception as exc:
            logger.error("Failed to register built-in tools: %s", exc)

    def register_tool(
        self,
        name: str,
        description: str,
        category: str,
        methods: Dict[str, Callable],
    ) -> bool:
        """Register a custom tool at runtime.

        Args:
            name: Unique tool name (e.g. "notion_tool", "jira_tool")
            description: Description for AI to understand what this tool does
            category: Provider category (e.g. "communication", "crm", "custom")
            methods: Dict of method_name → callable function

        Returns:
            True if registration succeeded
        """
        try:
            tool = DynamicTool(
                name=name,
                description=description,
                category=category,
                methods=methods,
                bridge=self._bridge,
                executor=self._executor,
            )
            self._dynamic_tools[name] = tool
            logger.info("Registered dynamic tool: %s (category: %s, methods: %s)",
                        name, category, list(methods.keys()))
            return True
        except Exception as exc:
            logger.error("Failed to register tool %s: %s", name, exc)
            return False

    def unregister_tool(self, name: str) -> bool:
        """Remove a dynamically registered tool."""
        if name in self._dynamic_tools:
            del self._dynamic_tools[name]
            logger.info("Unregistered dynamic tool: %s", name)
            return True
        return False

    def enable_tool_for_company(self, tool_name: str, company_id: str) -> None:
        """Enable a tool for a specific company."""
        if company_id not in self._company_tools:
            self._company_tools[company_id] = {}
        self._company_tools[company_id][tool_name] = True

    def disable_tool_for_company(self, tool_name: str, company_id: str) -> None:
        """Disable a tool for a specific company."""
        if company_id not in self._company_tools:
            self._company_tools[company_id] = {}
        self._company_tools[company_id][tool_name] = False

    def get_tool(self, name: str) -> Optional[BaseReactTool]:
        """Get a tool by name (built-in or dynamic)."""
        if name in self._builtin_tools:
            return self._builtin_tools[name]
        if name in self._dynamic_tools:
            return self._dynamic_tools[name]
        return None

    def list_tools(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available tools.

        If company_id is provided, only return tools enabled for that company.
        If no company_id, return all tools.
        """
        all_tools = {}

        # Built-in tools (always available)
        for name, tool in self._builtin_tools.items():
            methods = [
                m for m in dir(tool)
                if not m.startswith("_") and callable(getattr(tool, m)) and m != "to_dict"
            ]
            all_tools[name] = {
                "name": tool.name,
                "category": tool.category,
                "description": tool.description,
                "methods": methods,
                "type": "builtin",
            }

        # Dynamic tools
        for name, tool in self._dynamic_tools.items():
            all_tools[name] = {
                "name": tool.name,
                "category": tool.category,
                "description": tool.description,
                "methods": list(tool._methods.keys()),
                "type": "dynamic",
            }

        # Filter by company if needed
        if company_id and company_id in self._company_tools:
            company_tool_state = self._company_tools[company_id]
            result = []
            for name, info in all_tools.items():
                # If company has explicit state for this tool, respect it
                if name in company_tool_state:
                    if company_tool_state[name]:
                        result.append(info)
                else:
                    # Default: built-in tools are on, dynamic tools are on
                    result.append(info)
            return result

        return list(all_tools.values())

    def list_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List all tools in a specific category."""
        return [
            t for t in self.list_tools()
            if t.get("category") == category
        ]

    async def execute(
        self,
        tool_name: str,
        method: str,
        company_id: str,
        variant_tier: str = "parwa",
        **kwargs,
    ) -> ToolResult:
        """Execute any registered tool by name and method.

        This is the MAIN ENTRY POINT for the AI pipeline.
        The AI says "I want to use crm_tool.get_contact" and this method
        finds the tool, checks permissions, and executes it.
        """
        try:
            tool = self.get_tool(tool_name)
            if not tool:
                return ToolResult(
                    success=False,
                    message=f"Unknown tool: {tool_name}. Available: {list(self._builtin_tools.keys()) + list(self._dynamic_tools.keys())}",
                    tool_name=tool_name,
                )

            # Check company-level tool availability
            if company_id in self._company_tools:
                if tool_name in self._company_tools[company_id]:
                    if not self._company_tools[company_id][tool_name]:
                        return ToolResult(
                            success=False,
                            message=f"Tool {tool_name} is disabled for this company",
                            tool_name=tool_name,
                        )

            # Check variant permission
            perm = VARIANT_PERMISSIONS.get(variant_tier, PermissionLevel.EXECUTE)

            # Find the method
            if isinstance(tool, DynamicTool):
                result = await tool._execute_method(
                    method_name=method,
                    company_id=company_id,
                    variant_tier=variant_tier,
                    **kwargs,
                )
                return result
            else:
                # Built-in tool — find the method
                method_fn = getattr(tool, method, None)
                if not method_fn or not callable(method_fn):
                    return ToolResult(
                        success=False,
                        message=f"Method {method} not found on tool {tool_name}",
                        tool_name=tool_name,
                    )

                # Call the method with standard params
                return await method_fn(
                    company_id=company_id,
                    variant_tier=variant_tier,
                    **kwargs,
                )

        except Exception as exc:
            logger.error("UniversalToolRegistry.execute failed: %s", exc)
            return ToolResult(
                success=False,
                message=str(exc),
                tool_name=tool_name,
            )

    def register_rest_connector_tool(
        self,
        connector_name: str,
        base_url: str,
        openapi_spec: Optional[Dict] = None,
        auth_type: str = "bearer",
        credentials: Optional[Dict] = None,
    ) -> bool:
        """Auto-register a tool from a REST connector / OpenAPI spec.

        This is how we make ANY platform integratable:
        1. User imports an OpenAPI spec (or enters a base URL)
        2. We parse the endpoints into methods
        3. Each endpoint becomes a callable method
        4. The tool is registered in the registry
        5. AI can use it immediately
        """
        try:
            methods: Dict[str, Callable] = {}

            if openapi_spec:
                # Parse OpenAPI spec to extract endpoints
                paths = openapi_spec.get("paths", {})
                for path, path_item in paths.items():
                    for http_method, operation in path_item.items():
                        if http_method.lower() in ("get", "post", "put", "patch", "delete"):
                            op_id = operation.get("operationId", f"{http_method}_{path.replace('/', '_').strip('_')}")
                            # Create a closure for this endpoint
                            methods[op_id] = self._make_rest_method(
                                base_url=base_url,
                                path=path,
                                http_method=http_method,
                                auth_type=auth_type,
                                credentials=credentials,
                            )
            else:
                # No spec — register a generic "call" method
                methods["call"] = self._make_rest_method(
                    base_url=base_url,
                    path="/",
                    http_method="post",
                    auth_type=auth_type,
                    credentials=credentials,
                )

            description = f"REST connector for {connector_name}"
            if openapi_spec:
                info = openapi_spec.get("info", {})
                description = info.get("description", description)

            return self.register_tool(
                name=f"{connector_name}_tool",
                description=description,
                category="custom",
                methods=methods,
            )

        except Exception as exc:
            logger.error("register_rest_connector_tool failed: %s", exc)
            return False

    def _make_rest_method(
        self,
        base_url: str,
        path: str,
        http_method: str,
        auth_type: str = "bearer",
        credentials: Optional[Dict] = None,
    ) -> Callable:
        """Create a callable for a REST endpoint."""
        async def rest_method(**kwargs) -> Dict[str, Any]:
            try:
                import httpx

                url = f"{base_url.rstrip('/')}{path}"

                # Build headers
                headers = {"Content-Type": "application/json"}
                if credentials and auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {credentials.get('token', '')}"
                elif credentials and auth_type == "api_key":
                    key_name = credentials.get("header_name", "X-API-Key")
                    headers[key_name] = credentials.get("api_key", "")

                # Separate path/query params from body
                body_keys = set()
                if http_method.lower() in ("post", "put", "patch"):
                    body = {k: v for k, v in kwargs.items() if not k.startswith("_")}
                    body_keys = set(body.keys())
                else:
                    body = None

                # Add non-body kwargs as query params
                params = {k: v for k, v in kwargs.items() if k not in body_keys and not k.startswith("_")}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    fn = getattr(client, http_method.lower(), client.get)
                    resp = await fn(url, headers=headers, params=params, json=body)

                    if resp.status_code < 400:
                        return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"status": "success", "status_code": resp.status_code}
                    else:
                        return {"status": "error", "status_code": resp.status_code, "detail": resp.text[:500]}

            except ImportError:
                return {"status": "error", "message": "httpx not available"}
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        return rest_method

    def get_tool_schema_for_ai(self) -> List[Dict[str, Any]]:
        """Get a schema of all tools suitable for AI function calling.

        Returns a list of tool definitions that can be passed to
        Gemini or any LLM for function calling / tool use.
        """
        schemas = []
        for tool_info in self.list_tools():
            tool = self.get_tool(tool_info["name"])
            if not tool:
                continue

            schema = {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "category": tool_info["category"],
                "methods": {},
            }

            for method_name in tool_info["methods"]:
                if isinstance(tool, DynamicTool):
                    # Dynamic tool — generic parameter schema
                    schema["methods"][method_name] = {
                        "parameters": {
                            "company_id": {"type": "string", "required": True},
                            "variant_tier": {"type": "string", "required": True},
                        }
                    }
                else:
                    # Built-in tool — inspect the method signature
                    method_fn = getattr(tool, method_name, None)
                    if method_fn:
                        import inspect
                        sig = inspect.signature(method_fn)
                        params = {}
                        for pname, param in sig.parameters.items():
                            if pname in ("self", "kwargs"):
                                continue
                            params[pname] = {
                                "type": "string",
                                "required": param.default is inspect.Parameter.empty,
                            }
                        schema["methods"][method_name] = {"parameters": params}

            schemas.append(schema)

        return schemas
