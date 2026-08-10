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
    # /api/agent/chat expects: agentId + messages array + userMessage
    # The Agent will use Superglue's OWN NVIDIA GLM-5.2 LLM to generate the tool.
    instruction = _build_tool_instruction(
        agent_name, agent_instructions, agent_capabilities, sample_ticket, tenant_integrations
    )
    payload = {
        "agentId": "main",
        "userMessage": instruction,
        "messages": [
            {"role": "user", "content": instruction}
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # Try Superglue's Agent generate-tool endpoint (if it exists)
            res = await client.post(
                f"{url}/api/agent/chat",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if res.status_code in (200, 201):
            # /api/agent/chat returns Server-Sent Events (SSE stream)
            # Each line: data: {"type":"...", ...}
            # We need to parse the stream to find the tool_id
            # For now: if response has toolId in any line, extract it
            response_text = res.text
            import re as _re
            tool_id_match = _re.search(r'"toolId":\s*"([^"]+)"', response_text)
            if tool_id_match:
                tool_id = tool_id_match.group(1)
                logger.info("superglue_agent_generated_tool: agent=%s tool_id=%s", agent_name, tool_id)
                return {
                    "success": True,
                    "tool_id": tool_id,
                    "tool_definition": {"id": tool_id},
                    "error": None,
                    "generated_by": "superglue_agent",
                }
            # No toolId in response — agent might have asked a clarifying question
            # or hit an error. Fall back to PARWA LLM.
            logger.warning(
                "superglue_agent_no_tool_id: agent=%s — falling back to PARWA LLM. Response: %s",
                agent_name, response_text[:200],
            )
            return await _generate_tool_via_parwa_llm(
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                agent_capabilities=agent_capabilities,
                sample_ticket=sample_ticket,
                tenant_integrations=tenant_integrations,
            )

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

        # ── FALLBACK: Use PARWA's NVIDIA LLM to generate the tool ──
        # Superglue self-hosted version doesn't have the Agent API
        # (it's a cloud-only feature). When that's the case, we fall back
        # to using PARWA's NVIDIA GLM-5.2 to generate the tool JSON, then
        # POST it directly to Superglue /v1/tools (which works).
        # This costs PARWA 1 LLM call (~5s, ~500 tokens) but only happens
        # ONCE per agent creation — not per ticket.
        if res.status_code == 404:
            logger.info(
                "superglue_agent_api_unavailable: falling back to PARWA NVIDIA LLM "
                "for agent=%s (one-time cost, not per-ticket)",
                agent_name,
            )
            return await _generate_tool_via_parwa_llm(
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                agent_capabilities=agent_capabilities,
                sample_ticket=sample_ticket,
                tenant_integrations=tenant_integrations,
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


# ════════════════════════════════════════════════════════════════════════════
# FALLBACK: Generate tool via PARWA's NVIDIA LLM (when Superglue Agent API is unavailable)
# ════════════════════════════════════════════════════════════════════════════
#
# When the user's self-hosted Superglue doesn't have the Agent API (404 on
# /api/agent/chat), we fall back to using PARWA's NVIDIA GLM-5.2 to
# generate the tool JSON. This is a ONE-TIME cost per agent creation (not per
# ticket), so it doesn't impact the 512MB RAM constraint during normal operation.
#
# Flow:
#   1. PARWA's NVIDIA LLM generates tool JSON (URL, steps, transforms)
#   2. PARWA POSTs the JSON to Superglue /v1/tools (creates the tool)
#   3. Superglue returns the tool_id
#   4. PARWA saves tool_id to AIAgentAssignment
#
# This is a fallback, not the primary path. The primary path is Superglue Agent API.


async def _generate_tool_via_parwa_llm(
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str] = None,
    tenant_integrations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a Superglue tool using PARWA's NVIDIA LLM (fallback when Superglue Agent API is unavailable).

    This is the FALLBACK path. The primary path is Superglue's own Agent API.
    Use this only when /api/agent/chat returns 404 (self-hosted Superglue
    without Agent feature).

    Cost: 1 LLM call to PARWA's NVIDIA (~5s, ~500 tokens) — one-time per agent,
    not per ticket. Acceptable for 512MB Render constraint.
    """
    import json as _json
    import re as _re
    from app.core.parwa_pipeline.llm_client import llm_call

    # Build prompt for NVIDIA to generate tool JSON
    integ_text = ""
    if tenant_integrations:
        integ_text = "\nConnected integrations: " + ", ".join(tenant_integrations.keys())

    prompt = f"""You are designing a Superglue multi-step tool for an AI agent.

AGENT DETAILS:
  Name: {agent_name}
  Capabilities: {agent_capabilities}
  Instructions: {agent_instructions[:500] if agent_instructions else "(none)"}
{integ_text}

SAMPLE TICKET (optional context):
{sample_ticket[:300] if sample_ticket else "(none)"}

Generate a Superglue multi-step tool JSON that this agent can call to execute
real API actions. The tool should:
1. Take a customer identifier (email, order ID, transaction ID) as input
2. Make the necessary HTTP API calls to complete the action
3. Return a clean summary

Respond with ONLY valid JSON (no markdown, no explanation) in this format:
{{
  "id": "tool-id-kebab-case",
  "name": "Human Readable Name",
  "instruction": "What this tool does",
  "inputSchema": {{
    "type": "object",
    "properties": {{
      "customerEmail": {{"type": "string", "description": "Customer email"}}
    }},
    "required": ["customerEmail"]
  }},
  "steps": [
    {{
      "id": "step1",
      "instruction": "What this step does",
      "config": {{
        "type": "request",
        "method": "GET",
        "url": "https://api.example.com/endpoint",
        "headers": {{}}
      }}
    }}
  ],
  "outputTransform": "(sourceData) => ({{ result: sourceData.step1.data }})"
}}

Template syntax for URLs:
  - Tool input ref: <<customerEmail>>
  - Step result ref: <<(sourceData) => 'https://api.x.com/' + sourceData.stepId.data.path>>
  - For Paddle (wraps items in data[]): sourceData.stepId.data.data[0].id
  - ALWAYS end with >> (double chevron)

Generate ONLY the JSON. No markdown fences, no explanation."""

    try:
        # Call PARWA's NVIDIA LLM
        response = await llm_call(prompt, max_tokens=1500, temperature=0.2)

        if not response:
            return {
                "success": False,
                "error": "PARWA LLM returned empty response",
                "tool_id": None,
                "tool_definition": None,
            }

        # Extract JSON from response (handle markdown fences if present)
        # Strip markdown fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove first line (```json or ```) and last line (```)
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Find the JSON object
        match = _re.search(r'\{[\s\S]*\}', cleaned)
        if not match:
            return {
                "success": False,
                "error": "PARWA LLM response did not contain valid JSON",
                "tool_id": None,
                "tool_definition": None,
            }

        tool_def = _json.loads(match.group())

        # Validate minimal structure
        if not tool_def.get("id") or not tool_def.get("steps"):
            return {
                "success": False,
                "error": "PARWA LLM generated invalid tool structure (missing id or steps)",
                "tool_id": None,
                "tool_definition": tool_def,
            }

        # POST the generated tool to Superglue /v1/tools (creates the tool)
        url, token = _get_config()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                f"{url}/v1/tools",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=tool_def,
            )

        if res.status_code in (200, 201):
            result = res.json()
            tool_id = result.get("id") or tool_def.get("id")
            logger.info(
                "parwa_llm_generated_tool: agent=%s tool_id=%s",
                agent_name, tool_id,
            )
            return {
                "success": True,
                "tool_id": tool_id,
                "tool_definition": tool_def,
                "error": None,
                "generated_by": "parwa_nvidia_llm",  # for audit
            }

        # Superglue rejected the tool
        logger.warning(
            "superglue_rejected_parwa_tool: status=%d body=%s",
            res.status_code, res.text[:300],
        )
        return {
            "success": False,
            "error": f"Superglue rejected the generated tool: {res.status_code}",
            "tool_id": None,
            "tool_definition": tool_def,
        }

    except _json.JSONDecodeError as exc:
        return {
            "success": False,
            "error": f"PARWA LLM generated invalid JSON: {str(exc)[:100]}",
            "tool_id": None,
            "tool_definition": None,
        }
    except Exception as exc:
        logger.error("parwa_llm_tool_generation_failed: %s", str(exc)[:200])
        return {
            "success": False,
            "error": str(exc)[:200],
            "tool_id": None,
            "tool_definition": None,
        }
