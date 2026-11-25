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

Env vars (set on Render — one URL is enough, the rest derive from it):
  SUPERGLUE_API_URL=https://<your-superglue-host>/sgapi
  SUPERGLUE_AUTH_TOKEN=<set in environment ONLY — never in code>
  SUPERGLUE_LLM_API_KEY=<set in environment ONLY — never in code>  (required by the LLM lane)

SECURITY (2026-09-27): credentials are resolved from the environment ONLY.
No default tokens exist in this file. Missing SUPERGLUE_AUTH_TOKEN disables
all Superglue calls (fail-closed); missing SUPERGLUE_LLM_API_KEY disables
the LLM lane. If a token ever leaks, rotate it on the Superglue side and
update the env var — never paste secrets into source.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from datetime import datetime, timezone

logger = logging.getLogger("parwa.superglue_client")

HTTP_TIMEOUT = 30.0


# ── Default endpoint configuration; credentials are environment-only ──
DEFAULT_SUPERGLUE_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgapi"
DEFAULT_SUPERGLUE_QUEUE_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgq/jobs"
DEFAULT_SUPERGLUE_STATUS_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgq/jobs"
DEFAULT_SUPERGLUE_CORE_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgapi/v1/tools"

# Superglue's own LLM (OpenAI-compatible /sgai/v1) — used by the tool
# generator so PARWA pays $0 for generation. Verified live 2026-09-08.
DEFAULT_SUPERGLUE_LLM_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgai/v1/chat/completions"
# SECURITY: no default LLM key. SUPERGLUE_LLM_API_KEY must come from the env.
DEFAULT_SUPERGLUE_LLM_MODEL = "open-mistral-7b"

# Legacy gateway ports (kept for import compatibility; no longer appended
# to URLs — the new global stack is reached directly over HTTPS).


def _session_headers() -> dict:
    """Extra routing headers the Superglue host may require.

    The gateway in front of the current Superglue sandbox (Alibaba Cloud
    Function Compute) rejects any request without an `x-session-id`
    header (HTTP 400, session affinity). The value itself is arbitrary —
    any non-empty constant works. Set SUPERGLUE_SESSION_ID in the env.
    """
    session_id = os.environ.get("SUPERGLUE_SESSION_ID", "").strip()
    return {"x-session-id": session_id} if session_id else {}


def _get_tenant_api_key(tenant_id: Optional[str]) -> str:
    """Load one tenant's Superglue service-account key; never fall back to admin."""
    if not tenant_id:
        return ""
    try:
        from database.base import SessionLocal
        from app.core.superglue_tenant_accounts import get_tenant_api_key

        db = SessionLocal()
        try:
            return get_tenant_api_key(db, str(tenant_id)) or ""
        finally:
            db.close()
    except Exception as exc:
        logger.error("superglue_tenant_key_lookup_failed: %s", str(exc)[:160])
        return ""


def _get_config() -> tuple[str, str]:
    """Get Superglue URL + token.

    SUPERGLUE_AUTH_TOKEN is the only credential source. If it is absent,
    calls are disabled rather than falling back to a source-code secret.
    """
    url = os.environ.get("SUPERGLUE_API_URL", DEFAULT_SUPERGLUE_URL).strip().rstrip("/")
    token = os.environ.get("SUPERGLUE_AUTH_TOKEN", "").strip()
    if not token:
        logger.error(
            "SUPERGLUE_AUTH_TOKEN is not set — Superglue calls are DISABLED (fail-closed)."
        )
    return url, token


def _stack_root() -> str:
    """Root of the Superglue stack (scheme + host) from the effective API URL.

    SUPERGLUE_API_URL points at the core API, e.g. https://host/sgapi.
    The queue/status services live under the SAME host at /sgq/*, so the
    root (the URL minus its trailing /sgapi) is all we need to rebuild
    them. This makes a tunnel swap a ONE-env-var change on Render: set
    SUPERGLUE_API_URL and queue/status/core follow automatically.

    If the URL doesn't end in /sgapi it is used as the root as-is (the
    new stack contract: /sgapi/v1/* core, /sgq/* queue).
    """
    url, _ = _get_config()
    if url.endswith("/sgapi/"):
        url = url[: -len("/")]
    if url.endswith("/sgapi"):
        url = url[: -len("/sgapi")]
    return url.rstrip("/")


def _get_queue_url() -> str:
    """Queue service URL. SUPERGLUE_QUEUE_URL wins if set; else derive
    from SUPERGLUE_API_URL so a new tunnel host needs only one env var."""
    explicit = os.environ.get("SUPERGLUE_QUEUE_URL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("SUPERGLUE_API_URL", "").strip():
        return _stack_root() + "/sgq/jobs"
    return DEFAULT_SUPERGLUE_QUEUE_URL


def _get_status_url() -> str:
    """Status polling URL. SUPERGLUE_STATUS_URL wins if set; else derive
    from SUPERGLUE_API_URL so a new tunnel host needs only one env var."""
    explicit = os.environ.get("SUPERGLUE_STATUS_URL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("SUPERGLUE_API_URL", "").strip():
        return _stack_root() + "/sgq/jobs"
    return DEFAULT_SUPERGLUE_STATUS_URL


def _get_core_url() -> str:
    """Core API URL (for running tools). SUPERGLUE_CORE_URL wins if set;
    else derive from SUPERGLUE_API_URL so a new tunnel host needs only
    one env var."""
    explicit = os.environ.get("SUPERGLUE_CORE_URL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("SUPERGLUE_API_URL", "").strip():
        return _stack_root() + "/sgapi/v1/tools"
    return DEFAULT_SUPERGLUE_CORE_URL


def _get_llm_url() -> str:
    """Superglue LLM chat-completions URL. SUPERGLUE_LLM_URL wins if set;
    else derive from SUPERGLUE_API_URL (same one-var swap as above)."""
    explicit = os.environ.get("SUPERGLUE_LLM_URL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("SUPERGLUE_API_URL", "").strip():
        return _stack_root() + "/sgai/v1/chat/completions"
    return DEFAULT_SUPERGLUE_LLM_URL


def _get_llm_key() -> str:
    """Superglue LLM API key. The environment is the only credential source."""
    key = os.environ.get("SUPERGLUE_LLM_API_KEY", "").strip()
    if not key:
        logger.error(
            "SUPERGLUE_LLM_API_KEY is not set — Superglue LLM lane DISABLED (fail-closed)."
        )
    return key


def _get_llm_model() -> str:
    """Superglue LLM model id. SUPERGLUE_LLM_MODEL wins if set."""
    return os.environ.get("SUPERGLUE_LLM_MODEL", DEFAULT_SUPERGLUE_LLM_MODEL).strip()


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

    url, admin_token = _get_config()
    token = _get_tenant_api_key(tenant_id) if tenant_id else admin_token
    if not url or not token:
        return False
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
        # Never mark an unverified tool as production-ready or execute it blindly.
        logger.warning("verify_tool_exists_error: %s", str(exc)[:100])
        return False


async def get_tenant_tool_ids(tenant_id: Optional[str] = None) -> set:
    """Return the set of tool ids that BELONG to this tenant.

    Tools saved via generate_tool_for_agent(tenant_id=...) are stored as
    "tenant_{tenant_id}__{name}". This helper lists the Superglue server,
    keeps only ids carrying THIS tenant's namespace, and strips the prefix
    so callers can compare RAW ids (as an LLM would output them) against
    what actually exists.

    Returns BOTH forms per tool (raw + namespaced) so either style matches:
        {"order-status-check", "tenant_52bb..__order-status-check", ...}

    Never raises; on any error returns an empty set (caller then refuses
    to execute — safe default for multi-tenant isolation).
    """
    if not tenant_id:
        return set()
    prefix = f"tenant_{tenant_id}__"
    try:
        tools = await list_tools()
    except Exception as exc:
        logger.warning("get_tenant_tool_ids error: %s", str(exc)[:200])
        return set()
    ids: set = set()
    for tool in tools:
        if tool.get("archived", False):
            continue
        tid = tool.get("id", "") or ""
        if tid.startswith(prefix):
            ids.add(tid)
            ids.add(tid[len(prefix):])  # raw form too
    return ids


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
        tenant_id: REQUIRED authenticated tenant ID. The tool_id is namespaced
            as "tenant_{tenant_id}__{tool_id}" and executed with that tenant's
            dedicated Superglue service-account key.

    Returns:
        {success: bool, data: dict, error: str, run_id: str, step_results: list}

    Important:
        - The API field is "inputs" (PLURAL), not "input".
        - Sync mode returns the FULL result inline (no need to poll /v1/runs/{id}).
        - For multi-step tools, this waits for ALL steps to complete (~3-10s typical).
        - For async mode (long-running tools), pass options.async=true and poll separately.
        - Tenant isolation: tenant_id and its service-account key are mandatory.
    """
    url, _admin_token = _get_config()
    if not tenant_id:
        return {"success": False, "error": "Tenant context is required for tool execution"}
    token = _get_tenant_api_key(tenant_id)
    if not url or not token:
        return {"success": False, "error": "Tenant Superglue credentials are unavailable"}

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
    from shared.utils.token_encryption import encrypt_token
    _call_id = str(_uuid.uuid4())
    _call_persisted = False
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        _qdb = SessionLocal()
        try:
            if tenant_id and _qdb.bind and _qdb.bind.dialect.name == "postgresql":
                from sqlalchemy import text as _tenant_sql
                _qdb.execute(
                    _tenant_sql("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": tenant_id},
                )
            _qrow = SuperglueCallQueue(
                id=_call_id,
                company_id=tenant_id,
                tool_id=actual_tool_id,
                input_data=encrypt_token(_json.dumps(input_data)),
                status="in_progress",
                max_retries=2,
            )
            _qdb.add(_qrow)
            _qdb.commit()
            _call_persisted = True
        finally:
            _qdb.close()
    except Exception as persist_exc:
        logger.error("superglue_call_persist_failed; refusing external execution: %s", str(persist_exc)[:200])

    if not _call_persisted:
        return {
            "success": False,
            "error": "Durable tenant call queue is unavailable; action was not executed",
        }

    try:
        # Sync execution — waits for the full multi-step chain to complete.
        # Body MUST use "inputs" (plural) — confirmed in Superglue source code:
        # packages/core/api/tools.ts line 381: payload: body?.inputs
        payload = {"inputs": input_data}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            **_session_headers(),
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Shape A (new stack, verified live 2026-09-07):
            #   POST /v1/tools/{toolId}/run  → 200 {status, data, stepResults}
            res = await client.post(
                f"{_get_core_url()}/{actual_tool_id}/run",
                headers=headers,
                json=payload,
            )
            # Shape B fallback (deployments without the per-tool route):
            #   GET tool config, then POST /v1/tools/run with inline config.
            if res.status_code == 404:
                cfg_res = await client.get(
                    f"{_get_core_url()}/{actual_tool_id}", headers=headers
                )
                if cfg_res.status_code == 200:
                    tool_cfg = cfg_res.json()
                    if isinstance(tool_cfg, dict) and "data" in tool_cfg:
                        tool_cfg = tool_cfg["data"]
                    res = await client.post(
                        f"{_get_core_url()}/run",
                        headers=headers,
                        json={"tool": tool_cfg, "inputs": input_data},
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
                    _delete_superglue_call_row(_call_id, tenant_id)
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
                return await _poll_run_status(run_id, tool_id=tool_id, tenant_id=tenant_id)

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
            _mark_superglue_call_failed(_call_id, f"HTTP {res.status_code}", tenant_id)
        return {
            "success": False,
            "error": f"Superglue returned HTTP {res.status_code}",
            "tool_id": tool_id,
        }

    except Exception as exc:
        logger.error("superglue_execute_tool error: %s", str(exc)[:200])
        # Mark failed in DB (Render might have restarted mid-call)
        if _call_persisted:
            _mark_superglue_call_failed(_call_id, str(exc)[:200], tenant_id)
        return {"success": False, "error": str(exc)[:200], "tool_id": tool_id}


# ── DB queue helpers for Superglue calls (small + surgical) ────────────

def _delete_superglue_call_row(call_id: str, tenant_id: Optional[str] = None) -> None:
    """Delete a completed Superglue call from the queue."""
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        from sqlalchemy import text
        _db = SessionLocal()
        try:
            if tenant_id and _db.bind and _db.bind.dialect.name == "postgresql":
                _db.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})
            query = _db.query(SuperglueCallQueue).filter(SuperglueCallQueue.id == call_id)
            if tenant_id:
                query = query.filter(SuperglueCallQueue.company_id == tenant_id)
            query.delete()
            _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("superglue_call_delete_failed: %s", str(exc)[:200])


def _mark_superglue_call_failed(call_id: str, error: str, tenant_id: Optional[str] = None) -> None:
    """Mark a Superglue call as failed (kept in DB for audit + recovery)."""
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        from datetime import datetime, timezone
        from sqlalchemy import text
        _db = SessionLocal()
        try:
            if tenant_id and _db.bind and _db.bind.dialect.name == "postgresql":
                _db.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})
            query = _db.query(SuperglueCallQueue).filter(SuperglueCallQueue.id == call_id)
            if tenant_id:
                query = query.filter(SuperglueCallQueue.company_id == tenant_id)
            row = query.first()
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

    The queue is provisioned by Alembic. If an older deployment has not
    applied the migration yet, this function silently skips — no log spam.
    """
    global _superglue_queue_table_missing_warned
    try:
        from database.base import SessionLocal
        from database.models.core import SuperglueCallQueue
        import json as _json
        from sqlalchemy import text as _sql_text

        from app.core.tenant_context import tenant_bypass
        with tenant_bypass(reason="Superglue queue recovery worker"):
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
                        if row.company_id and getattr(_db, "bind", None) and _db.bind.dialect.name == "postgresql":
                            _db.execute(
                                _sql_text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                {"tenant_id": str(row.company_id)},
                            )
                        row.status = "failed"
                        row.error_message = "max retries exceeded during recovery"
                        row.completed_at = datetime.now(timezone.utc)
                        _db.commit()
                        continue

                    # Retry the call
                    try:
                        # New rows are encrypted at rest. Support legacy plaintext
                        # rows during the rolling migration, then rewrite them encrypted.
                        try:
                            from shared.utils.token_encryption import decrypt_token, encrypt_token
                            decrypted_payload = decrypt_token(row.input_data)
                            input_data = _json.loads(decrypted_payload)
                        except Exception:
                            try:
                                input_data = _json.loads(row.input_data)
                                from shared.utils.token_encryption import encrypt_token
                                row.input_data = encrypt_token(_json.dumps(input_data))
                            except Exception:
                                if row.company_id and getattr(_db, "bind", None) and _db.bind.dialect.name == "postgresql":
                                    _db.execute(
                                        _sql_text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                        {"tenant_id": str(row.company_id)},
                                    )
                                row.status = "failed"
                                row.error_message = "queued payload could not be decrypted"
                                row.completed_at = datetime.now(timezone.utc)
                                _db.commit()
                                continue

                        # Set tenant RLS context before modifying this tenant's queue row.
                        if row.company_id and getattr(_db, "bind", None) and _db.bind.dialect.name == "postgresql":
                            _db.execute(
                                _sql_text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                {"tenant_id": str(row.company_id)},
                            )
                        row.retry_count = (row.retry_count or 0) + 1
                        _db.commit()

                        # Make the actual call (without re-persisting to avoid loops)
                        result = await _execute_tool_raw(
                            row.tool_id, input_data, tenant_id=row.company_id
                        )

                        if result.get("success"):
                            # Success — delete the row
                            if row.company_id and getattr(_db, "bind", None) and _db.bind.dialect.name == "postgresql":
                                _db.execute(
                                    _sql_text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                    {"tenant_id": str(row.company_id)},
                                )
                            _db.query(SuperglueCallQueue).filter(
                                SuperglueCallQueue.id == row.id,
                                SuperglueCallQueue.company_id == row.company_id,
                            ).delete()
                            _db.commit()
                            logger.info("superglue_call_recovery: call %s retried successfully", row.id[:8])
                        else:
                            if row.company_id and getattr(_db, "bind", None) and _db.bind.dialect.name == "postgresql":
                                _db.execute(
                                    _sql_text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                    {"tenant_id": str(row.company_id)},
                                )
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

    url, _admin_token = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "error": "Tenant Superglue credentials are unavailable"}
    actual_tool_id = namespaced_tool_id(tool_id, tenant_id) if tenant_id else tool_id

    try:
        payload = {"inputs": input_data}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            **_session_headers(),
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{_get_core_url()}/{actual_tool_id}/run",
                headers=headers,
                json=payload,
            )
            if res.status_code == 404:
                cfg_res = await client.get(
                    f"{_get_core_url()}/{actual_tool_id}", headers=headers
                )
                if cfg_res.status_code == 200:
                    tool_cfg = cfg_res.json()
                    if isinstance(tool_cfg, dict) and "data" in tool_cfg:
                        tool_cfg = tool_cfg["data"]
                    res = await client.post(
                        f"{_get_core_url()}/run",
                        headers=headers,
                        json={"tool": tool_cfg, "inputs": input_data},
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


async def _poll_run_status(run_id: str, tool_id: str = "", tenant_id: Optional[str] = None, max_polls: int = 30, interval: float = 2.0) -> Dict[str, Any]:
    """Poll a Superglue run until it completes (success/failed) or times out.

    Used for async-execution tools that return status=running.
    Returns the same shape as execute_tool():
        {success, data, error, run_id, step_results, tool_id}
    """
    url, admin_token = _get_config()
    # Superglue service accounts can execute tools but cannot read run history.
    # This run_id is returned by the immediately preceding tenant-authenticated
    # execute request, never supplied by a user; use the server admin key only
    # to retrieve that single run's completion result.
    if not url or not admin_token:
        return {"success": False, "error": "Superglue run status is unavailable", "run_id": run_id, "tool_id": tool_id}
    token = admin_token

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


async def get_available_tools_description(tenant_id: Optional[str] = None) -> str:
    """Get a human-readable description of available tools for the LLM.

    This is what PARWA's LLM sees to decide which tool to call.
    Includes: tool ID, name, instruction (what it does), required inputs.
    Skips archived tools.

    2026-09 tenant isolation: when tenant_id is provided, ONLY that
    tenant's tools ("tenant_{tenant_id}__*" ids) are shown — previously
    every tenant's LLM could see and pick ANOTHER tenant's raw tool ids
    (cross-tenant leak + guaranteed 404 on execute).
    """
    tools = await list_tools()
    if tenant_id:
        prefix = f"tenant_{tenant_id}__"
        tools = [t for t in tools if str(t.get("id", "")).startswith(prefix)]
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
    system_id: str, name: str, url: str, tenant_id: Optional[str] = None,
    credentials: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None,
    icon: str = "", specific_instructions: str = "",
    customer_api_key: Optional[str] = None, credential_url: Optional[str] = None,
    template_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create/update a connection owned by exactly one Superglue tenant account."""
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}
    cfg_url, _ = _get_config()
    token = customer_api_key or _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "error": "Tenant Superglue service account is unavailable"}

    meta = metadata or {}
    auth_type = str(meta.get("auth_type") or "api_key").lower()
    connection_url = credential_url or url
    if auth_type == "oauth":
        # OAuth exchange creates the provider connection after user consent.
        return {"success": True, "pending_oauth": True, "data": {
            "id": system_id, "systemId": system_id, "name": name,
            "url": connection_url, "icon": icon, "metadata": meta,
        }}

    authentication = {"type": "none"} if auth_type in {"database", "smtp"} else {"type": "api_key"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", **_session_headers()}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            existing_response = await client.get(
                f"{cfg_url}/v1/connections", headers=headers, params={"systemId": system_id}
            )
            existing = None
            if existing_response.status_code == 200:
                body = existing_response.json()
                data = body.get("data", body) if isinstance(body, dict) else {}
                if isinstance(data, list):
                    existing = next((x for x in data if isinstance(x, dict) and x.get("systemId") == system_id), None)
                elif isinstance(data, dict):
                    items = data.get("connections")
                    if isinstance(items, list):
                        existing = next((x for x in items if isinstance(x, dict) and x.get("systemId") == system_id), None)
                    else:
                        existing = data.get("connection")

            request_body = {
                "systemId": system_id, "name": name, "url": connection_url,
                "authentication": authentication, "credentials": credentials or {},
            }
            if isinstance(existing, dict) and existing.get("id"):
                response = await client.patch(
                    f"{cfg_url}/v1/connections/{existing['id']}", headers=headers, json=request_body
                )
            else:
                response = await client.post(
                    f"{cfg_url}/v1/connections", headers=headers, json=request_body
                )
        if response.status_code not in (200, 201):
            logger.error("superglue_connection_write_failed system=%s status=%s", system_id[:80], response.status_code)
            return {"success": False, "error": f"Could not save tenant connection (HTTP {response.status_code})"}
        body = response.json()
        data = body.get("data", body) if isinstance(body, dict) else {}
        return {"success": True, "data": data}
    except Exception as exc:
        logger.warning("superglue_create_connection_error: %s", str(exc)[:160])
        return {"success": False, "error": "Could not save tenant connection"}

async def get_system(system_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Read a tenant-owned connection; never use the organization admin key."""
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}
    cfg_url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "error": "Tenant Superglue credentials are unavailable"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{cfg_url}/v1/connections", headers={"Authorization": f"Bearer {token}", **_session_headers()},
                params={"systemId": system_id},
            )
        if response.status_code == 404:
            return {"success": False, "error": "Connection not found"}
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}"}
        body = response.json()
        data = body.get("data", body) if isinstance(body, dict) else {}
        if isinstance(data, list):
            connection = next((x for x in data if isinstance(x, dict) and x.get("systemId") == system_id), None)
        elif isinstance(data, dict):
            items = data.get("connections")
            connection = next((x for x in items if isinstance(x, dict) and x.get("systemId") == system_id), None) if isinstance(items, list) else data.get("connection") or data
        else:
            connection = None
        if not isinstance(connection, dict) or not connection:
            return {"success": False, "error": "Connection not found"}
        safe = {k: connection[k] for k in ("id", "systemId", "name", "url", "authentication", "credentialKeys", "createdAt", "updatedAt") if k in connection}
        return {"success": True, "data": safe}
    except Exception as exc:
        logger.warning("superglue_get_connection_error: %s", str(exc)[:160])
        return {"success": False, "error": "Could not read tenant connection"}

async def delete_system(system_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete only this tenant's connection for the selected system ID."""
    return await delete_tenant_credentials(system_id, str(tenant_id or ""))

async def list_tenant_systems(tenant_id: str) -> List[Dict[str, Any]]:
    """List only connections visible to the tenant service account."""
    if not is_configured() or not tenant_id:
        return []
    cfg_url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{cfg_url}/v1/connections",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        if response.status_code != 200:
            return []
        body = response.json()
        data = body.get("data", body) if isinstance(body, dict) else []
        if isinstance(data, dict):
            data = data.get("connections", [])
        return [
            {k: item[k] for k in ("id", "systemId", "name", "url", "authentication", "credentialKeys") if k in item}
            for item in data if isinstance(item, dict)
        ] if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("superglue_list_tenant_connections_error: %s", str(exc)[:160])
        return []

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

    cfg_url = _get_config()[0]
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "schema": None, "error": "Tenant Superglue credentials are unavailable"}

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


async def delete_tenant_credentials(system_id: str, tenant_id: str) -> Dict[str, Any]:
    """Revoke only this tenant's credential connection; keep shared system definitions."""
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}
    url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "error": "Tenant Superglue credentials are unavailable"}

    headers = {"Authorization": f"Bearer {token}", **_session_headers()}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{url}/v1/connections",
                headers=headers,
                params={"systemId": system_id},
            )
            if response.status_code == 404:
                return {"success": True}
            if response.status_code != 200:
                return {"success": False, "error": f"Could not inspect tenant connection (HTTP {response.status_code})"}
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            if isinstance(data, list):
                connection = next(
                    (item for item in data if isinstance(item, dict) and item.get("systemId") == system_id),
                    None,
                )
            elif isinstance(data, dict):
                connections = data.get("connections")
                if isinstance(connections, list):
                    connection = next(
                        (item for item in connections if isinstance(item, dict) and item.get("systemId") == system_id),
                        None,
                    )
                else:
                    connection = data.get("connection") or data
            else:
                connection = None
            connection_id = connection.get("id") if isinstance(connection, dict) else None
            if not connection_id:
                return {"success": True}
            deleted = await client.delete(
                f"{url}/v1/connections/{connection_id}",
                headers=headers,
            )
            return {"success": deleted.status_code in (200, 204, 404)}
    except Exception as exc:
        logger.warning("superglue_tenant_credential_delete_error: %s", str(exc)[:160])
        return {"success": False, "error": "Could not revoke tenant connection"}


async def start_oauth_exchange(
    system_id: str,
    tenant_id: str,
    oauth_app_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Start Superglue-managed OAuth using this tenant's service account."""
    if not is_configured():
        return {"success": False, "error": "Superglue not configured"}
    url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {"success": False, "error": "Tenant Superglue service account is unavailable"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        **_session_headers(),
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            selected_app_id = oauth_app_id
            if not selected_app_id:
                apps_response = await client.get(
                    f"{url}/v1/oauth-apps",
                    headers={"Authorization": f"Bearer {token}", **_session_headers()},
                    params={"systemId": system_id},
                )
                if apps_response.status_code == 200:
                    apps_payload = apps_response.json()
                    apps_data = apps_payload.get("data", apps_payload) if isinstance(apps_payload, dict) else []
                    if isinstance(apps_data, dict):
                        apps_data = apps_data.get("oauthApps") or apps_data.get("apps") or []
                    if isinstance(apps_data, list):
                        selected = next(
                            (
                                item for item in apps_data
                                if isinstance(item, dict) and item.get("id")
                            ),
                            None,
                        )
                        if selected:
                            selected_app_id = str(selected["id"])

            payload: Dict[str, Any] = {"systemId": system_id}
            if selected_app_id:
                payload["oauthAppId"] = selected_app_id
            response = await client.post(
                f"{url}/v1/oauth/exchanges",
                headers=headers,
                json=payload,
            )
        if response.status_code not in (200, 201):
            logger.warning("superglue_oauth_start_failed system=%s status=%s", system_id, response.status_code)
            return {
                "success": False,
                "error": f"Superglue OAuth could not start (HTTP {response.status_code})",
            }
        body = response.json()
        data = body.get("data", body) if isinstance(body, dict) else {}
        authorization_url = data.get("authorizationUrl") or data.get("authorization_url")
        if not authorization_url:
            return {"success": False, "error": "Superglue did not return an authorization URL"}
        return {"success": True, "authorization_url": authorization_url}
    except Exception as exc:
        logger.warning("superglue_oauth_start_error: %s", str(exc)[:160])
        return {"success": False, "error": "Could not start provider authorization"}

async def check_oauth_credentials(system_id: str, tenant_id: str) -> Dict[str, Any]:
    """Check the tenant's Superglue connection without returning secret values."""
    if not is_configured():
        return {"success": False, "connected": False, "error": "Superglue not configured"}
    url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {
            "success": False,
            "connected": False,
            "error": "Tenant Superglue service account is unavailable",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{url}/v1/connections",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
                params={"systemId": system_id},
            )
        if response.status_code == 404:
            return {"success": True, "connected": False}
        if response.status_code != 200:
            return {
                "success": False,
                "connected": False,
                "error": f"Could not verify provider connection (HTTP {response.status_code})",
            }

        payload = response.json()
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, list):
            connection = next(
                (
                    item for item in data
                    if isinstance(item, dict) and item.get("systemId") == system_id
                ),
                None,
            )
        elif isinstance(data, dict):
            connections = data.get("connections")
            if isinstance(connections, list):
                connection = next(
                    (
                        item for item in connections
                        if isinstance(item, dict) and item.get("systemId") == system_id
                    ),
                    None,
                )
            else:
                connection = data.get("connection") or data
        else:
            connection = None

        keys = connection.get("credentialKeys", []) if isinstance(connection, dict) else []
        has_access_token = False
        if isinstance(keys, dict):
            entry = keys.get("access_token")
            has_access_token = bool(
                entry.get("hasValue") if isinstance(entry, dict) else entry
            )
        elif isinstance(keys, list):
            has_access_token = any(
                isinstance(entry, dict)
                and (entry.get("key") or entry.get("name")) == "access_token"
                and entry.get("hasValue") is True
                for entry in keys
            )
        return {"success": True, "connected": has_access_token}
    except Exception as exc:
        logger.warning("superglue_oauth_status_error: %s", str(exc)[:160])
        return {
            "success": False,
            "connected": False,
            "error": "Could not check provider authorization",
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

    cfg_url, _ = _get_config()
    token = _get_tenant_api_key(tenant_id)
    if not token:
        return {
            "success": False,
            "schema": None,
            "error": "Tenant Superglue credentials are unavailable",
        }

    try:
        # Call Superglue's auto.read with the tenant identity. Database
        # connection secrets must never be sent using the organization key.
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{cfg_url}/v1/discover/db-schema",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **_session_headers()},
                json={
                    "connection_id": db_connection_id,
                    "db_type": db_type,
                    "connection_config": connection_config,
                },
            )

        if res.status_code == 200:
            payload = res.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            if isinstance(data, dict) and isinstance(data.get("schema"), dict):
                data = data["schema"]
            has_objects = isinstance(data, dict) and any(
                isinstance(data.get(key), list) and len(data[key]) > 0
                for key in ("tables", "collections", "schemas")
            )
            if has_objects and data.get("source") != "fallback":
                return {"success": True, "schema": data}
            return {
                "success": False,
                "schema": None,
                "error": "Superglue returned no verified tables, collections, or schemas",
            }

        # Never report a generic fallback as a successful discovery. Agents
        # must not treat an unknown schema as verified or invent table names.
        return {
            "success": False,
            "schema": None,
            "error": f"Superglue schema discovery failed (HTTP {res.status_code})",
        }

    except Exception as exc:
        logger.warning("superglue_analyze_db_schema error: %s", str(exc)[:200])
        return {"success": False, "schema": None, "error": str(exc)[:200]}


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
