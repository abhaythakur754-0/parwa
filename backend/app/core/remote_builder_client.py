"""
Remote Builder Client — calls the external Builder service.

This offloads the heavy 4-stage Builder pipeline (EXPLORE → DESIGN → VERIFY →
REFINE, 12+ LLM calls, 20-30s per agent) to a dedicated service running
on a separate machine with 2GB RAM + Groq + Mistral API keys.

ARCHITECTURE:
  Render PARWA (512MB)              External Builder Service (2GB)
  ──────────────────               ────────────────────────────────
  1. Detect capability gap  →      2. Receives POST /api/build
  3. Save agent to Postgres ←      2. Runs 4-stage pipeline (30s)
     RAM used: ~50MB                  RAM used: ~2GB (not on Render!)

WHY THIS EXISTS:
  The local Builder pipeline (builder_pipeline.py) was too heavy for
  Render's 512MB Starter plan — it caused OOM crashes when building
  multiple agents. This remote client offloads the work.

  The LOCAL builder code (builder_pipeline.py, builder_llm.py) is NOT
  deleted — it's kept as a fallback. If the remote service is down,
  the code falls back to the local builder (if BUILDER_FALLBACK_LOCAL=true).

CONFIG:
  BUILDER_SERVICE_URL: URL of the external Builder service
  BUILDER_FALLBACK_LOCAL: If 'true', fall back to local builder on remote
                          failure (default: 'false' — fail, don't use RAM)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.remote_builder")

# The correct public URL (uses chat_id, not session_id)
DEFAULT_BUILDER_URL = "https://preview-chat-ac11d6a7-6c3d-42a0-acb8-a37ecf9e8dea.space-z.ai"


def get_builder_url() -> str:
    """Get the Builder service URL.

    Uses BUILDER_SERVICE_URL env var if set, otherwise defaults to the
    hardcoded public URL (user doesn't need to add env var on Render).
    """
    return os.environ.get("BUILDER_SERVICE_URL", DEFAULT_BUILDER_URL).rstrip("/")


async def call_remote_builder(
    *,
    tenant_id: str,
    kb_context: str,
    integrations: Optional[List[str]] = None,
    capability: str = "general_assistant",
    timeout: float = 240.0,
) -> Dict[str, Any]:
    """Call the external Builder service to build an agent.

    Args:
        tenant_id: The tenant's company_id (for scoping).
        kb_context: Knowledge base text about the tenant's business.
        integrations: List of connected integration names (e.g. ["stripe"]).
        capability: The capability to build (e.g. "refund_processing").
        timeout: HTTP timeout in seconds (default 240s = 4 min).

    Returns:
        Dict with:
          - agent_id: UUID of the built agent
          - agent_config: {agent_name, agent_role, capabilities, instructions,
                          restrictions, attachment_method, is_customer_care}
          - status: "complete" | "rejected" | "failed"
          - quality_score: float (0-1)
          - stage_iterations: {explore: N, design: N, verify: N}
          - error: None or error message

    Raises:
        RuntimeError: If the remote service is unreachable or returns an error.
    """
    import httpx

    url = f"{get_builder_url()}/api/build"
    payload = {
        "tenant_id": tenant_id,
        "kb_context": kb_context,
        "integrations": integrations or [],
        "capability": capability,
    }

    logger.info(
        "remote_builder_call tenant=%s capability=%s url=%s",
        tenant_id[:8], capability, url[:60],
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            result = r.json()

        logger.info(
            "remote_builder_success tenant=%s capability=%s status=%s quality=%.2f",
            tenant_id[:8], capability,
            result.get("status"),
            result.get("quality_score", 0),
        )
        return result

    except httpx.TimeoutException:
        logger.error("remote_builder_timeout tenant=%s capability=%s", tenant_id[:8], capability)
        raise RuntimeError(f"Builder service timed out after {timeout}s")
    except httpx.HTTPStatusError as exc:
        logger.error("remote_builder_http_error status=%s body=%s",
                     exc.response.status_code, exc.response.text[:200])
        raise RuntimeError(f"Builder service returned {exc.response.status_code}: {exc.response.text[:200]}")
    except Exception as exc:
        logger.error("remote_builder_failed: %s", str(exc)[:200])
        raise RuntimeError(f"Builder service unreachable: {str(exc)[:200]}")


async def build_agent_with_fallback(
    *,
    tenant_id: str,
    kb_context: str,
    integrations: Optional[List[str]] = None,
    capability: str = "general_assistant",
) -> Dict[str, Any]:
    """Build an agent, falling back to local builder if remote fails.

    If BUILDER_FALLBACK_LOCAL=true and the remote service fails, this
    falls back to the local builder_pipeline.py (uses Render's RAM).
    Default is false (fail, don't risk OOM on Render).

    Returns:
        Same dict as call_remote_builder(), or from local builder.
    """
    try:
        return await call_remote_builder(
            tenant_id=tenant_id,
            kb_context=kb_context,
            integrations=integrations,
            capability=capability,
        )
    except RuntimeError as exc:
        fallback = os.environ.get("BUILDER_FALLBACK_LOCAL", "false").lower() == "true"
        if not fallback:
            raise

        logger.warning(
            "remote_builder_failed_falling_back_to_local err=%s",
            str(exc)[:200],
        )
        # Fall back to local builder (uses Render RAM — risky on 512MB)
        from app.core.builder_agent.builder_pipeline import run_builder_pipeline
        return await run_builder_pipeline(
            tenant_id=tenant_id,
            capability=capability,
            query=kb_context[:500],
            ticket_type=capability,
            complexity="medium",
            tier="parwa",
        )
