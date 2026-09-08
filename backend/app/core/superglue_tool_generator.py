"""
Superglue Tool Generator — PARWA's bridge to Superglue tool generation.

PARWA's Builder Agent creates AI agents (instructions, restrictions, capabilities).
For each agent that needs API actions (refund, cancel, etc.), PARWA asks Superglue
to GENERATE a multi-step tool. Superglue's OWN LLM does the design work.

This keeps Render's 512MB RAM free — PARWA just makes an HTTP call, Superglue does
the heavy LLM work on a separate server with a separate rate limit pool.

Flow (stable stack, verified live 2026-09-08):
  1. Builder Agent creates AI agent config (PARWA's NVIDIA GLM-5.2)
  2. Builder Agent calls generate_tool_for_agent() below
  3. PARWA POSTs the tool request DIRECTLY to Superglue's OpenAI-compatible
     LLM (/sgai/v1/chat/completions, model open-mistral-7b, sgai_… key).
     The /sgq/jobs queue CANNOT do this — it is a serial API-job executor
     that only reaches /sgapi/v1/* paths ("/sgai/…" is rejected at enqueue,
     "/v1/chat/completions" 404s server-side; both verified).
  4. PARWA parses the tool JSON, validates it, and saves it via
     POST /v1/tools (verified 201).
  5. Superglue returns the saved tool → PARWA saves tool_id in
     AIAgentAssignment.superglue_tool_id
  6. Fallback on any primary failure: PARWA's own NVIDIA LLM generates the
     tool JSON and it is saved the same way (one-time cost per agent).

Cost: $0 on PARWA side for the primary path (LLM cost absorbed by Superglue).

Env vars (one URL is enough — the rest derive from it):
  SUPERGLUE_API_URL=https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgapi
  SUPERGLUE_AUTH_TOKEN=sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b
  SUPERGLUE_LLM_API_KEY=sgai_39ff17e8bca987faa7fb31c92d952ee0d9fe021fea592c4f  (optional)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.superglue_client import (
    _get_config,
    _get_llm_key,
    _get_llm_model,
    _get_llm_url,
    _session_headers,
    is_configured,
)

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
        sample_ticket: A real ticket text that triggered this agent (helps design the tool)
        tenant_integrations: Integrations the tenant has connected
            (e.g. {"paddle": {"api_key": "pdl_..."}})

    Returns:
        {
            success: bool,
            tool_id: str | None,      # the Superglue tool ID to save
            tool_definition: dict,    # the full JSON for audit
            error: str | None
        }
    """
    if not is_configured():
        return {
            "success": False,
            "error": "Superglue not configured — set SUPERGLUE_API_URL + SUPERGLUE_AUTH_TOKEN",
            "tool_id": None,
            "tool_definition": None,
        }

    instruction = _build_tool_instruction(
        agent_name, agent_instructions, agent_capabilities, sample_ticket, tenant_integrations
    )

    # ── PRIMARY: Superglue's own LLM designs the tool (OpenAI-compatible
    # /sgai/v1, Superglue's key — $0 on PARWA side). The queue CANNOT do
    # this: it is a serial API-job executor that only reaches /sgapi/v1/*
    # paths (verified: "/sgai/…" rejected at enqueue, "/v1/chat/…" 404s
    # server-side). Generation goes DIRECT to the LLM; the resulting JSON
    # is then saved via POST /v1/tools (verified 201).
    try:
        result = await _generate_tool_via_superglue_llm(instruction, agent_name)
        if result.get("success"):
            return result
        logger.warning(
            "superglue_llm_generation_failed: agent=%s — falling back to PARWA LLM: %s",
            agent_name, result.get("error"),
        )
    except Exception as exc:
        logger.warning(
            "superglue_llm_generation_error: agent=%s — falling back to PARWA LLM: %s",
            agent_name, str(exc)[:200],
        )

    # ── FALLBACK: PARWA's own LLM generates the tool (one-time cost per
    # agent creation, not per ticket). Also covers any Superglue outage.
    return await _generate_tool_via_parwa_llm(
        agent_name=agent_name,
        agent_instructions=agent_instructions,
        agent_capabilities=agent_capabilities,
        sample_ticket=sample_ticket,
        tenant_integrations=tenant_integrations,
    )


_TOOL_JSON_SPEC = """{
  "id": "tool-id-kebab-case",
  "name": "Human Readable Name",
  "instruction": "What this tool does",
  "inputSchema": {
    "type": "object",
    "properties": {
      "customerEmail": {"type": "string", "description": "Customer email"}
    },
    "required": ["customerEmail"]
  },
  "steps": [
    {
      "id": "step1",
      "instruction": "What this step does",
      "config": {
        "type": "request",
        "method": "GET",
        "url": "https://api.example.com/endpoint",
        "headers": {}
      }
    }
  ],
  "outputTransform": "(sourceData) => ({ result: sourceData.step1.data })"
}

HARD RULES (violations are rejected by validation):
  - Every step config "type" MUST be exactly "request" or "transform".
    No other step types exist.
  - "request" config fields: type, method (GET/POST/PUT/PATCH/DELETE),
    url, headers (object, optional), queryParams (object, optional),
    body (string, optional), systemId (string, optional).
  - "transform" config fields: type ("transform"), transformCode
    (a single "(sourceData) => ..." expression string).
  - Step ids: lowercase snake_case (step1, step2, ...).
  - JSON strings must be single-line — NEVER put raw newlines inside a
    string value.
  - Inside transformCode / outputTransform / url arrow-function strings use
    ONLY SINGLE QUOTES for JS strings (e.g. 'No posts found') — NEVER
    double quotes.

TRANSFORM RULE (critical - prevents invalid JSON):
  - If a step needs "transformCode", or you need "outputTransform", DO NOT
    write JavaScript inside the JSON. Set the value to a marker instead:
      "transformCode": "@@T1@@"   (use T1, T2, ... in order)
    Then AFTER the JSON, add ONE fenced js block defining each marker as a
    single-expression arrow function, e.g.:
    ```js
    @@T1@@ = (sourceData) => sourceData.step1.data.map(p => p.title)
    ```
    Use single quotes in JS. Never put raw newlines inside JSON strings.

Template syntax for URLs:
  - Tool input ref: <<customerEmail>>
  - Step result ref: <<(sourceData) => 'https://api.x.com/' + sourceData.stepId.data.path>>
  - For Paddle (wraps items in data[]): sourceData.stepId.data.data[0].id
  - ALWAYS end with >> (double chevron)"""


def _parse_tool_json(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract and validate the tool JSON from an LLM response.

    Handles markdown fences and surrounding prose, and repairs the most
    common small-LLM defect: RAW control characters (newlines/tabs) inside
    JSON string literals — e.g. multi-line outputTransform arrow functions,
    which strict json.loads rejects. Returns None if no structurally valid
    tool can be recovered.
    """
    import re as _re

    cleaned = response_text.strip()
    # Prefer an explicit ```json fenced block (the response may continue
    # with a separate ```js block whose braces must NOT pollute extraction)
    mj = _re.search(r'```json\s*([\s\S]*?)```', cleaned)
    if mj:
        candidate = mj.group(1).strip()
    else:
        # Drop a single leading/trailing fence, then extract the FIRST
        # balanced top-level JSON object (string-aware brace counting)
        cleaned = _re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', cleaned)
        cleaned = _re.sub(r'\s*```\s*$', '', cleaned)
        start = cleaned.find('{')
        if start < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        end = -1
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        if end < 0:
            return None
        candidate = cleaned[start:end]

    def _loads(text: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(text)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _valid(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if data and data.get("id") and data.get("steps"):
            return data
        return None

    # Fast path: strict JSON
    result = _valid(_loads(candidate))
    if result:
        return result

    # Repair ladder — first pass that yields a valid tool wins.
    # Pass 1: escape raw control characters inside JSON strings.
    # Pass 2: pass 1 + embedded-quote tolerance (JS code inside string
    # values contains " that is NOT a JSON terminator — see below).
    def _escape_newlines(text: str) -> str:
        out: list = []
        in_string = False
        escaped = False
        for ch in text:
            if in_string:
                if escaped:
                    escaped = False
                    out.append(ch)
                elif ch == '\\':
                    escaped = True
                    out.append(ch)
                elif ch == '"':
                    in_string = False
                    out.append(ch)
                elif ch == '\n':
                    out.append('\\n')
                elif ch == '\r':
                    out.append('\\r')
                elif ch == '\t':
                    out.append('\\t')
                else:
                    out.append(ch)
            else:
                if ch == '"':
                    in_string = True
                out.append(ch)
        return ''.join(out)

    def _escape_newlines_and_quotes(text: str) -> str:
        """Pass 1 + embedded-quote tolerance.

        LLMs put JS code inside JSON string values (transformCode,
        outputTransform). Double quotes in that JS are NOT JSON string
        terminators. Heuristic: a quote inside a string is the real
        terminator only if followed (after optional spaces) by , } ] :
        or end-of-line-then-structure; otherwise it is embedded code
        and gets escaped.
        """
        out2: list = []
        i, n = 0, len(text)
        in_string = False
        key_position = False   # True iff current string opened after { or ,
        last_sig = ''          # last significant (non-ws) char outside strings
        while i < n:
            ch = text[i]
            if not in_string:
                if ch == '"':
                    in_string = True
                    key_position = last_sig in '{,'
                out2.append(ch)
                if ch not in ' \t\r\n':
                    last_sig = ch
                i += 1
                continue
            if ch == '\\':
                out2.append(ch)
                if i + 1 < n:
                    out2.append(text[i + 1])
                    i += 2
                else:
                    i += 1
                continue
            if ch == '\n':
                out2.append('\\n')
                i += 1
                continue
            if ch == '\r':
                out2.append('\\r')
                i += 1
                continue
            if ch == '\t':
                out2.append('\\t')
                i += 1
                continue
            if ch == '"':
                j = i + 1
                while j < n and text[j] in ' \t':
                    j += 1
                terminator = False
                if j >= n:
                    terminator = True
                elif text[j] in ',}]' or (text[j] == ':' and key_position):
                    # value-position strings: ", " (comma then quote) inside
                    # the value is JS code like foo("a", "b") — not JSON
                    if (not key_position and text[j] == ','):
                        k = j + 1
                        while k < n and text[k] in ' \t':
                            k += 1
                        if k < n and text[k] == '"':
                            out2.append('\\"')
                            i += 1
                            continue  # embedded JS quote, keep in string
                    terminator = True
                    terminator = True
                elif text[j] == '\n':
                    k = j + 1
                    while k < n and text[k] in ' \t':
                        k += 1
                    terminator = k >= n or text[k] in ',}]'
                if terminator:
                    in_string = False
                    out2.append(ch)
                else:
                    out2.append('\\"')
                i += 1
                continue
            out2.append(ch)
            i += 1
        return ''.join(out2)

    for repaired in (
        _escape_newlines(candidate),
        _escape_newlines_and_quotes(candidate),
    ):
        result = _valid(_loads(repaired))
        if result:
            return result
    return None


def _stitch_transforms(raw_response: str, tool_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Replace @@Tn@@ markers in tool_def with JS definitions from ```js blocks.

    The model writes NO JavaScript inside the JSON (which small LLMs cannot
    escape reliably) — markers reference definitions in a separate fenced
    js block. Stitching happens on the parsed dict, so proper JSON escaping
    of the JS is guaranteed by construction. Returns None when a marker is
    used but never defined (caller retries / falls back).
    """
    import re as _re

    defs: Dict[str, str] = {}
    blocks = _re.findall(r'```(?:js|javascript)\s*([\s\S]*?)```', raw_response)
    for block in blocks:
        # @@Tn@@ = <expression possibly spanning lines until next marker>
        for m in _re.finditer(
            r'@@([\w-]+)@@\s*=\s*([\s\S]*?)(?=\n\s*@@[\w-]+@@|$)', block
        ):
            defs[m.group(1)] = ' '.join(m.group(2).split())

    def resolve(val: str) -> Optional[str]:
        m = _re.fullmatch(r'\s*@@([\w-]+)@@\s*', val or '')
        if not m:
            return val  # inline transform — keep as-is
        return defs.get(m.group(1))

    used_any = False
    for step in tool_def.get("steps") or []:
        cfg = step.get("config") if isinstance(step, dict) else None
        if isinstance(cfg, dict) and isinstance(cfg.get("transformCode"), str):
            resolved = resolve(cfg["transformCode"])
            if resolved is None:
                logger.warning(
                    "superglue_stitch_missing_definition: marker=%r in step=%s",
                    cfg["transformCode"][:40], step.get("id"),
                )
                return None  # marker without definition
            if resolved != cfg["transformCode"]:
                used_any = True
            cfg["transformCode"] = resolved

    ot = tool_def.get("outputTransform")
    if isinstance(ot, str) and ot.strip():
        resolved = resolve(ot)
        if resolved is None:
            logger.warning(
                "superglue_stitch_missing_definition: marker=%r in outputTransform",
                ot[:40],
            )
            return None  # marker without definition
        if resolved != ot:
            used_any = True
        tool_def["outputTransform"] = resolved

    if not defs and not used_any and '@@' in json.dumps(tool_def):
        return None  # stray marker that resolve() never saw
    return tool_def


async def _save_tool_to_superglue(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """POST a tool definition to Superglue /v1/tools (create).

    Returns the generator result dict (success/tool_id/tool_definition/error).
    """
    url, token = _get_config()
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        res = await client.post(
            f"{url}/v1/tools",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                **_session_headers(),
            },
            json=tool_def,
        )

    if res.status_code in (200, 201):
        result = res.json()
        tool_id = result.get("id") or tool_def.get("id")
        logger.info("superglue_tool_saved: tool_id=%s", tool_id)
        return {
            "success": True,
            "tool_id": tool_id,
            "tool_definition": tool_def,
            "error": None,
        }

    logger.warning(
        "superglue_rejected_tool: status=%d body=%s",
        res.status_code, res.text[:300],
    )
    return {
        "success": False,
        "error": f"Superglue rejected the generated tool: {res.status_code}",
        "tool_id": None,
        "tool_definition": tool_def,
    }


async def _generate_tool_via_superglue_llm(
    instruction: str,
    agent_name: str,
) -> Dict[str, Any]:
    """Generate a tool using SUPERGLUE'S OWN LLM (primary path).

    Direct POST to the OpenAI-compatible /sgai/v1/chat/completions with
    Superglue's sgai_ key — the queue cannot reach the LLM (verified).
    Returns the standard generator result dict with generated_by="superglue_llm".
    """
    llm_url = _get_llm_url()
    llm_key = _get_llm_key()
    model = _get_llm_model()

    system = (
        "You are a Superglue tool designer. You respond with EXACTLY two "
        "fenced blocks and nothing else: (1) a ```json block with the tool "
        "JSON, where every transform is the marker @@T1@@, @@T2@@, ... ; "
        "(2) a ```js block defining each marker as a single-expression "
        "arrow function, one per line, e.g. @@T1@@ = (sourceData) => ... "
        "Never write JavaScript inside the JSON block."
    )
    base_user = (
        f"{instruction}\n\n"
        f"Respond with ONLY the tool JSON in exactly this format:\n{_TOOL_JSON_SPEC}"
    )

    user = base_user
    # Up to 3 attempts: if Superglue's validation rejects the generated
    # tool (e.g. invented step type) or the response is unparseable, feed
    # a corrective nudge back. Still $0 — this is Superglue's own LLM.
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                llm_url,
                headers={
                    "Authorization": f"Bearer {llm_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 2600,
                    "temperature": 0.2,
                },
            )

        if res.status_code != 200:
            return {
                "success": False,
                "error": f"Superglue LLM returned {res.status_code}: {res.text[:200]}",
                "tool_id": None,
                "tool_definition": None,
            }

        content = (res.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not content:
            return {
                "success": False,
                "error": "Superglue LLM returned empty response",
                "tool_id": None,
                "tool_definition": None,
            }

        tool_def = _parse_tool_json(content)
        fail_reason = "json_parse" if not tool_def else None
        if tool_def:
            tool_def = _stitch_transforms(content, tool_def)
            if not tool_def:
                fail_reason = "transform_stitch"
        if not tool_def:
            logger.warning(
                "superglue_llm_generation_reject (%s): agent=%s len=%d head=%r tail=%r",
                fail_reason, agent_name, len(content), content[:300], content[-250:],
            )
            if attempt < 2:
                if fail_reason == "transform_stitch":
                    user = (
                        f"{base_user}\n\n"
                        f"Your JSON used transform markers (@@T1@@ etc.) but you did "
                        f"not DEFINE them. Respond again with the ```json block, then "
                        f"a ```js block that defines EVERY marker you used, one per "
                        f"line: @@T1@@ = (sourceData) => ... (single expression, "
                        f"single quotes). No other text."
                    )
                else:
                    user = (
                        f"{base_user}\n\n"
                        f"Your previous response could not be parsed as JSON. "
                        f"Respond again with the ```json block (all strings "
                        f"single-line) then the ```js block for any markers. "
                        f"No other text."
                    )
                continue
            return {
                "success": False,
                "error": "Superglue LLM response did not contain valid tool JSON",
                "tool_id": None,
                "tool_definition": None,
            }

        result = await _save_tool_to_superglue(tool_def)
        if result.get("success"):
            result["generated_by"] = "superglue_llm"  # for audit
            if attempt > 0:
                result["generated_after_retry"] = True
            logger.info(
                "superglue_llm_generated_tool: agent=%s tool_id=%s (attempt %d)",
                agent_name, result.get("tool_id"), attempt + 1,
            )
            return result

        # Validation rejection → one corrective retry with the error text
        user = (
            f"{base_user}\n\n"
            f"Your previous JSON was REJECTED by validation with this error:\n"
            f"{result.get('error', 'unknown')}\n"
            f"Fix exactly that problem and respond again with ONLY the corrected JSON."
        )

    return result


def _build_tool_instruction(
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str],
    tenant_integrations: Optional[Dict[str, Any]],
) -> str:
    """Build the natural-language instruction describing WHAT tool to build."""
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
    """Check if a previously-generated tool exists and is active.

    Returns:
        {status: "active"|"disabled"|"failed"|"unknown", tool_id, definition?}
    """
    if not is_configured():
        return {"status": "unknown", "tool_id": tool_id}

    url, token = _get_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{url}/v1/tools/{tool_id}",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
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
    """Disable a Superglue tool. Returns True on success.

    NOTE: the current stack has NO PATCH /v1/tools/{id} route (verified 404).
    DELETE /v1/tools/{id} is the supported removal (verified 200
    {"success":true}) — it permanently deletes the tool.
    """
    if not is_configured():
        return False

    url, token = _get_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.delete(
                f"{url}/v1/tools/{tool_id}",
                headers={"Authorization": f"Bearer {token}", **_session_headers()},
            )
        return res.status_code in (200, 204)
    except Exception as exc:
        logger.warning("disable_tool error: %s", str(exc)[:200])
        return False


# ════════════════════════════════════════════════════════════════════════════
# FALLBACK: Generate tool via PARWA's NVIDIA LLM (when Superglue LLM is
# unavailable or returns unusable output)
# ════════════════════════════════════════════════════════════════════════════
#
# This is a ONE-TIME cost per agent creation (not per ticket), so it doesn't
# impact the 512MB Render constraint during normal operation.
#
# Flow:
#   1. PARWA's NVIDIA LLM generates tool JSON (URL, steps, transforms)
#   2. PARWA POSTs the JSON to Superglue /v1/tools (creates the tool)
#   3. Superglue returns the tool_id
#   4. PARWA saves tool_id to AIAgentAssignment


async def _generate_tool_via_parwa_llm(
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str] = None,
    tenant_integrations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a Superglue tool using PARWA's NVIDIA LLM (fallback path).

    Cost: 1 LLM call to PARWA's NVIDIA (~5s, ~500 tokens) — one-time per agent,
    not per ticket. Acceptable for 512MB Render constraint.
    """
    try:
        from app.core.parwa_pipeline.llm_client import llm_call
    except Exception as exc:
        # Import chain pulls in the full pipeline package (langgraph etc.) —
        # degrade gracefully instead of bubbling a 500 to the API layer.
        logger.error("parwa_llm_fallback_import_failed: %s", str(exc)[:200])
        return {
            "success": False,
            "error": f"PARWA LLM fallback unavailable: {str(exc)[:150]}",
            "tool_id": None,
            "tool_definition": None,
        }

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
{_TOOL_JSON_SPEC}

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

        tool_def = _parse_tool_json(response)
        if not tool_def:
            return {
                "success": False,
                "error": "PARWA LLM response did not contain valid tool JSON",
                "tool_id": None,
                "tool_definition": None,
            }

        result = await _save_tool_to_superglue(tool_def)
        if result.get("success"):
            result["generated_by"] = "parwa_nvidia_llm"  # for audit
            logger.info(
                "parwa_llm_generated_tool: agent=%s tool_id=%s",
                agent_name, result.get("tool_id"),
            )
        return result

    except Exception as exc:
        logger.error("parwa_llm_tool_generation_failed: %s", str(exc)[:200])
        return {
            "success": False,
            "error": str(exc)[:200],
            "tool_id": None,
            "tool_definition": None,
        }
