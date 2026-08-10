"""
Superglue Tool Generator — PARWA's bridge to Superglue's Agent API.

PARWA's Builder Agent creates AI agents (instructions, restrictions, capabilities).
For each agent that needs API actions (refund, cancel, etc.), PARWA asks Superglue
to GENERATE a multi-step tool. Superglue uses its OWN LLM key to do this.

This keeps Render's 512MB RAM free — PARWA just makes an HTTP call, Superglue does
the heavy LLM work on a separate server with a separate rate limit pool.

Flow:
  1. Builder Agent creates AI agent config (PARWA's NVIDIA GLM-5.2)
  2. Builder Agent calls generate_tool_for_agent() below
  3. PARWA sends POST /v1/agent/generate to Superglue with the tool description
  4. Superglue uses ITS LLM (separate key, separate IP) to generate tool JSON
  5. Superglue saves the tool + returns tool_id
  6. PARWA saves tool_id in AIAgentAssignment.superglue_tool_id

Cost: $0 on PARWA side (just HTTP call). LLM cost absorbed by Superglue's free trial.

Env vars (already configured):
  SUPERGLUE_API_URL=https://preview-chat-xxx.space-z.ai
  SUPERGLUE_AUTH_TOKEN=c398040a73bfc7880ae316a122bcb322419bf26789e47416
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.superglue_client import _get_config, is_configured

logger = logging.getLogger("parwa.superglue_tool_generator")

HTTP_TIMEOUT = 90.0  # tool generation takes longer than execution (LLM involved)


async def generate_tool_for_agent(
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str] = None,
    tenant_integrations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ask Superglue to generate a multi-step tool for this AI agent.

    Args:
        agent_name: Human name of the PARWA agent (e.g. "Refund Specialist")
        agent_instructions: The system prompt PARWA's LLM uses for this agent
        agent_capabilities: What this agent handles (e.g. "refund_processing, billing_inquiry")
        sample_ticket: A real ticket text that triggered this agent (helps Superglue design the tool)
        tenant_integrations: List of integrations the tenant has connected
            (e.g. {"paddle": {"api_key": "pdl_..."}, "brevo": {"api_key": "..."}})

    Returns:
        {
            success: bool,
            tool_id: str,             # the Superglue tool ID to save
            tool_definition: dict,    # the full JSON for audit
            error: str | None
        }

    Note:
        - Superglue's Agent API uses Superglue's OWN LLM key (configured on the server).
        - PARWA does NOT call any LLM directly here.
        - If Superglue is unconfigured or down, returns success=false (caller can retry).
    """
    if not is_configured():
        return {
            "success": False,
            "error": "Superglue not configured — set SUPERGLUE_API_URL + SUPERGLUE_AUTH_TOKEN",
            "tool_id": None,
            "tool_definition": None,
        }

    url, token = _get_config()

    # Build the request to Superglue's Agent API.
    # Superglue's Agent endpoint accepts a natural-language description of the tool
    # and returns a saved tool_id. The LLM call happens INSIDE Superglue.
    payload = {
        "name": f"PARWA: {agent_name}",
        "instruction": _build_tool_instruction(
            agent_name, agent_instructions, agent_capabilities, sample_ticket, tenant_integrations
        ),
        # Superglue uses its OWN credentials store for the actual API keys.
        # We just tell it which integrations are connected.
        "availableSystems": _format_integrations(tenant_integrations or {}),
        # Optional: a sample ticket for context
        "sampleTicket": sample_ticket,
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # Try Superglue's Agent generate-tool endpoint (if it exists)
            res = await client.post(
                f"{url}/v1/agent/generate-tool",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if res.status_code in (200, 201):
            result = res.json()
            tool_id = result.get("toolId") or result.get("id")
            tool_definition = result.get("tool") or result.get("definition") or result

            logger.info(
                "superglue_generate_tool: agent=%s tool_id=%s",
                agent_name, tool_id,
            )

            return {
                "success": True,
                "tool_id": tool_id,
                "tool_definition": tool_definition,
                "error": None,
            }

        # Superglue returned an error
        logger.warning(
            "superglue_generate_tool failed: status=%d body=%s",
            res.status_code, res.text[:300],
        )
        return {
            "success": False,
            "error": f"Superglue returned {res.status_code}: {res.text[:200]}",
            "tool_id": None,
            "tool_definition": None,
        }

    except Exception as exc:
        logger.error("superglue_generate_tool error: %s", str(exc)[:200])
        return {
            "success": False,
            "error": str(exc)[:200],
            "tool_id": None,
            "tool_definition": None,
        }


def _build_tool_instruction(
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str],
    tenant_integrations: Optional[Dict[str, Any]],
) -> str:
    """Build the natural-language instruction sent to Superglue's Agent.

    Superglue's Agent uses this to understand WHAT tool to build.
    It will use its own LLM to design the multi-step workflow.
    """
    parts = [
        f"Build a multi-step tool for PARWA agent: {agent_name}.",
        f"This agent handles: {agent_capabilities}.",
    ]

    if agent_instructions:
        parts.append(f"Agent context: {agent_instructions[:500]}")

    if sample_ticket:
        parts.append(f"Sample ticket this agent needs to handle: {sample_ticket[:500]}")

    if tenant_integrations:
        integ_list = ", ".join(tenant_integrations.keys())
        parts.append(f"Tenant has these integrations connected: {integ_list}.")

    parts.append(
        "Design a multi-step tool that takes the customer's input (e.g. email, order ID) "
        "and executes the necessary API calls end-to-end. Use the connected integrations' "
        "credentials from your systems store."
    )

    return " ".join(parts)


def _format_integrations(integrations: Dict[str, Any]) -> list:
    """Format tenant integrations for Superglue's Agent API.

    Superglue's Agent needs to know which systems are available so it can
    pick the right API endpoints when designing the tool.
    """
    systems = []
    for integ_type, creds in integrations.items():
        systems.append({
            "id": integ_type,
            "type": integ_type,
            "credentials": creds if isinstance(creds, dict) else {},
        })
    return systems


async def check_tool_status(tool_id: str) -> Dict[str, Any]:
    """Check if a previously-generated tool is ready (Superglue Agent is async).

    Returns:
        {status: "active"|"pending"|"failed", tool_id, definition}
    """
    if not is_configured():
        return {"status": "unknown", "tool_id": tool_id}

    url, token = _get_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{url}/v1/tools/{tool_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if res.status_code == 200:
            tool = res.json()
            return {
                "status": "active" if not tool.get("archived", False) else "disabled",
                "tool_id": tool_id,
                "definition": tool,
            }
        return {"status": "failed", "tool_id": tool_id}

    except Exception as exc:
        logger.warning("check_tool_status error: %s", str(exc)[:200])
        return {"status": "unknown", "tool_id": tool_id, "error": str(exc)[:200]}


async def disable_tool(tool_id: str) -> bool:
    """Disable a Superglue tool (archive it). Returns True on success."""
    if not is_configured():
        return False

    url, token = _get_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.patch(
                f"{url}/v1/tools/{tool_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"archived": True},
            )
        return res.status_code in (200, 204)
    except Exception as exc:
        logger.warning("disable_tool error: %s", str(exc)[:200])
        return False
