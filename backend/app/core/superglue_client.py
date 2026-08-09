"""
Superglue Client — PARWA's bridge to Superglue integration platform.

Superglue handles ALL API connections (public + private + custom).
PARWA's LLM decides what to do → Superglue executes it.

Flow:
  1. PARWA LLM: "Customer wants refund → call stripe-refund tool"
  2. Superglue: POST /v1/tools/{toolId}/run with {input: {amount: 14900}}
  3. Superglue calls Stripe API → returns result
  4. PARWA LLM reads result → tells customer "Refund processed"

Env vars (set on Render):
  SUPERGLUE_API_URL=https://preview-chat-xxx.space-z.ai
  SUPERGLUE_AUTH_TOKEN=c398040a73bfc7880ae316a122bcb322419bf26789e47416
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("parwa.superglue_client")

HTTP_TIMEOUT = 30.0


def _get_config() -> tuple[str, str]:
    """Get Superglue URL + token from env vars."""
    url = os.environ.get("SUPERGLUE_API_URL", "").strip().rstrip("/")
    token = os.environ.get("SUPERGLUE_AUTH_TOKEN", "").strip()
    return url, token


def is_configured() -> bool:
    """Check if Superglue is configured."""
    url, token = _get_config()
    return bool(url and token)


async def list_tools() -> List[Dict[str, Any]]:
    """List all tools available in Superglue.

    Returns list of tool dicts: {id, name, inputSchema, ...}
    """
    url, token = _get_config()
    if not url or not token:
        return []

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(
                f"{url}/v1/tools",
                headers={"Authorization": f"Bearer {token}"},
            )
        if res.status_code == 200:
            data = res.json()
            return data.get("data", [])
        logger.warning("superglue_list_tools status=%d", res.status_code)
        return []
    except Exception as exc:
        logger.warning("superglue_list_tools error: %s", str(exc)[:200])
        return []


async def list_systems() -> List[Dict[str, Any]]:
    """List all connected systems in Superglue."""
    url, token = _get_config()
    if not url or not token:
        return []

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(
                f"{url}/v1/systems",
                headers={"Authorization": f"Bearer {token}"},
            )
        if res.status_code == 200:
            data = res.json()
            return data.get("data", [])
        return []
    except Exception as exc:
        logger.warning("superglue_list_systems error: %s", str(exc)[:200])
        return []


async def execute_tool(tool_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Superglue tool.

    Args:
        tool_id: The Superglue tool ID (e.g. "stripe-refund")
        input_data: Input parameters (e.g. {"chargeId": "ch_xxx", "amount": 14900})

    Returns:
        {success: bool, data: dict, error: str}
    """
    url, token = _get_config()
    if not url or not token:
        return {"success": False, "error": "Superglue not configured"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{url}/v1/tools/{tool_id}/run",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"input": input_data},
            )

        if res.status_code in (200, 201):
            result = res.json()
            run_id = result.get("runId", "")

            # If we got a runId, check the run status
            if run_id:
                run_result = await _get_run_status(run_id)
                if run_result:
                    return run_result

            # No runId → return direct result
            return {
                "success": result.get("status") != "failed",
                "data": result.get("result", result),
                "error": result.get("error"),
            }

        return {
            "success": False,
            "error": f"Superglue returned {res.status_code}: {res.text[:200]}",
        }

    except Exception as exc:
        logger.error("superglue_execute_tool error: %s", str(exc)[:200])
        return {"success": False, "error": str(exc)[:200]}


async def _get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a tool run."""
    url, token = _get_config()
    if not url or not token:
        return None

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(
                f"{url}/v1/runs/{run_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if res.status_code == 200:
            result = res.json()
            status = result.get("status", "unknown")

            if status == "success":
                return {
                    "success": True,
                    "data": result.get("result", result.get("toolPayload", {})),
                    "error": None,
                    "run_id": run_id,
                }
            elif status == "failed":
                return {
                    "success": False,
                    "data": None,
                    "error": result.get("error", "Tool execution failed"),
                    "run_id": run_id,
                }
            else:
                # Still running or unknown
                return {
                    "success": False,
                    "data": None,
                    "error": f"Tool status: {status}",
                    "run_id": run_id,
                }
        return None
    except Exception:
        return None


async def get_available_tools_description() -> str:
    """Get a human-readable description of available tools for the LLM.

    This is what PARWA's LLM sees to decide which tool to call.
    """
    tools = await list_tools()
    if not tools:
        return "No Superglue tools available."

    lines = []
    for tool in tools:
        tool_id = tool.get("id", "?")
        name = tool.get("name", "?")
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {}) if schema else {}

        params = ", ".join(
            f"{k}: {v.get('type', 'string')}" for k, v in properties.items()
        ) if properties else "no params"

        lines.append(f"- {tool_id} ({name}): {params}")

    return "Available Superglue tools:\n" + "\n".join(lines)
