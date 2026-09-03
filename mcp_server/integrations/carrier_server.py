"""
PARWA MCP — Carrier Server (v2.0.0 — Wired to Real Backend)

Provides shipping carrier tracking and logistics tools.
Wired to real backend CarrierAPIConnector via httpx.

Backend service: backend/app/core/carrier_api_connector.py
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.carrier_server")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class CarrierServer(MCPServerBase):
    """MCP sub-server for shipping carrier tracking and logistics — wired to real backend."""

    name = "carrier_server"
    description = "Shipping carrier tracking, delay detection, and compensation calculation"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register carrier tools."""
        registry.register_tool(
            ToolDefinition(
                name="carrier_detect",
                description="Detect the shipping carrier from a tracking number. "
                            "Supports USPS, UPS, FedEx, DHL, and others.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "tracking_number": {
                            "type": "string",
                            "description": "Tracking number to identify carrier for",
                        },
                    },
                    "required": ["tracking_number"],
                },
                tags=["carrier", "shipping", "detect", "tracking"],
            ),
            handler=self._invoke_detect_carrier,
        )

        registry.register_tool(
            ToolDefinition(
                name="carrier_track_shipment",
                description="Track a shipment by tracking number. Returns standardized tracking info "
                            "including status, location history, and estimated delivery.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "tracking_number": {
                            "type": "string",
                            "description": "Tracking number",
                        },
                        "carrier_id": {
                            "type": "string",
                            "description": "Optional carrier ID (auto-detected if not provided)",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID",
                        },
                    },
                    "required": ["tracking_number"],
                },
                tags=["carrier", "shipping", "tracking", "status"],
            ),
            handler=self._invoke_track_shipment,
        )

        registry.register_tool(
            ToolDefinition(
                name="carrier_detect_delays",
                description="Detect shipping delays by comparing actual tracking status against expected timelines.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "tracking_number": {
                            "type": "string",
                        },
                        "company_id": {
                            "type": "string",
                        },
                    },
                    "required": ["tracking_number"],
                },
                tags=["carrier", "shipping", "delay", "detection"],
            ),
            handler=self._invoke_detect_delays,
        )

        registry.register_tool(
            ToolDefinition(
                name="carrier_calculate_compensation",
                description="Calculate compensation for delayed shipments based on SLA and shipping tier.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "tracking_number": {
                            "type": "string",
                        },
                        "shipping_cost": {
                            "type": "number",
                            "description": "Original shipping cost",
                        },
                        "service_tier": {
                            "type": "string",
                            "enum": ["standard", "express", "overnight"],
                            "default": "standard",
                        },
                        "company_id": {
                            "type": "string",
                        },
                    },
                    "required": ["tracking_number"],
                },
                tags=["carrier", "shipping", "compensation", "refund"],
            ),
            handler=self._invoke_calculate_compensation,
        )

    def get_router(self) -> APIRouter:
        """Return the carrier REST router."""
        router = APIRouter(prefix="/integrations/carrier", tags=["Integration — Carrier"])

        @router.post("/detect")
        async def detect_carrier(request: dict) -> dict:
            """Detect carrier from tracking number."""
            result = await self._invoke_detect_carrier(request)
            if result.success and result.data:
                return result.data
            return {"error": result.error or "Carrier detection failed"}

        @router.post("/track")
        async def track_shipment(request: dict) -> dict:
            """Track a shipment."""
            result = await self._invoke_track_shipment(request)
            if result.success and result.data:
                return result.data
            return {"error": result.error or "Tracking failed"}

        return router

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend carrier API.

        Returns the parsed JSON body on HTTP 200/201, or None on transport error
        / non-2xx response. Callers inspect the `status` field of the returned
        body (one of "ok" / "not_configured" / "not_found" / "external_error").
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "carrier_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("carrier_backend_failed", path=path, error=str(exc)[:200])
        return None

    def _status_response(self, tool_name: str, body: dict) -> ToolInvokeResponse:
        """Translate the backend's structured CarrierActionResponse into a ToolInvokeResponse.

        - status="ok"             → success=True, data populated
        - status="not_found"      → success=False, error explains no carrier matched
        - status="not_configured" → success=False, error explains how to connect the integration
        - status="external_error" → success=False, error includes the provider error
        """
        status = body.get("status", "external_error")
        if status == "ok":
            return ToolInvokeResponse(
                success=True,
                tool_name=tool_name,
                data=body.get("data", {}),
                metadata={"source": "backend"},
            )
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=body.get("error") or f"Carrier {status}",
            data=body.get("data", {}),
            metadata={"source": "backend", "status": status},
        )

    def _unreachable_response(self, tool_name: str) -> ToolInvokeResponse:
        """Backend unreachable — honest failure, no fake data."""
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error="Backend carrier API is unreachable. Check that the backend service is running.",
            metadata={"source": "unreachable"},
        )

    async def _invoke_detect_carrier(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle carrier_detect tool invocation — wired to backend."""
        params = parameters or {}
        tracking_number = params.get("tracking_number", "")

        logger.info("carrier_detect_invoked", tracking_number=tracking_number)

        body = await self._backend_call(
            "POST", "/api/integrations/carrier/detect",
            json_data={"tracking_number": tracking_number},
        )
        if body:
            return self._status_response("carrier_detect", body)
        return self._unreachable_response("carrier_detect")

    async def _invoke_track_shipment(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle carrier_track_shipment tool invocation — wired to backend."""
        params = parameters or {}
        tracking_number = params.get("tracking_number", "")
        carrier_id = params.get("carrier_id")

        logger.info("carrier_track_shipment_invoked", tracking_number=tracking_number)

        payload = {"tracking_number": tracking_number}
        if carrier_id:
            payload["carrier_id"] = carrier_id

        body = await self._backend_call(
            "POST", "/api/integrations/carrier/track",
            json_data=payload,
        )
        if body:
            return self._status_response("carrier_track_shipment", body)
        return self._unreachable_response("carrier_track_shipment")

    async def _invoke_detect_delays(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle carrier_detect_delays tool invocation — wired to backend."""
        params = parameters or {}
        tracking_number = params.get("tracking_number", "")

        logger.info("carrier_detect_delays_invoked", tracking_number=tracking_number)

        payload = {"tracking_number": tracking_number}
        if params.get("carrier_id"):
            payload["carrier_id"] = params["carrier_id"]

        body = await self._backend_call(
            "POST", "/api/integrations/carrier/detect-delays",
            json_data=payload,
        )
        if body:
            return self._status_response("carrier_detect_delays", body)
        return self._unreachable_response("carrier_detect_delays")

    async def _invoke_calculate_compensation(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle carrier_calculate_compensation tool invocation — wired to backend."""
        params = parameters or {}
        tracking_number = params.get("tracking_number", "")

        logger.info("carrier_calculate_compensation_invoked", tracking_number=tracking_number)

        payload = {
            "tracking_number": tracking_number,
            "shipping_cost": params.get("shipping_cost", 0),
            "service_tier": params.get("service_tier", "standard"),
        }
        if params.get("carrier_id"):
            payload["carrier_id"] = params["carrier_id"]

        body = await self._backend_call(
            "POST", "/api/integrations/carrier/compensation",
            json_data=payload,
        )
        if body:
            return self._status_response("carrier_calculate_compensation", body)
        return self._unreachable_response("carrier_calculate_compensation")


# Singleton instance
carrier_server = CarrierServer()
