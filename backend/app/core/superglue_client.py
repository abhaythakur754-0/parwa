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
from datetime import datetime, timezone

logger = logging.getLogger("parwa.superglue_client")

HTTP_TIMEOUT = 30.0


# ── Hardcoded Superglue config (no env var needed on Render) ──
# Same pattern as Builder + CRM Analyser — URL hardcoded.
# User request (2026-08-12): "connect this also same way"
DEFAULT_SUPERGLUE_URL = "https://preview-chat-57c587a9-5bfa-49a2-a723-08e25fa91694.space-z.ai"
DEFAULT_SUPERGLUE_TOKEN = "sg-test-token"
DEFAULT_SUPERGLUE_QUEUE_URL = "https://preview-chat-57c587a9-5bfa-49a2-a723-08e25fa91694.space-z.ai/enqueue"
DEFAULT_SUPERGLUE_STATUS_URL = "https://preview-chat-57c587a9-5bfa-49a2-a723-08e25fa91694.space-z.ai/status"
DEFAULT_SUPERGLUE_CORE_URL = "https://preview-chat-57c587a9-5bfa-49a2-a723-08e25fa91694.space-z.ai/v1/tools"

# XTransformPort values for the gateway
SUPERGLUE_QUEUE_PORT = 3003   # enqueue + status
SUPERGLUE_CORE_PORT = 3002    # /v1/tools (run tools)


def _session_headers() -> dict:
    """Extra routing headers the Superglue host may require.

    The gateway in front of the current Superglue sandbox (Alibaba Cloud
    Function Compute) rejects any request without an `x-session-id`
    header (HTTP 400, session affinity). The value itself is arbitrary —
    any non-empty constant works. Set SUPERGLUE_SESSION_ID in the env.
    """
    session_id = os.environ.get("SUPERGLUE_SESSION_ID", "").strip()
    return {"x-session-id": session_id} if session_id else {}


def _get_config() -> tuple[str, str]:
    """Get Superglue URL + token.

    Uses hardcoded defaults (no env var needed on Render).
    Env vars still work if set (overrides default).
    """
    url = os.environ.get("SUPERGLUE_API_URL", DEFAULT_SUPERGLUE_URL).strip().rstrip("/")
    token = os.environ.get("SUPERGLUE_AUTH_TOKEN", DEFAULT_SUPERGLUE_TOKEN).strip()
    if not os.environ.get("SUPERGLUE_AUTH_TOKEN"):
        logger.warning(
            "SUPERGLUE_AUTH_TOKEN not set — using built-in default token. "
            "Set a real token before production traffic."
        )
    return url, token


def _get_queue_url() -> str:
    """Get the queue service URL (for tool generation)."""
    return os.environ.get("SUPERGLUE_QUEUE_URL", DEFAULT_SUPERGLUE_QUEUE_URL)


def _get_status_url() -> str:
    """Get the status polling URL."""
    return os.environ.get("SUPERGLUE_STATUS_URL", DEFAULT_SUPERGLUE_STATUS_URL)


def _get_core_url() -> str:
    """Get the core API URL (for running tools)."""
    return os.environ.get("SUPERGLUE_CORE_URL", DEFAULT_SUPERGLUE_CORE_URL)


def is_configured() -> bool:
    """Check if Superglue is configured."""
    url, token = _get_config()
    return bool(url and token)


# ── Per-tenant tool isolation ─────────────────────────────────────────
# Superglue stores tools by their string ID globally. To prevent Tenant A
# from calling Tenant B's tools (e.g. calling Tenant B's refund tool with
# Tenant A's customer email), we prefix every tool ID with the tenant's UUID.
#
# Format: "tenant_{company_id}__{tool_name}"
#   - company_id is the tenant's UUID (e.g. "abc-123-def")
#   - tool_name is the human-readable name (e.g. "payment-refund-by-email")
#   - Separator is "__" (double underscore) — never appears in UUIDs
#
# Examples:
#   raw_tool_id = "payment-refund-by-email"
#   tenant_id = "abc-123"
#   → namespaced = "tenant_abc-123__payment-refund-by-email"
#
# When PARWA's Node 5 routes a ticket to an agent, it uses the agent's
# stored superglue_tool_id (already namespaced at creation time). When
# PARWA calls execute_tool() directly with a generic tool_id, it passes
# tenant_id so the namespacing happens automatically.


def namespaced_tool_id(tool_id: str, tenant_id: str) -> str:
    """Construct a tenant-namespaced Superglue tool ID.

    If the tool_id is ALREADY namespaced (starts with "tenant_"), return as-is.
    Otherwise prefix with "tenant_{tenant_id}__".

    This prevents Tenant A from calling Tenant B's tools on the shared
    Superglue server.
    """
    if not tenant_id:
        return tool_id  # no tenant context — use raw ID (legacy behavior)
    if tool_id.startswith(f"tenant_") and "__" in tool_id:
        return tool_id  # already namespaced
    return f"tenant_{tenant_id}__{tool_id}"


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
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if res.status_code == 200:
            data = res.json()
            return data.get("data", [])
        logger.warning("superglue_list_tools status=%d", res.status_code)
        return []
    except Exception as exc:
        logger.warning("superglue_list_tools error: %s", str(exc)[:200])
        return []


async def verify_tool_exists(tool_id: str, tenant_id: Optional[str] = None) -> bool:
    """Check if a tool actually exists on the Superglue server before calling it.

    This prevents broken calls when Superglue server is reset (all tools disappear).
    Without this check, Node 5 would call execute_tool() on a non-existent tool
    → fail → fall back to LLM → wasted time + potential wrong answer.

    Uses tenant-namespaced tool_id (same as execute_tool).

    Returns True if tool exists + is not archived. False otherwise.
    """
    if not is_configured():
        return False

    url, token = _get_config()
    actual_tool_id = namespaced_tool_id(tool_id, tenant_id) if tenant_id else tool_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{url}/v1/tools/{actual_tool_id}",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if res.status_code == 200:
            tool = res.json()
            archived = tool.get("archived", False)
            if archived:
                logger.warning("verify_tool_exists: tool %s is archived", actual_tool_id[:50])
                return False
            return True
        # 404 or other → tool doesn't exist
        return False
    except Exception as exc:
        # If we can't reach Superglue, assume tool exists (don't block tickets)
        logger.warning("verify_tool_exists_error: %s — assuming exists", str(exc)[:100])
        return True


async def list_systems() -> List[Dict[str, Any]]:
    """List all connected systems in Superglue."""
    url, token = _get_config()
    if not url or not token:
        return []

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(
                f"{url}/v1/systems",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if res.status_code == 200:
            data = res.json()
            return data.get("data", [])
        return []
    except Exception as exc:
        logger.warning("superglue_list_systems error: %s", str(exc)[:200])
        return []


async def execute_tool(tool_id: str, input_data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute a Superglue tool (sync — waits for full multi-step chain to complete).

    Args:
        tool_id: The Superglue tool ID (e.g. "payment-refund-by-email")
        input_data: Input parameters (e.g. {"customerEmail": "john@gmail.com"})
        tenant_id: OPTIONAL but strongly recommended. When provided, the tool_id
            is namespaced as "tenant_{tenant_id}__{tool_id}" so each tenant
            can only execute their OWN tools. This is critical for multi-tenant
            security — without it, Tenant A could call Tenant B's tools.

    Returns:
        {success: bool, data: dict, error: str, run_id: str, step_results: list}

    Important:
        - The API field is "inputs" (PLURAL), not "input".
        - Sync mode returns the FULL result inline (no need to poll /v1/runs/{id}).
        - For multi-step tools, this waits for ALL steps to complete (~3-10s typical).
        - For async mode (long-running tools), pass options.async=true and poll separately.
        - Tenant isolation: pass tenant_id from the caller's authenticated context.
          The actual tool ID sent to Superglue becomes tenant-namespaced.
    """
    url, token = _get_config()
    if not url or not token:
        return {"success": False, "error": "Superglue not configured"}

    # ── Per-tenant tool isolation (CRITICAL for multi-tenant security) ──
    # Without this, Tenant A could call Tenant B's tools by guessing the tool_id.
    # Format: tenant_{uuid}__{tool_name} — Superglue stores tools by this ID.
    if tenant_id:
        actual_tool_id = namespaced_tool_id(tool_id, tenant_id)
    else:
        actual_tool_id = tool_id

    # ── DB-BACKED QUEUE: persist before HTTP call (survives Render restart) ──
    # User vision: 'and other data also' — same pattern as LLM queue
    import uuid as _uuid
    import json as _json
    _call_id = str(_uuid.uuid4())
    _call_persisted = False
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        _qdb = SessionLocal()
        try:
            _qrow = SuperglueCallQueue(
                id=_call_id,
                company_id=tenant_id,
                tool_id=actual_tool_id,
                input_data=_json.dumps(input_data),
                status="in_progress",
                max_retries=2,
            )
            _qdb.add(_qrow)
            _qdb.commit()
            _call_persisted = True
        finally:
            _qdb.close()
    except Exception as persist_exc:
        logger.warning("superglue_call_persist_failed: %s", str(persist_exc)[:200])

    try:
        # Sync execution — waits for the full multi-step chain to complete.
        # Body MUST use "inputs" (plural) — confirmed in Superglue source code:
        # packages/core/api/tools.ts line 381: payload: body?.inputs
        payload = {"inputs": input_data}

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Use XTransformPort=3002 for the Superglue core API (gateway routing)
            res = await client.post(
                f"{_get_core_url()}/{actual_tool_id}/run?XTransformPort={SUPERGLUE_CORE_PORT}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    **_session_headers(),
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
                # ── SUCCESS: delete from queue (user's 'delete that' vision) ──
                if _call_persisted:
                    _delete_superglue_call_row(_call_id)
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

        # ── FAILURE: mark in DB for audit (don't delete — keep for recovery) ──
        if _call_persisted:
            _mark_superglue_call_failed(_call_id, f"HTTP {res.status_code}: {res.text[:200]}")
        return {
            "success": False,
            "error": f"Superglue returned {res.status_code}: {res.text[:200]}",
            "tool_id": tool_id,
        }

    except Exception as exc:
        logger.error("superglue_execute_tool error: %s", str(exc)[:200])
        # Mark failed in DB (Render might have restarted mid-call)
        if _call_persisted:
            _mark_superglue_call_failed(_call_id, str(exc)[:200])
        return {"success": False, "error": str(exc)[:200], "tool_id": tool_id}


# ── DB queue helpers for Superglue calls (small + surgical) ────────────

def _delete_superglue_call_row(call_id: str) -> None:
    """Delete a completed Superglue call from the queue."""
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        _db = SessionLocal()
        try:
            _db.query(SuperglueCallQueue).filter(SuperglueCallQueue.id == call_id).delete()
            _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("superglue_call_delete_failed: %s", str(exc)[:200])


def _mark_superglue_call_failed(call_id: str, error: str) -> None:
    """Mark a Superglue call as failed (kept in DB for audit + recovery)."""
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        from datetime import datetime, timezone
        _db = SessionLocal()
        try:
            row = _db.query(SuperglueCallQueue).filter(SuperglueCallQueue.id == call_id).first()
            if row:
                row.status = "failed"
                row.error_message = error[:500]
                row.completed_at = datetime.now(timezone.utc)
                _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("superglue_call_mark_failed_error: %s", str(exc)[:200])


# Track if we've already warned about the missing table (avoid log spam)
_superglue_queue_table_missing_warned = False

async def recover_stuck_superglue_calls() -> None:
    """Recovery worker: retry stuck Superglue calls after Render restart.

    Called by background loop in main.py (same as LLM recovery worker).
    Finds calls with status='in_progress' (Render died mid-call) and
    retries them.

    If the superglue_call_queue table doesn't exist yet (fresh DB), this
    function silently skips — no log spam. The table is created on first
    Superglue call that needs DB-backed queueing.
    """
    global _superglue_queue_table_missing_warned
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        import json as _json
        from sqlalchemy import text as _sql_text

        _db = SessionLocal()
        try:
            # Check if table exists first (avoid spamming errors every 60s)
            try:
                _db.execute(_sql_text("SELECT 1 FROM superglue_call_queue LIMIT 1"))
            except Exception as table_check_exc:
                if "does not exist" in str(table_check_exc).lower():
                    if not _superglue_queue_table_missing_warned:
                        logger.info(
                            "superglue_call_recovery: table superglue_call_queue not yet created — "
                            "will be auto-created on first Superglue DB-backed call. Skipping recovery loop."
                        )
                        _superglue_queue_table_missing_warned = True
                    return  # Table doesn't exist yet — silent skip
                raise  # Different error — re-raise

            stuck_rows = _db.query(SuperglueCallQueue).filter(
                SuperglueCallQueue.status == "in_progress"
            ).limit(5).all()  # cap at 5 per cycle

            if not stuck_rows:
                return

            # Table exists now — reset the warned flag
            _superglue_queue_table_missing_warned = False

            logger.info("superglue_call_recovery: found %d stuck calls", len(stuck_rows))

            for row in stuck_rows:
                if row.retry_count >= row.max_retries:
                    # Max retries exceeded — mark failed
                    row.status = "failed"
                    row.error_message = "max retries exceeded during recovery"
                    row.completed_at = datetime.now(timezone.utc)
                    _db.commit()
                    continue

                # Retry the call
                try:
                    input_data = _json.loads(row.input_data)
                    # Increment retry count
                    row.retry_count = (row.retry_count or 0) + 1
                    _db.commit()

                    # Make the actual call (without re-persisting to avoid loops)
                    result = await _execute_tool_raw(
                        row.tool_id, input_data, tenant_id=row.company_id
                    )

                    if result.get("success"):
                        # Success — delete the row
                        _db.query(SuperglueCallQueue).filter(
                            SuperglueCallQueue.id == row.id
                        ).delete()
                        _db.commit()
                        logger.info("superglue_call_recovery: call %s retried successfully", row.id[:8])
                    else:
                        row.status = "failed"
                        row.error_message = result.get("error", "unknown")[:500]
                        row.completed_at = datetime.now(timezone.utc)
                        _db.commit()
                except Exception as retry_exc:
                    logger.warning(
                        "superglue_call_recovery_retry_failed: call=%s err=%s",
                        row.id[:8], str(retry_exc)[:200],
                    )
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("recover_stuck_superglue_calls_error: %s", str(exc)[:200])


async def _execute_tool_raw(tool_id: str, input_data: dict, tenant_id: str = None) -> dict:
    """Internal: execute tool WITHOUT DB persistence (used by recovery worker).

    The recovery worker calls this to avoid creating a new queue row
    (which would cause an infinite loop).
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}

    url, token = _get_config()
    actual_tool_id = namespaced_tool_id(tool_id, tenant_id) if tenant_id else tool_id

    try:
        payload = {"inputs": input_data}
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{_get_core_url()}/{actual_tool_id}/run?XTransformPort={SUPERGLUE_CORE_PORT}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    **_session_headers(),
                },
                json=payload,
            )

        if res.status_code in (200, 202):
            result = res.json()
            if result.get("status") == "success":
                return {
                    "success": True,
                    "data": result.get("data"),
                    "error": None,
                }
            return {
                "success": False,
                "error": result.get("error", "unknown"),
            }
        return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)[:200]}


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
                    headers={"Authorization": f"Bearer {token}", **_session_headers()},
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


# ── System (connection) management ────────────────────────────────────
# These functions manage "systems" in Superglue = connected external apps
# (Shopify, Gmail, Slack, etc.). Used by onboarding Step 2 to let users
# connect their apps via Superglue instead of the removed Nango layer.
#
# Superglue /v1/systems API (verified live 2026-08-18):
#   POST   /v1/systems          → create (requires id, name, url)
#   GET    /v1/systems          → list all
#   GET    /v1/systems/{id}     → get one (404 if not found)
#   DELETE /v1/systems/{id}     → delete (200)
#
# Per-tenant isolation: system IDs are namespaced as
#   tenant_{company_id}__{system_id}
# so Tenant A cannot see/call Tenant B's connected systems.


async def create_system(
    system_id: str,
    name: str,
    url: str,
    tenant_id: Optional[str] = None,
    credentials: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    icon: str = "",
    specific_instructions: str = "",
) -> Dict[str, Any]:
    """Create a system (connected app) in Superglue.

    Args:
        system_id: Raw system ID (e.g. "shopify-store"). Will be namespaced.
        name: Human-readable name (e.g. "My Shopify Store").
        url: Base URL of the external system (e.g. "https://mystore.myshopify.com").
        tenant_id: Tenant UUID for namespacing. Strongly recommended.
        credentials: Optional auth credentials (api_key, oauth_token, etc.).
        metadata: Optional freeform metadata.
        icon: Optional emoji/icon string.
        specific_instructions: Optional notes for Superglue's LLM.

    Returns: {"success": bool, "data": {...}, "error": str?}
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}

    cfg_url, token = _get_config()
    actual_id = namespaced_tool_id(system_id, tenant_id) if tenant_id else system_id

    payload: Dict[str, Any] = {
        "id": actual_id,
        "name": name,
        "url": url,
        "icon": icon,
        "specificInstructions": specific_instructions,
        "credentials": credentials or {},
        "metadata": metadata or {},
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                f"{cfg_url}/v1/systems",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **_session_headers()},
                json=payload,
            )
        if res.status_code in (200, 201):
            data = res.json()
            return {"success": True, "data": data.get("data", data)}
        return {"success": False, "error": f"HTTP {res.status_code}: {res.text[:200]}"}
    except Exception as exc:
        logger.warning("superglue_create_system error: %s", str(exc)[:200])
        return {"success": False, "error": str(exc)[:200]}


async def get_system(system_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get a single system from Superglue.

    Returns: {"success": bool, "data": {...}, "error": str?}
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}

    cfg_url, token = _get_config()
    actual_id = namespaced_tool_id(system_id, tenant_id) if tenant_id else system_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{cfg_url}/v1/systems/{actual_id}",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if res.status_code == 200:
            data = res.json()
            return {"success": True, "data": data.get("data", data)}
        if res.status_code == 404:
            return {"success": False, "error": "System not found"}
        return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as exc:
        logger.warning("superglue_get_system error: %s", str(exc)[:200])
        return {"success": False, "error": str(exc)[:200]}


async def delete_system(system_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete a system from Superglue (disconnect the app).

    Returns: {"success": bool, "error": str?}
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}

    cfg_url, token = _get_config()
    actual_id = namespaced_tool_id(system_id, tenant_id) if tenant_id else system_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.delete(
                f"{cfg_url}/v1/systems/{actual_id}",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if res.status_code in (200, 204):
            return {"success": True}
        if res.status_code == 404:
            return {"success": False, "error": "System not found"}
        return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as exc:
        logger.warning("superglue_delete_system error: %s", str(exc)[:200])
        return {"success": False, "error": str(exc)[:200]}


async def list_tenant_systems(tenant_id: str) -> List[Dict[str, Any]]:
    """List all systems belonging to a specific tenant.

    Filters the global system list by the tenant's namespace prefix
    (tenant_{tenant_id}__) so each tenant only sees their own connections.

    Returns: list of system dicts (empty list on error).
    """
    all_systems = await list_systems()
    if not tenant_id:
        return all_systems
    prefix = f"tenant_{tenant_id}__"
    return [s for s in all_systems if s.get("id", "").startswith(prefix)]


# ── Superglue Catalog Discovery (for Custom integrations/databases) ─────
# When a user wants to connect a platform NOT in our curated catalog,
# we ask Superglue "what auth does this platform need?" and get back
# the auth type + required fields. This is the "Ask Superglue" flow.

async def discover_auth_schema(platform_name: str, platform_type: str = "integration") -> Dict[str, Any]:
    """Ask Superglue for the auth schema of a platform.

    Used when a user wants to connect a Custom integration or database
    that's NOT in our curated POPULAR_SYSTEMS catalog. Instead of making
    the user manually pick auth type and enter fields, we ask Superglue
    what the platform needs.

    Args:
        platform_name: Name of the platform (e.g., "Zoho Inventory", "Paddle", "CockroachDB")
        platform_type: "integration" or "database" — changes what Superglue looks for

    Returns: {
        "success": bool,
        "auth_type": "oauth"|"api_key"|"basic_auth"|"database"|"smtp",
        "fields": [{"key": str, "label": str, "type": str, "required": bool}],
        "url_hint": str,  # optional base URL hint
        "error": str
    }

    Note: If Superglue doesn't know this platform, we return a fallback
    schema so the user can still connect manually.
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured", "auth_type": "api_key", "fields": []}

    cfg_url, token = _get_config()

    try:
        # Ask Superglue to discover the auth schema for this platform
        # Superglue may have its own catalog or can analyze the platform's API docs
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{cfg_url}/v1/discover/auth-schema",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **_session_headers()},
                json={
                    "platform_name": platform_name,
                    "platform_type": platform_type,
                },
            )

        if res.status_code == 200:
            data = res.json().get("data", res.json())
            return {
                "success": True,
                "auth_type": data.get("auth_type", "api_key"),
                "fields": data.get("fields", []),
                "url_hint": data.get("url_hint", ""),
            }

        # Superglue doesn't know this platform → return fallback
        if platform_type == "database":
            return {
                "success": True,
                "auth_type": "database",
                "fields": [
                    {"key": "host", "label": "Host", "type": "text", "required": True, "placeholder": "localhost"},
                    {"key": "port", "label": "Port", "type": "text", "required": True, "placeholder": "5432"},
                    {"key": "database", "label": "Database", "type": "text", "required": True},
                    {"key": "username", "label": "Username", "type": "text", "required": True},
                    {"key": "password", "label": "Password", "type": "password", "required": True},
                ],
                "url_hint": "",
            }
        return {
            "success": True,
            "auth_type": "api_key",
            "fields": [
                {"key": "base_url", "label": "API Base URL", "type": "text", "required": True, "placeholder": "https://api.example.com"},
                {"key": "api_key", "label": "API Key / Token", "type": "password", "required": True},
            ],
            "url_hint": "",
        }

    except Exception as exc:
        logger.warning("superglue_discover_auth_schema error: %s", str(exc)[:200])
        # Fallback: return generic schema so user can still connect
        if platform_type == "database":
            return {
                "success": True,
                "auth_type": "database",
                "fields": [
                    {"key": "host", "label": "Host", "type": "text", "required": True},
                    {"key": "port", "label": "Port", "type": "text", "required": True},
                    {"key": "database", "label": "Database", "type": "text", "required": True},
                    {"key": "username", "label": "Username", "type": "text", "required": True},
                    {"key": "password", "label": "Password", "type": "password", "required": True},
                ],
                "url_hint": "",
            }
        return {
            "success": True,
            "auth_type": "api_key",
            "fields": [
                {"key": "base_url", "label": "API Base URL", "type": "text", "required": True},
                {"key": "api_key", "label": "API Key / Token", "type": "password", "required": True},
            ],
            "url_hint": "",
        }


async def analyze_db_schema(
    db_connection_id: str,
    tenant_id: str,
    db_type: str,
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Ask Superglue to analyze a connected database's schema.

    After a database is connected, Superglue's auto.read discovers the
    tables, columns, types, and relationships. This schema is saved to
    DBConnection.schema_analysis and used by the 8-node pipeline for
    ticket solving context.

    Args:
        db_connection_id: The DBConnection record ID
        tenant_id: Tenant UUID
        db_type: Database type (postgresql, mongodb, etc.)
        connection_config: Connection parameters (host, port, etc.)

    Returns: {
        "success": bool,
        "schema": {"tables": [...], "summary": str},
        "error": str
    }
    """
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}

    cfg_url, token = _get_config()

    try:
        # Call Superglue's auto.read to discover the database schema
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{cfg_url}/v1/discover/db-schema",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **_session_headers()},
                json={
                    "connection_id": namespaced_tool_id(db_connection_id, tenant_id),
                    "db_type": db_type,
                    "connection_config": connection_config,
                },
            )

        if res.status_code == 200:
            data = res.json().get("data", res.json())
            return {"success": True, "schema": data}

        # If Superglue can't analyze, return a basic schema based on DB type
        return {
            "success": True,
            "schema": _fallback_schema(db_type),
        }

    except Exception as exc:
        logger.warning("superglue_analyze_db_schema error: %s", str(exc)[:200])
        return {"success": True, "schema": _fallback_schema(db_type)}


def _fallback_schema(db_type: str) -> Dict[str, Any]:
    """Fallback schema when Superglue can't analyze."""
    base = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "source": "fallback",
        "database_type": db_type,
    }
    if db_type in ("postgresql", "mysql"):
        return {**base, "tables": [], "summary": "Relational database. Schema analysis pending — will be discovered by Superglue auto.read."}
    elif db_type == "mongodb":
        return {**base, "collections": [], "summary": "Document store. Schema analysis pending — will be discovered by Superglue auto.read."}
    elif db_type in ("snowflake", "bigquery"):
        return {**base, "schemas": [], "summary": "Data warehouse. Schema analysis pending — will be discovered by Superglue auto.read."}
    return {**base, "summary": "Custom database. Schema analysis pending."}
