"""
Superglue Client — PARWA's bridge to Superglue integration platform.

Superglue handles ALL API connections (public + private + custom).
PARWA's LLM decides what to do → Superglue executes it.

Flow:
  1. PARWA LLM: "Customer wants refund → call payment-refund-by-email tool"
  2. Superglue: POST /v1/tools/{toolId}/run with {"inputs": {customerEmail: "..."}}
  3. Superglue executes multi-step chain: find customer → list txn → refund → email
  4. Returns result to PARWA LLM → tells customer "Refund processed"

Multi-step template syntax (proven working):
  - Tool input reference:        <<customerEmail>>
  - Step result (arrow fn):      <<(sourceData) => 'https://api.x.com/' + sourceData.stepId.data.path>>
  - For Paddle (wraps in data[]): sourceData.stepId.data.data[0].id (DOUBLE .data)
  - For Stripe (flat response):  sourceData.stepId.data.id (single .data)
  - ALWAYS end templates with >> (DOUBLE chevron)

Execution endpoint:
  POST /v1/tools/{toolId}/run    — execute a saved tool (sync, returns full result)
  POST /v1/tools/run             — execute by providing full tool config inline
  POST /v1/runs                  — only for LOGGING a run record (NOT execution)

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
    """Execute a Superglue tool (sync — waits for full multi-step chain to complete).

    Args:
        tool_id: The Superglue tool ID (e.g. "payment-refund-by-email")
        input_data: Input parameters (e.g. {"customerEmail": "john@gmail.com"})

    Returns:
        {success: bool, data: dict, error: str, run_id: str, step_results: list}

    Important:
        - The API field is "inputs" (PLURAL), not "input".
        - Sync mode returns the FULL result inline (no need to poll /v1/runs/{id}).
        - For multi-step tools, this waits for ALL steps to complete (~3-10s typical).
        - For async mode (long-running tools), pass options.async=true and poll separately.
    """
    url, token = _get_config()
    if not url or not token:
        return {"success": False, "error": "Superglue not configured"}

    try:
        # Sync execution — waits for the full multi-step chain to complete.
        # Body MUST use "inputs" (plural) — confirmed in Superglue source code:
        # packages/core/api/tools.ts line 381: payload: body?.inputs
        payload = {"inputs": input_data}

        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{url}/v1/tools/{tool_id}/run",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if res.status_code in (200, 202):
            result = res.json()
            status = result.get("status", "unknown")
            run_id = result.get("runId", "")
            step_results = result.get("stepResults", []) or []

            # Sync success — result.data is the final output (after outputTransform)
            if status == "success":
                return {
                    "success": True,
                    "data": result.get("data"),
                    "error": None,
                    "run_id": run_id,
                    "step_results": [
                        {
                            "step_id": sr.get("stepId"),
                            "success": sr.get("success", False),
                            "error": sr.get("error"),
                        }
                        for sr in step_results
                    ],
                    "tool_id": tool_id,
                }

            # Async accepted — run started but not yet complete. Poll for result.
            if status == "running" and run_id:
                logger.info("superglue tool %s running async, polling run_id=%s", tool_id, run_id)
                return await _poll_run_status(run_id, tool_id=tool_id)

            # Failed or unknown
            return {
                "success": False,
                "data": result.get("data"),
                "error": result.get("error") or f"Superglue returned status: {status}",
                "run_id": run_id,
                "step_results": [
                    {
                        "step_id": sr.get("stepId"),
                        "success": sr.get("success", False),
                        "error": sr.get("error"),
                    }
                for sr in step_results
                ],
                "tool_id": tool_id,
            }

        return {
            "success": False,
            "error": f"Superglue returned {res.status_code}: {res.text[:200]}",
            "tool_id": tool_id,
        }

    except Exception as exc:
        logger.error("superglue_execute_tool error: %s", str(exc)[:200])
        return {"success": False, "error": str(exc)[:200], "tool_id": tool_id}


async def _poll_run_status(run_id: str, tool_id: str = "", max_polls: int = 30, interval: float = 2.0) -> Dict[str, Any]:
    """Poll a Superglue run until it completes (success/failed) or times out.

    Used for async-execution tools that return status=running.
    Returns the same shape as execute_tool():
        {success, data, error, run_id, step_results, tool_id}
    """
    url, token = _get_config()
    if not url or not token:
        return {"success": False, "error": "Superglue not configured", "run_id": run_id, "tool_id": tool_id}

    import asyncio

    for poll_idx in range(max_polls):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                res = await client.get(
                    f"{url}/v1/runs/{run_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

            if res.status_code != 200:
                logger.warning("superglue poll %d/%d status=%d", poll_idx + 1, max_polls, res.status_code)
                await asyncio.sleep(interval)
                continue

            result = res.json()
            status = result.get("status", "unknown")
            step_results = result.get("stepResults", []) or []

            if status == "success":
                return {
                    "success": True,
                    "data": result.get("data"),
                    "error": None,
                    "run_id": run_id,
                    "step_results": [
                        {"step_id": sr.get("stepId"), "success": sr.get("success", False), "error": sr.get("error")}
                        for sr in step_results
                    ],
                    "tool_id": tool_id,
                }

            if status == "failed":
                return {
                    "success": False,
                    "data": result.get("data"),
                    "error": result.get("error", "Tool execution failed"),
                    "run_id": run_id,
                    "step_results": [
                        {"step_id": sr.get("stepId"), "success": sr.get("success", False), "error": sr.get("error")}
                        for sr in step_results
                    ],
                    "tool_id": tool_id,
                }

            # Still running — wait and retry
            logger.info("superglue poll %d/%d status=%s, waiting %.1fs", poll_idx + 1, max_polls, status, interval)
            await asyncio.sleep(interval)

        except Exception as exc:
            logger.warning("superglue poll %d/%d error: %s", poll_idx + 1, max_polls, str(exc)[:100])
            await asyncio.sleep(interval)

    # Timed out
    return {
        "success": False,
        "error": f"Superglue run {run_id} did not complete within {max_polls * interval:.0f}s",
        "run_id": run_id,
        "tool_id": tool_id,
    }


# Backwards-compat alias
_get_run_status = _poll_run_status


async def get_available_tools_description() -> str:
    """Get a human-readable description of available tools for the LLM.

    This is what PARWA's LLM sees to decide which tool to call.
    Includes: tool ID, name, instruction (what it does), required inputs.
    Skips archived tools.
    """
    tools = await list_tools()
    if not tools:
        return "No Superglue tools available."

    lines = []
    for tool in tools:
        if tool.get("archived", False):
            continue  # hide archived tools from LLM

        tool_id = tool.get("id", "?")
        name = tool.get("name", "?")
        instruction = tool.get("instruction", "") or ""
        schema = tool.get("inputSchema", {}) or {}
        properties = schema.get("properties", {}) if schema else {}
        required = schema.get("required", []) if schema else []

        if properties:
            param_parts = []
            for k, v in properties.items():
                ptype = v.get("type", "string")
                desc = v.get("description", "")
                req_marker = " (required)" if k in required else " (optional)"
                if desc:
                    param_parts.append(f"{k}: {ptype}{req_marker} — {desc}")
                else:
                    param_parts.append(f"{k}: {ptype}{req_marker}")
            params = "\n      ".join(param_parts)
        else:
            params = "no params"

        # Include instruction so LLM understands what the tool DOES (not just its name)
        if instruction:
            lines.append(f"- {tool_id} — {name}\n    what it does: {instruction}\n    inputs:\n      {params}")
        else:
            lines.append(f"- {tool_id} — {name}\n    inputs:\n      {params}")

    return "Available Superglue tools (each is a multi-step workflow — pick ONE that matches the customer's intent):\n" + "\n".join(lines)
