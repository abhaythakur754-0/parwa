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
import re
from typing import Any, Dict, List, Optional

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
    trial_run_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ask Superglue to generate a multi-step tool for this AI agent.

    Args:
        agent_name: Human name of the PARWA agent (e.g. "Refund Specialist")
        agent_instructions: The system prompt PARWA's LLM uses for this agent
        agent_capabilities: What this agent handles (e.g. "refund_processing, billing_inquiry")
        sample_ticket: A real ticket text that triggered this agent (helps design the tool)
        tenant_integrations: Integrations the tenant has connected
            (e.g. {"paddle": {"api_key": "pdl_..."}})
        trial_run_inputs: OPTIONAL side-effect-safe inputs. When provided,
            the saved tool is trial-RUN with these inputs and a runtime
            failure deletes the tool and feeds the error back for a
            corrective retry (catches e.g. hallucinated table names).
            NEVER pass inputs that mutate real customer data.

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
        result = await _generate_tool_via_superglue_llm(
            instruction, agent_name, trial_run_inputs
        )
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
  - "body" MUST be a JSON-encoded STRING, NEVER a JSON object (the engine
    only templates string bodies). Example:
      "body": "{\"query\": \"SELECT * FROM t WHERE email = '<<customerEmail>>'\"}"
  - "transform" config fields: type ("transform"), transformCode
    (a single "(sourceData) => ..." expression string).
  - Step ids: lowercase snake_case (step1, step2, ...).
  - Step ORDER matters: a transform step MUST come BEFORE any request step
    that references its result (e.g. a body of
    "<<(sourceData) => sourceData.update_query.data>>" requires the
    "update_query" transform to appear EARLIER in steps).
  - JSON strings must be single-line — NEVER put raw newlines inside a
    string value.
  - Inside transformCode / outputTransform / url arrow-function strings use
    ONLY SINGLE QUOTES for JS strings (e.g. 'No posts found') — NEVER
    double quotes.

TRANSFORM RULE (critical - prevents invalid JSON):
  - If a transform step needs "transformCode", or you need
    "outputTransform", DO NOT write JavaScript inside the JSON. Set that
    value to a marker instead:
      "transformCode": "@@T1@@"   (use T1, T2, ... in order)
    @@Tn@@ markers are allowed ONLY in transformCode / outputTransform —
    NOWHERE else. PARWA resolves each marker against real JavaScript
    afterwards — you do NOT provide any js block or definitions. Your
    ENTIRE response is the single ```json block and nothing else.
  - For a COMPUTED request "body" (depends on a previous step's result)
    use this VERIFIED two-step pattern — NEVER inline JS in the body:
      1) add a transform step whose transformCode RETURNS the body JSON
         string, e.g. it ends with: JSON.stringify({query: 'UPDATE ...'})
         (use a @@Tn@@ marker there — PARWA fills the JS)
      2) the request step's body is exactly ONE reference to it:
           "body": "<<(sourceData) => sourceData.<thatStepId>.data>>"
    The ONLY other allowed body form is a static JSON string with
    <<input>> refs inside. NEVER write inline JavaScript in a body
    string (quote escaping breaks), NEVER a bare "(sourceData) => ..."
    string, NEVER a @@Tn@@ marker directly in body.

Template syntax for URLs:
  - Tool input ref: <<customerEmail>>
  - Step result ref: <<(sourceData) => 'https://api.x.com/' + sourceData.stepId.data.path>>
  - For Paddle (wraps items in data[]): sourceData.stepId.data.data[0].id
  - ALWAYS end with >> (double chevron)

Data shapes inside transforms (verified — follow exactly):
  - Step results live at sourceData.<stepId>.
  - The payload is at sourceData.<stepId>.data. For Postgres steps this is
    ALREADY the rows array (e.g. sourceData.step1.data[0].stage) — there is
    NO extra .rows wrapper. For HTTP steps it is the response payload.
  - Use defensive access (?. and || []) so an empty result cannot crash."""


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


def _extract_markers(tool_def: Dict[str, Any]) -> List[str]:
    """Collect @@Tn@@ markers from transformCode / outputTransform ONLY.

    Markers anywhere else (body, url, queryParams, ...) are banned by the
    SPEC and rejected by _validate_marker_placement — the ONLY supported
    computed-value form outside transform fields is the <<(...) => ...>>
    template ref (verified live: template ref runs, bare arrow fn breaks
    the postgres engine with 'Cannot destructure property camelCase').
    """
    markers: List[str] = []

    def scan(val: Any) -> None:
        if isinstance(val, str):
            for m in re.finditer(r'@@([\w-]+)@@', val):
                if m.group(1) not in markers:
                    markers.append(m.group(1))

    for step in tool_def.get("steps") or []:
        if not isinstance(step, dict):
            continue
        cfg = step.get("config")
        if isinstance(cfg, dict) and isinstance(cfg.get("transformCode"), str):
            scan(cfg["transformCode"])
    ot = tool_def.get("outputTransform")
    if isinstance(ot, str):
        scan(ot)
    return markers


def _validate_marker_placement(tool_def: Dict[str, Any]) -> Optional[str]:
    """Reject @@Tn@@ markers outside transformCode/outputTransform and bare
    arrow-function bodies. Returns an error string, or None when clean.

    Verified live: a body of "<<(sourceData) => '...'>>" runs; the same
    arrow WITHOUT the << >> wrapper makes the postgres plugin fail with
    "Cannot destructure property 'camelCase' of 'config_or_text'".
    """
    for step in tool_def.get("steps") or []:
        if not isinstance(step, dict):
            continue
        cfg = step.get("config")
        if not isinstance(cfg, dict):
            continue
        sid = step.get("id")
        for key, val in cfg.items():
            if isinstance(val, str) and "@@" in val and key not in ("transformCode", "outputTransform"):
                return (
                    f"step {sid}: @@Tn@@ marker in '{key}' is not allowed — "
                    f"use a <<(sourceData) => ...>> template ref instead"
                )
        body = cfg.get("body")
        if isinstance(body, str):
            b = body.strip()
            if b.startswith("(sourceData"):
                return (
                    f"step {sid}: computed body must be produced by a preceding "
                    f"transform step and referenced as "
                    f"<<(sourceData) => sourceData.<stepId>.data>> — a bare arrow "
                    f"function breaks the engine"
                )
            if "<<(" in b and not re.fullmatch(
                r'<<\(sourceData\) => sourceData\.[\w-]+\.data>>', b
            ):
                return (
                    f"step {sid}: inline JS in body breaks escaping — produce the "
                    f"body JSON string in a preceding transform step and reference "
                    f"it as <<(sourceData) => sourceData.<stepId>.data>>"
                )
        elif body is not None:
            return f"step {sid}: body must be a JSON-encoded string, never an object"
    return None


def _validate_body_refs(tool_def: Dict[str, Any]) -> Optional[str]:
    """Pre-save static check of the computed-body chain (no save quota burned).

    A request body of "<<(sourceData) => sourceData.<ref>.data>>" requires:
      1. step <ref> exists,
      2. it is a transform step,
      3. its (stitched) transformCode returns JSON.stringify({query: ...}) —
         the FULL body JSON string (verified live; a bare SQL string or a
         plain value makes the postgres plugin fail with 'Cannot
         destructure property camelCase').
    Returns an error string for the retry loop, or None when clean.
    """
    steps = tool_def.get("steps") or []
    by_id = {s.get("id"): s for s in steps if isinstance(s, dict)}
    for s in steps:
        if not isinstance(s, dict):
            continue
        cfg = s.get("config") or {}
        body = cfg.get("body") if isinstance(cfg, dict) else None
        if not isinstance(body, str):
            continue
        m = re.fullmatch(
            r'<<\(sourceData\) => sourceData\.([\w-]+)\.data>>', body.strip()
        )
        if not m:
            continue
        ref = m.group(1)
        ref_step = by_id.get(ref)
        if ref_step is None:
            return f"step {s.get('id')}: body references step '{ref}' which does not exist"
        rcfg = ref_step.get("config") or {}
        if not isinstance(rcfg, dict) or rcfg.get("type") != "transform":
            return (
                f"step {s.get('id')}: body references step '{ref}' which must be "
                f"a transform step returning JSON.stringify({{query: ...}})"
            )
        tc = rcfg.get("transformCode") or ""
        if "JSON.stringify" not in tc:
            return (
                f"step {ref}: must return JSON.stringify({{query: '...'}}) — the FULL "
                f"body JSON string — because step {s.get('id')} uses its output as "
                f"a request body"
            )
    return None


def _fix_step_order(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically reorder steps so a body-referenced transform comes
    BEFORE the request step that consumes it (verified live failure: the
    7B placed the body-producing transform AFTER its consumer — the engine
    then saw sourceData.<id> as undefined). Only body-ref edges are used:
      request step with body "<<(sourceData) => sourceData.<id>.data>>"
      depends on step <id>.
    Original order is kept for everything else (stable Kahn, lowest-index
    tie-break). Cycles → return unchanged (save will fail, retry loop).
    """
    steps = tool_def.get("steps")
    if not isinstance(steps, list) or len(steps) < 2:
        return tool_def

    deps: Dict[int, set] = {}
    for i, s in enumerate(steps):
        deps[i] = set()
        cfg = s.get("config") if isinstance(s, dict) else None
        body = cfg.get("body") if isinstance(cfg, dict) else None
        if isinstance(body, str):
            m = re.fullmatch(
                r'<<\(sourceData\) => sourceData\.([\w-]+)\.data>>', body.strip()
            )
            if m:
                ref = m.group(1)
                for j, other in enumerate(steps):
                    if isinstance(other, dict) and other.get("id") == ref:
                        deps[i].add(j)

    order, done, remaining = [], set(), set(range(len(steps)))
    while remaining:
        ready = next((i for i in sorted(remaining) if deps[i] <= done), None)
        if ready is None:
            return tool_def  # cycle / dangling ref — leave as-is
        order.append(ready)
        done.add(ready)
        remaining.discard(ready)

    if order != list(range(len(steps))):
        logger.info("superglue_step_order_fixed: %s", order)
        tool_def["steps"] = [steps[i] for i in order]
    return tool_def


def _stitch_transforms(tool_def: Dict[str, Any], defs: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Replace @@Tn@@ markers in tool_def with the supplied JS definitions.

    Definitions come from the focused marker-definition LLM call (the model
    could NOT reliably emit them alongside the JSON — verified live: 4/4
    attempts ended right after the JSON block). Stitching happens on the
    parsed dict, so proper JSON escaping of the JS is guaranteed by
    construction. Returns None when a marker is used but never defined.
    """

    def resolve(val: str) -> Optional[str]:
        m = re.fullmatch(r'\s*@@([\w-]+)@@\s*', val or '')
        if not m:
            return val  # not a bare marker — keep as-is
        return defs.get(m.group(1))

    def apply(container: Any, where: str) -> bool:
        if isinstance(container, dict):
            items = list(container.items())
        elif isinstance(container, list):
            items = list(enumerate(container))
        else:
            return True
        for key, val in items:
            if isinstance(val, str):
                if not re.search(r'@@[\w-]+@@', val):
                    continue
                resolved = resolve(val)
                if resolved is None:
                    logger.warning(
                        "superglue_stitch_missing_definition: marker=%r in %s.%s",
                        val[:40], where, key,
                    )
                    return False
                if resolved != val:
                    container[key] = resolved
            elif isinstance(val, (dict, list)):
                if not apply(val, where):
                    return False
        return True

    for step in tool_def.get("steps") or []:
        cfg = step.get("config") if isinstance(step, dict) else None
        if isinstance(cfg, dict) and not apply(cfg, str(step.get("id"))):
            return None

    ot = tool_def.get("outputTransform")
    if isinstance(ot, str) and ot.strip():
        pseudo: Dict[str, Any] = {"outputTransform": ot}
        if not apply(pseudo, "outputTransform"):
            return None
        tool_def["outputTransform"] = pseudo["outputTransform"]

    return tool_def


async def _superglue_llm_ask(system: str, user: str) -> Optional[str]:
    """One direct call to Superglue's OpenAI-compatible LLM (/sgai/v1).

    The queue CANNOT reach the LLM (verified) — generation always goes
    direct. Returns the message content, or None on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                _get_llm_url(),
                headers={
                    "Authorization": f"Bearer {_get_llm_key()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _get_llm_model(),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 2600,
                    "temperature": 0.2,
                },
            )
    except Exception as exc:
        logger.warning("superglue_llm_call_error: %s", str(exc)[:200])
        return None
    if res.status_code != 200:
        logger.warning(
            "superglue_llm_call_status: %s %s", res.status_code, res.text[:200]
        )
        return None
    return ((res.json().get("choices") or [{}])[0].get("message") or {}).get("content") or None


async def _define_markers_via_llm(
    ask_fn,
    tool_def: Dict[str, Any],
    markers: List[str],
) -> Dict[str, str]:
    """Focused second call: define each requested @@Tn@@ marker as JS.

    Small models reliably emit a plain list of one-line arrow functions when
    asked for NOTHING else — but they cannot reliably emit the JSON block
    AND a js block together (verified live: 4/4 attempts ended after the
    JSON block, js block never produced).
    """
    system = (
        "You write JavaScript arrow functions for Superglue tool transforms. "
        "Respond ONLY with one definition line per requested marker, in the "
        "exact form @@T1@@ = (sourceData) => <single expression>. Use single "
        "quotes for JS strings. No fences, no prose, no markdown."
    )
    user = (
        "Tool JSON:\n" + json.dumps(tool_def) + "\n\n"
        "Write the definition line for EACH of these markers: "
        + ", ".join(f"@@{m}@@" for m in markers)
        + "\n\nIMPORTANT: if a marker belongs to a transform step whose output is "
        "consumed by a later request step's body (referenced as "
        "sourceData.<stepId>.data), the function MUST return the FULL body JSON "
        "string, e.g. JSON.stringify({query: 'UPDATE ...'}) — not a bare SQL "
        "string or a plain value. Use EXACTLY the table/column names shown in "
        "the tool JSON's SQL strings. Use single quotes for JS strings."
    )
    content = await ask_fn(system, user)
    if not content:
        return {}
    defs: Dict[str, str] = {}
    for m in re.finditer(
        r'@@([\w-]+)@@\s*=\s*([\s\S]*?)(?=\n\s*@@[\w-]+@@|\Z)', content
    ):
        defs[m.group(1)] = ' '.join(m.group(2).split())
    return defs


async def _trial_run_tool(tool_id: str, inputs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Direct POST /v1/tools/{id}/run — post-save validation of a generated tool.

    Bypasses execute_tool()'s DB queue (bare-bones, no persistence). The
    CALLER decides whether the trial inputs are side-effect-safe (e.g. a
    test entity); generation never trial-runs unless inputs were provided.
    """
    url, token = _get_config()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{url}/v1/tools/{tool_id}/run",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    **_session_headers(),
                },
                json={"inputs": inputs or {}},
            )
    except Exception as exc:
        return {"success": False, "error": f"trial run error: {str(exc)[:200]}"}
    if res.status_code not in (200, 202):
        return {"success": False, "error": f"trial run HTTP {res.status_code}: {res.text[:200]}"}
    r = res.json()
    if r.get("status") != "success":
        errs = [
            sr.get("error") for sr in (r.get("stepResults") or [])
            if isinstance(sr, dict) and not sr.get("success")
        ]
        return {"success": False, "error": "; ".join(filter(None, errs))[:300] or f"status={r.get('status')}"}
    return {"success": True, "data": r.get("data")}


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
    trial_run_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a tool using SUPERGLUE'S OWN LLM (primary path).

    Direct POST to the OpenAI-compatible /sgai/v1/chat/completions with
    Superglue's sgai_ key — the queue cannot reach the LLM (verified).
    Returns the standard generator result dict with generated_by="superglue_llm".

    Architecture (verified live 2026-09-08 — the model ends its turn right
    after the JSON block 4/4 times, so the js block is never produced):
      call 1 → tool JSON with @@Tn@@ markers only (parses reliably)
      call 2 → focused "define these markers" ask, plain JS lines
      stitch → PARWA splices definitions into the parsed dict, then saves.
    """
    system = (
        "You are a Superglue tool designer. Respond with EXACTLY ONE fenced "
        "```json block and nothing else. Where a transform step's "
        "\"transformCode\" or the tool's \"outputTransform\" is needed, set "
        "that value to a marker @@T1@@, @@T2@@, ... — PARWA collects the "
        "JavaScript definitions separately. A computed request body must be "
        "produced by a preceding transform step and referenced as "
        "<<(sourceData) => sourceData.<stepId>.data>> — never inline JS. "
        "Never write "
        "JavaScript inside the JSON. Never put raw newlines inside JSON "
        "strings."
    )
    base_user = (
        f"{instruction}\n\n"
        f"Respond with ONLY the tool JSON in exactly this format:\n{_TOOL_JSON_SPEC}"
    )

    user = base_user
    result: Dict[str, Any] = {
        "success": False,
        "error": "generation loop exited unexpectedly",
        "tool_id": None,
        "tool_definition": None,
    }
    # Up to 3 attempts: if Superglue's validation rejects the generated
    # tool (e.g. invented step type) or the response is unusable, feed a
    # corrective nudge back. Still $0 — this is Superglue's own LLM.
    for attempt in range(3):
        content = await _superglue_llm_ask(system, user)
        if not content:
            return {
                "success": False,
                "error": "Superglue LLM unreachable or returned an empty response",
                "tool_id": None,
                "tool_definition": None,
            }

        tool_def = _parse_tool_json(content)
        fail_reason = "json_parse" if not tool_def else None
        if tool_def:
            # fail fast on banned marker placement / bare-arrow bodies
            fail_reason = _validate_marker_placement(tool_def)
            if fail_reason:
                tool_def = None
        if tool_def:
            markers = _extract_markers(tool_def)
            if markers:
                defs = await _define_markers_via_llm(_superglue_llm_ask, tool_def, markers)
                missing = [m for m in markers if m not in defs]
                if missing:
                    logger.warning(
                        "superglue_marker_defs_missing_first_pass: %s — one targeted retry",
                        missing,
                    )
                    defs.update(
                        await _define_markers_via_llm(_superglue_llm_ask, tool_def, missing)
                    )
                tool_def = _stitch_transforms(tool_def, defs)
            if tool_def is not None and "@@" in json.dumps(tool_def):
                tool_def = None  # stray marker survived somewhere
            if tool_def is not None:
                tool_def = _fix_step_order(tool_def)
            if tool_def is not None:
                ref_err = _validate_body_refs(tool_def)
                if ref_err:
                    fail_reason = ref_err
                    tool_def = None
            if tool_def is None and fail_reason is None:
                fail_reason = "transform_stitch"

        if tool_def is None:
            logger.warning(
                "superglue_llm_generation_reject (%s): agent=%s len=%d head=%r tail=%r",
                fail_reason, agent_name, len(content), content[:300], content[-250:],
            )
            if attempt < 2:
                user = (
                    f"{base_user}\n\n"
                    f"Your previous response could not be used ({fail_reason}). "
                    f"Respond again with ONLY the single ```json block (all "
                    f"strings single-line; use @@T1@@ markers for transforms; "
                    f"do NOT write JavaScript). No other text."
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
            # Optional post-save validation: trial-run with caller-provided
            # safe inputs. A runtime failure deletes the tool and feeds the
            # error back for a corrective retry (catches e.g. hallucinated
            # table names that Superglue's own validation cannot see).
            if trial_run_inputs is not None:
                trial = await _trial_run_tool(result.get("tool_id"), trial_run_inputs)
                if not trial.get("success"):
                    await disable_tool(result.get("tool_id"))
                    logger.warning(
                        "superglue_trial_run_failed: agent=%s tool_id=%s error=%s",
                        agent_name, result.get("tool_id"), trial.get("error"),
                    )
                    if attempt < 2:
                        user = (
                            f"{base_user}\n\n"
                            f"Your tool was saved but FAILED its trial run with this "
                            f"runtime error:\n{trial.get('error')}\n"
                            f"Fix the tool (exact table/column names, correct step "
                            f"wiring, defensive access) and respond again with ONLY "
                            f"the corrected JSON."
                        )
                        continue
                    return {
                        "success": False,
                        "error": f"tool trial run failed: {trial.get('error')}",
                        "tool_id": None,
                        "tool_definition": None,
                    }
                result["trial_run_data"] = trial.get("data")
            result["generated_by"] = "superglue_llm"  # for audit
            if attempt > 0:
                result["generated_after_retry"] = True
            logger.info(
                "superglue_llm_generated_tool: agent=%s tool_id=%s (attempt %d)",
                agent_name, result.get("tool_id"), attempt + 1,
            )
            return result

        # Validation rejection → corrective retry with the error text
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
        "credentials from your systems store. Use EXACTLY the table, column, and "
        "endpoint names given in the agent context — never invent, rename, or "
        "shorten them."
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

        # Same pipeline as the primary path: reject bad marker placement,
        # then resolve transform markers before saving.
        placement_error = _validate_marker_placement(tool_def)
        if placement_error:
            return {
                "success": False,
                "error": f"PARWA LLM tool invalid: {placement_error}",
                "tool_id": None,
                "tool_definition": None,
            }
        markers = _extract_markers(tool_def)
        if markers:
            async def _parwa_ask(system: str, user: str) -> Optional[str]:
                return await llm_call(f"{system}\n\n{user}", max_tokens=900, temperature=0.2)

            defs = await _define_markers_via_llm(_parwa_ask, tool_def, markers)
            tool_def = _stitch_transforms(tool_def, defs)
            if not tool_def or "@@" in json.dumps(tool_def):
                return {
                    "success": False,
                    "error": "PARWA LLM tool used transform markers that could not be resolved",
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
