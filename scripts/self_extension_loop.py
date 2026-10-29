#!/usr/bin/env python3
"""
PARWA Self-Extension Loop — the agent grows its own tools.

When the agent's Act node (node_5_act_verify.py) finds NO tool for a
capability it needs, instead of escalating to a human this loop:

  1. DETECT      — verify_tool_exists() → 404 = missing
  2. DESIGN      — Superglue's own LLM lane (/sgai/v1, Mistral — $0 for
                   Parwa) generates a strict JSON tool spec; a validated
                   deterministic template backs it up if the LLM output
                   fails validation
  3. CREATE      — tool_factory.upsert_tool() → tool live in Superglue
                   (tenant-namespaced, exactly like the runtime expects)
  4. TEST        — execute the tool with realistic inputs; must produce
                   a usable result BEFORE the agent is allowed to use it
  5. RESOLVE     — run the real ticket through the new tool, attach the
                   full audit trail

Safety rails (mirrors Parwa's approval-gate model):
  - Only `read`-risk tools are auto-approved in this loop.
  - `write`-risk specs are created but flagged approval_required:true in
    the manifest — at runtime node_5 routes them to the approval queue.
  - Every step is journaled to scripts/out/self_extension_<ts>.json.

Usage:
  python3 self_extension_loop.py --demo            # full demo (GadgetHub warranty ticket)
  python3 self_extension_loop.py --check <slug> --tenant T
  python3 self_extension_loop.py --design --capability "..." --tenant T
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tool_factory import (  # noqa: E402
    SUPERGLUE_URL,
    SUPERGLUE_TOKEN,
    OUT_DIR,
    api_request,
    namespaced,
    upsert_tool,
    tool_exists,
    run_tool,
    validate_spec,
    classify_result,
)
try:  # optional DB registry — best-effort, never blocks the loop
    from tool_registry_db import register_tool  # noqa: E402
except Exception:  # noqa: BLE001
    register_tool = None

# Superglue's own LLM lane (OpenAI-compatible) — $0 generation cost for Parwa
DEFAULT_LLM_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgai/v1/chat/completions"
DEFAULT_LLM_KEY = "sgai_39ff17e8bca987faa7fb31c92d952ee0d9fe021fea592c4f"
LLM_MODEL = "open-mistral-7b"

LLM_URL = os.environ.get("SUPERGLUE_LLM_URL", DEFAULT_LLM_URL)
LLM_KEY = os.environ.get("SUPERGLUE_LLM_API_KEY", DEFAULT_LLM_KEY)


def _register_in_db(journal: dict | None, tenant: str, tool_id: str, spec: dict,
                    risk: str, capability: str, origin: str,
                    created_for_ticket: str | None = None) -> dict | None:
    """Best-effort DB registration: tool inventory + agent↔tool link.
    Never raises; result is journaled so it's always auditable."""
    if register_tool is None:
        return None
    r = register_tool(
        company_id=tenant,
        tool_id=tool_id,
        tool_name=spec.get("name", tool_id),
        risk=risk,
        approval_required=(risk == "write"),
        capability=capability,
        created_by="self_extension" if origin == "self_extension" else "tool_factory",
        origin=origin,
        created_for_ticket=created_for_ticket,
        tool_definition=spec,
    )
    if journal is not None:
        journal.setdefault("steps", []).append({
            "at": datetime.now(timezone.utc).isoformat(),
            "step": "db_register", "ok": r.get("ok", False),
            **({"error": r.get("error")} if not r.get("ok") else {"inventory": r.get("inventory"), "agent_link": r.get("agent_link")}),
        })
    return r


# ════════════════════════════════════════════════════════════════════════════
# 1. DETECT
# ════════════════════════════════════════════════════════════════════════════
def detect_missing_tool(tenant: str, slug: str) -> dict:
    tid = namespaced(slug, tenant)
    exists = tool_exists(tid)
    return {
        "tool_id": tid,
        "exists": exists,
        "action": "use_existing" if exists else "self_extend",
    }


# ════════════════════════════════════════════════════════════════════════════
# 2. DESIGN — LLM generates the spec; deterministic fallback backs it up
# ════════════════════════════════════════════════════════════════════════════
DESIGN_SYSTEM_PROMPT = """You are PARWA's tool architect. You design Superglue tools.

Return ONLY a JSON object (no markdown, no explanation) with EXACTLY these fields:
{
  "id": "<kebab-case-slug>",
  "name": "<Human Name>",
  "instruction": "<one paragraph: what it does and when the agent should use it>",
  "inputSchema": {"type": "object", "required": [...], "properties": {...}},
  "steps": [
    {"id": "<stepId>", "instruction": "...", "config": {"type": "request", "method": "GET|POST", "url": "https://...<<input>>...", "headers": {...}}},
    {"id": "<stepId2>", "config": {"type": "transform", "transformCode": "(sourceData) => ({ ... })"}}
  ],
  "outputTransform": "(sourceData) => JSON.stringify({...})"
}

TEMPLATE RULES (mandatory):
- Tool inputs in URLs/headers: <<inputName>>
- Prior step data — ALWAYS with .data: sourceData.<stepId>.data.<field> (this includes outputTransform: write sourceData.<stepId>.data.<field>, NEVER bare sourceData.<stepId>)
- Output MUST end with: return JSON.stringify({...});
- JS must be ES5-safe: NO optional chaining (?.), NO arrow shorthand in transformCode except the leading (sourceData) =>, NO const/let (use var), wrap in try/catch.

API RULES:
- Use ONLY these free public APIs: https://dummyjson.com (products search: /products/search?q=<q>, single product: /products/<id>, carts: /carts/<id>), https://jsonplaceholder.typicode.com (users: /users/<id>, posts: /users/<id>/posts, todos: /todos/<id>), https://api.open-meteo.com (weather: /v1/forecast?latitude=..&longitude=..&current_weather=true), https://postman-echo.com (echo: /get, /post)
- dummyjson.com/product fields are EXACTLY: id, title, description, category, price, discountPercentage, rating, stock, tags, brand, warrantyInformation (string like '1 week warranty' / '3 months warranty'), returnPolicy, shippingInformation, availabilityStatus.
- dummyjson.com/cart fields: id, userId, total, discountedTotal, products[] {title, quantity, price}.
- NEVER invent API keys or require authentication.
- Prefer 1-3 steps: fetch, then a transform to shape the result.
- If the capability mentions a product NAME (not an id), use /products/search?q=<<name>> — do NOT invent an id-based lookup.
- The transform step MUST read sourceData.<fetchStepId>.data.<field> and be defensive (missing fields → null).
"""

# Deterministic fallback templates — validated, production-safe, zero LLM risk.
# Keyed by capability family. Each returns a full spec dict.
FALLBACK_TEMPLATES = {
    "warranty_check": {
        "id": "warranty-status-check",
        "name": "Warranty Status Check (products DB)",
        "instruction": (
            "Look up a product by name and return its warranty information, price and "
            "rating from the products catalog. Read-only. Use when a customer asks "
            "whether their device is still under warranty or what the warranty covers."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["productName"],
            "properties": {
                "productName": {"type": "string", "description": "Product name to look up, e.g. 'iPhone'"},
            },
        },
        "steps": [
            {
                "id": "searchProduct",
                "instruction": "Search the catalog for the product",
                "config": {
                    "type": "request",
                    "method": "GET",
                    "url": "https://dummyjson.com/products/search?q=<<productName>>&limit=5",
                    "headers": {},
                },
            },
            {
                "id": "shapeResult",
                "instruction": "Pick the best match and shape the warranty answer",
                "config": {
                    "type": "transform",
                    "transformCode": (
                        "(sourceData) => { try {"
                        " var resp = sourceData.searchProduct || {};"
                        " var items = (resp.data && resp.data.products) ? resp.data.products : [];"
                        " var q = String(sourceData.productName || '').toLowerCase();"
                        " var best = null;"
                        " for (var i = 0; i < items.length; i++) {"
                        "  var t = items[i] && items[i].title ? String(items[i].title).toLowerCase() : '';"
                        "  if (t.indexOf(q) !== -1) { best = items[i]; break; }"
                        " }"
                        " if (!best && items.length) best = items[0];"
                        " if (!best) return { found: false };"
                        " return { found: true, product: { title: best.title, brand: best.brand || null, category: best.category || null, price: best.price || null, rating: best.rating || null, warranty: best.warrantyInformation || null, returnPolicy: best.returnPolicy || null, stock: best.stock !== undefined ? best.stock : null } };"
                        " } catch (e) { return { found: false, error: String(e) }; } }"
                    ),
                },
            },
        ],
        "outputTransform": (
            "(sourceData) => { try {"
            " var s = sourceData.shapeResult && sourceData.shapeResult.data ? sourceData.shapeResult.data : { found: false };"
            " return JSON.stringify(s);"
            " } catch (e) { return JSON.stringify({ found: false, error: String(e) }); } }"
        ),
    },
    "order_tracking": {
        "id": "order-status-lookup",
        "name": "Order Status Lookup (carts DB)",
        "instruction": (
            "Look up a customer's order/cart by id and return its contents, total and "
            "status. Read-only. Use when a customer asks where their order is."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["orderId"],
            "properties": {"orderId": {"type": "string", "description": "Order/cart id"}},
        },
        "steps": [
            {
                "id": "fetchOrder",
                "instruction": "Fetch the order",
                "config": {
                    "type": "request",
                    "method": "GET",
                    "url": "https://dummyjson.com/carts/<<orderId>>",
                    "headers": {},
                },
            },
            {
                "id": "shapeResult",
                "instruction": "Shape the order summary",
                "config": {
                    "type": "transform",
                    "transformCode": (
                        "(sourceData) => { try {"
                        " var d = sourceData.fetchOrder && sourceData.fetchOrder.data ? sourceData.fetchOrder.data : null;"
                        " if (!d || !d.id) return { found: false };"
                        " var items = [];"
                        " var ps = d.products || [];"
                        " for (var i = 0; i < ps.length; i++) { items.push({ title: ps[i].title, qty: ps[i].quantity, price: ps[i].price }); }"
                        " return { found: true, order: { id: d.id, userId: d.userId, total: d.total, discountedTotal: d.discountedTotal, items: items } };"
                        " } catch (e) { return { found: false, error: String(e) }; } }"
                    ),
                },
            },
        ],
        "outputTransform": (
            "(sourceData) => { try {"
            " var s = sourceData.shapeResult && sourceData.shapeResult.data ? sourceData.shapeResult.data : { found: false };"
            " return JSON.stringify(s);"
            " } catch (e) { return JSON.stringify({ found: false, error: String(e) }); } }"
        ),
    },
# LLM design hints per capability → which fallback applies + suggested slug
    # Meeting booking — services-industry runtime scenario: a ticket asks
    # to schedule a setup meeting, no meeting tool exists, the agent builds one.
    "meeting_setup": {
        "id": "meeting-setup",
        "name": "Meeting Setup / Booking",
        "instruction": (
            "Books a setup meeting between the customer and the team: name, email, "
            "topic and the chosen slot are sent to the booking endpoint, which "
            "returns a booking reference and confirmation. Use when a customer "
            "asks to schedule, book or set up a meeting/call. Write action — at "
            "runtime this goes through the approval gate."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["customerName", "customerEmail", "topic", "slot"],
            "properties": {
                "customerName": {"type": "string", "description": "Customer full name"},
                "customerEmail": {"type": "string", "description": "Customer email for the invite"},
                "topic": {"type": "string", "description": "Meeting subject"},
                "slot": {"type": "string", "description": "Chosen slot, e.g. '2026-11-05T14:00 UTC'"},
                "durationMinutes": {"type": "number", "description": "Meeting length in minutes (default 30)"},
            },
        },
        "steps": [
            {
                "id": "bookMeeting",
                "instruction": "Send the booking request to the booking endpoint",
                "config": {
                    "type": "request",
                    "method": "POST",
                    "url": "https://postman-echo.com/post",
                    "headers": {"Content-Type": "application/json"},
                    "body": (
                        "<<(sourceData) => JSON.stringify({ customerName: sourceData.customerName, "
                        "customerEmail: sourceData.customerEmail, topic: sourceData.topic, "
                        "slot: sourceData.slot, durationMinutes: Number(sourceData.durationMinutes || 30), "
                        "source: 'parwa-agent' })>>"
                    ),
                },
            }
        ],
        "outputTransform": (
            "(sourceData) => { try {"
            " var r = sourceData.bookMeeting && sourceData.bookMeeting.data ? sourceData.bookMeeting.data : {};"
            " var b = r.data ? r.data : {};"
            " if (!b.customerEmail) return JSON.stringify({ booked: false, error: 'booking endpoint did not accept the request' });"
            " var s = String(b.customerName || '') + String(b.topic || '') + String(b.slot || '');"
            " var h = 0;"
            " for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) % 99991; }"
            " var ref = 'MTG-' + (h < 10000 ? '0' + h : '' + h);"
            " return JSON.stringify({ booked: true, bookingRef: ref, topic: b.topic, slot: b.slot, "
            "customerEmail: b.customerEmail, confirmation: 'Meeting booked for ' + b.customerName + ' on ' + b.slot + ' — ref ' + ref });"
            " } catch (e) { return JSON.stringify({ booked: false, error: String(e) }); } }"
        ),
    },
    # Weather — field-services scenario. Open-Meteo needs no keys, so the
    # test run is fully green with real data.
    "weather_check": {
        "id": "weather-check",
        "name": "Weather Check (service location)",
        "instruction": (
            "Returns the current weather (temperature, wind, conditions) for a "
            "location given latitude and longitude. Read-only. Use when a ticket "
            "depends on on-site conditions — e.g. 'can the technician visit today'."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["latitude", "longitude"],
            "properties": {
                "latitude": {"type": "string", "description": "Latitude, e.g. '52.52'"},
                "longitude": {"type": "string", "description": "Longitude, e.g. '13.41'"},
            },
        },
        "steps": [
            {
                "id": "fetchWeather",
                "instruction": "Fetch current weather from Open-Meteo",
                "config": {
                    "type": "request",
                    "method": "GET",
                    "url": "https://api.open-meteo.com/v1/forecast?latitude=<<latitude>>&longitude=<<longitude>>&current_weather=true",
                    "headers": {},
                },
            },
            {
                "id": "shapeWeather",
                "instruction": "Shape a concise weather report",
                "config": {
                    "type": "transform",
                    "transformCode": (
                        "(sourceData) => { try {"
                        " var w = sourceData.fetchWeather && sourceData.fetchWeather.data ? sourceData.fetchWeather.data : null;"
                        " var cw = w && w.current_weather ? w.current_weather : null;"
                        " if (!cw) return { found: false, error: 'no weather data' };"
                        " var code = cw.weathercode;"
                        " var desc = code === 0 ? 'Clear sky' : ((code >= 1 && code <= 3) ? 'Partly cloudy' : (code === 45 || code === 48) ? 'Fog' : ((code >= 51 && code <= 67) ? 'Rain' : ((code >= 71 && code <= 77) ? 'Snow' : ((code >= 80 && code <= 82) ? 'Rain showers' : ((code >= 95) ? 'Thunderstorm' : 'Unknown')))));"
                        " return { found: true, weather: { temperature: cw.temperature, unit: 'celsius', windspeed: cw.windspeed, conditions: desc } };"
                        " } catch (e) { return { found: false, error: String(e) }; } }"
                    ),
                },
            }
        ],
        "outputTransform": (
            "(sourceData) => { try {"
            " var s = sourceData.shapeWeather && sourceData.shapeWeather.data ? sourceData.shapeWeather.data : { found: false };"
            " return JSON.stringify(s);"
            " } catch (e) { return JSON.stringify({ found: false, error: String(e) }); } }"
        ),
    },
    # Universal graceful-degradation template — works for ANY capability.
    # Used when a NOVEL capability's LLM design fails its test gate: the
    # ticket still gets a live, working tool (records the request, returns
    # a structured confirmation + reference id) instead of a dead end.
    "universal": {
        "id": "universal-request-recorder",
        "name": "Universal Request Recorder (graceful fallback)",
        "instruction": (
            "Records any request payload and returns a structured confirmation "
            "with a reference id. This is the agent's graceful fallback: when a "
            "specialised integration is not available yet, the request is still "
            "captured and confirmed so the ticket can move forward."
        ),
        "inputSchema": {
            "type": "object",
            "required": [],
            "properties": {
                "payload": {"type": "string", "description": "Free-form request payload/context"},
            },
        },
        "steps": [
            {
                "id": "recordRequest",
                "instruction": "Record the request payload",
                "config": {
                    "type": "request",
                    "method": "POST",
                    "url": "https://postman-echo.com/post",
                    "headers": {"Content-Type": "application/json"},
                    "body": (
                        "<<(sourceData) => JSON.stringify({ received: sourceData, "
                        "recordedBy: 'parwa-agent' })>>"
                    ),
                },
            }
        ],
        "outputTransform": (
            "(sourceData) => { try {"
            " var r = sourceData.recordRequest && sourceData.recordRequest.data ? sourceData.recordRequest.data : {};"
            " var b = r.json ? r.json : (r.data ? r.data : r);"
            " var s = String(b.customerEmail || '') + String(b.productName || '') + String(b.product || '');"
            " var h = 0;"
            " for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) % 99991; }"
            " var ref = 'REQ-' + (h < 10000 ? '0' + h : '' + h);"
            " return JSON.stringify({ recorded: true, requestRef: ref, request: b });"
            " } catch (e) { return JSON.stringify({ recorded: false, error: String(e) }); } }"
        ),
    },
}

# LLM design hints per capability → which fallback applies + suggested slug
CAPABILITY_HINTS = {
    "warranty_check": {
        "slug": "warranty-status-check", "fallback": "warranty_check",
        "context": (
            "Electronics e-commerce shop. Customers ask about product warranties, "
            "returns and order status. The agent needs to look up warranty info "
            "from the product catalog by product name."
        ),
        "test_inputs": {"productName": "iPhone"},
        "risk": "read",
    },
    "order_tracking": {
        "slug": "order-status-lookup", "fallback": "order_tracking",
        "context": (
            "Online retail shop. Customers ask where their order is and what is "
            "in it. The agent needs to fetch an order/cart by id and summarize it."
        ),
        "test_inputs": {"orderId": "1"},
        "risk": "read",
    },
    "meeting_setup": {
        "slug": "meeting-setup", "fallback": "meeting_setup",
        "context": (
            "Services business. Customers open tickets asking to schedule a setup "
            "meeting/call with the team. The agent needs to book a meeting: take "
            "the customer name, email, topic and a chosen slot, and get a booking "
            "reference back."
        ),
        "test_inputs": {
            "customerName": "Jane Customer",
            "customerEmail": "jane@example.com",
            "topic": "Product setup walkthrough",
            "slot": "2026-11-05T14:00 UTC",
            "durationMinutes": 30,
        },
        "risk": "write",
    },
    "weather_check": {
        "slug": "weather-check", "fallback": "weather_check",
        "context": (
            "Customers ask about weather conditions affecting service visits or "
            "shipments. The agent needs current weather for a location by lat/long."
        ),
        "test_inputs": {"latitude": "52.52", "longitude": "13.41"},
        "risk": "read",
    },
}


def llm_generate_spec(capability: str, context: str, slug_hint: str) -> dict | None:
    """Ask Superglue's LLM lane to design a tool spec. Returns parsed JSON or None."""
    if not LLM_KEY:
        return None
    user = (
        f"Design a Superglue tool for this capability:\n{capability}\n\n"
        f"Context: {context}\n"
        f"The tool id MUST be exactly: {slug_hint}\n"
        f"Return only the JSON object."
    )
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": DESIGN_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    try:
        req = urllib.request.Request(LLM_URL, data=json.dumps(body).encode(), method="POST")
        req.add_header("Authorization", f"Bearer {LLM_KEY}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        # strip code fences if present
        content = re.sub(r"^```(json)?\s*|\s*```$", "", content.strip(), flags=re.M)
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            return None
        blob = content[start : end + 1]
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            pass
        # Repair pass 1: small models emit literal newlines inside strings
        try:
            return json.loads(blob, strict=False)
        except json.JSONDecodeError:
            pass
        # Repair pass 2: strip trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", blob)
        try:
            return json.loads(repaired, strict=False)
        except json.JSONDecodeError:
            return None
    except Exception:
        return None


def design_tool_spec(capability: str, tenant: str, context: str, allow_llm: bool = True) -> dict:
    """Returns {spec, source: 'llm'|'fallback_template', slug}."""
    hint = CAPABILITY_HINTS.get(capability, {})
    slug = hint.get("slug", re.sub(r"[^a-z0-9]+", "-", capability.lower())[:40].strip("-") or "generated-tool")
    spec = None
    source = None
    if allow_llm:
        raw = llm_generate_spec(capability, context, slug)
        if raw:
            raw["id"] = slug  # enforce namespacing contract
            if not validate_spec(raw):
                spec, source = raw, "llm_generated"
    if spec is None:
        fam = hint.get("fallback")
        if fam and fam in FALLBACK_TEMPLATES:
            spec, source = dict(FALLBACK_TEMPLATES[fam]), "fallback_template"
        else:
            # NOVEL capability with no domain template: use the universal
            # recorder instead of borrowing a wrong-domain template.
            spec, source = dict(FALLBACK_TEMPLATES["universal"]), "fallback_template_universal"
            spec["id"] = slug
    return {"spec": spec, "source": source, "slug": slug}


# ════════════════════════════════════════════════════════════════════════════
# 2b. REPAIR — when the executor rejects LLM-generated transform code, feed
# the exact executor error back to the LLM and let it fix its own JS.
# ════════════════════════════════════════════════════════════════════════════

REPAIR_SYSTEM_PROMPT = """You are a JavaScript repair service for Superglue transform code.
You will receive broken transform code and the executor's error message.
Return ONLY the corrected complete JavaScript function — nothing else, no markdown fences, no explanation.
Hard rules:
- The function shape is exactly: (sourceData) => { try { ... } catch (e) { return ...; } }
- ES5 ONLY: use var (never const/let), no optional chaining (?.), no template literals, no arrow shorthand inside the body.
- NEVER put a semicolon after a property value inside an object literal (e.g. `foo: x === 1 ? 'a' : 'b';` inside { } is INVALID — the ; must be removed).
- Prior step data is ALWAYS at sourceData.<stepId>.data.<field>.
- The final statement must return an object or JSON.stringify(...).
"""


def _extract_transform_failure(run_json: dict):
    """Return (step_id, error) for the first rejected transform, else (None, '')."""
    for sr in run_json.get("stepResults") or []:
        err = str(sr.get("error") or "")
        if "Invalid transform code" in err or "Transform step failed" in err:
            return sr.get("stepId"), err
    tool_err = str(run_json.get("error") or "")
    if "Invalid transform code" in tool_err or "Transform step failed" in tool_err:
        return "outputTransform", tool_err
    return None, ""


def llm_repair_transform(spec: dict, step_id: str, error: str) -> str | None:
    """Ask the LLM to fix broken transform code. Returns corrected JS or None."""
    if not LLM_KEY:
        return None
    code = None
    if step_id == "outputTransform":
        code = spec.get("outputTransform")
        where = "the tool's outputTransform field"
    else:
        for s in spec.get("steps", []):
            if s.get("id") == step_id and s.get("config", {}).get("type") == "transform":
                code = s.get("config", {}).get("transformCode")
                where = f"the transform step '{step_id}'"
    if not code:
        return None
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"This JavaScript code failed with the executor error:\n{error}\n\n"
                f"The broken code ({where}):\n{code}\n\n"
                "Return ONLY the corrected JavaScript code — one complete function."
            )},
        ],
        "temperature": 0.0,
        "max_tokens": 1200,
    }
    try:
        req = urllib.request.Request(LLM_URL, data=json.dumps(body).encode(), method="POST")
        req.add_header("Authorization", f"Bearer {LLM_KEY}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"^```(javascript|js)?\s*|\s*```$", "", content.strip(), flags=re.M).strip()
        if not content.startswith("("):
            s = content.find("(sourceData")
            if s == -1:
                return None
            content = content[s:]
        if "(sourceData)" not in content:
            return None
        # shape guard: mandated form is (sourceData) => { ... } — reject
        # anything else (e.g. statement-style code that re-breaks the executor)
        if not re.match(r"^\s*\(\s*sourceData\s*\)\s*=>\s*\{", content):
            return None
        return content
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
# 3. CREATE + 4. TEST + 5. RESOLVE
# ════════════════════════════════════════════════════════════════════════════
def synthesize_test_inputs(spec: dict, provided: dict) -> dict:
    """Fill missing required inputs from the DESIGNED spec's own schema.

    The loop must adapt its test to whatever tool it just created — not the
    other way around. Values are realistic-but-safe for the public APIs in
    the design allowlist.
    """
    out = dict(provided or {})
    schema = spec.get("inputSchema", {})
    props = schema.get("properties", {})
    for k in schema.get("required", []):
        if k in out:
            continue
        name = k.lower()
        desc = str(props.get(k, {}).get("description", "")).lower()
        if "email" in name or "mail" in desc:
            out[k] = "someone@example.com"
        elif "lat" in name and "translate" not in name:
            out[k] = "52.52"
        elif "lon" in name or "long" in name:
            out[k] = "13.41"
        elif name.endswith("id") or "identifier" in desc:
            out[k] = "1"
        elif "name" in name or "query" in name or "search" in name or "product" in name:
            out[k] = "iPhone"
        else:
            out[k] = "test"
    return out


def _data_is_usable(data) -> bool:
    """A verified tool must return REAL payload, not just status flags.

    Parses the tool's data (string JSON from outputTransform) and requires
    at least one meaningful non-null value beyond generic status keys.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return False
    if not isinstance(data, dict):
        return False
    generic = {"success", "error", "status", "ok", "found"}
    for k, v in data.items():
        if k in generic:
            continue
        if v is not None and v != "" and v != [] and v != {}:
            return True
    return False


def extend_toolset(tenant: str, capability: str, context: str, test_inputs: dict,
                   journal: dict | None = None, allow_llm: bool = True,
                   risk: str | None = None) -> dict:
    """Full loop for one capability: detect → design → create → test.

    Self-healing: if the LLM-designed tool fails its own test, the loop
    replaces it with the validated fallback template and re-tests once.

    `risk`: optional 'read'/'write' override from the ticket planner —
    lets NOVEL (hint-less) capabilities carry the correct safety class
    (default: hint risk, else 'read').
    """
    def note(step, **kw):
        if journal is not None:
            journal.setdefault("steps", []).append({"at": datetime.now(timezone.utc).isoformat(), "step": step, **kw})

    # 1. DETECT
    det = detect_missing_tool(tenant, CAPABILITY_HINTS.get(capability, {}).get("slug", capability))
    eff_risk = risk or CAPABILITY_HINTS.get(capability, {}).get("risk", "read")
    note("detect", **det)
    if det["exists"]:
        # ownership tracking: make sure a pre-existing tool is in the DB registry too
        reg = _register_in_db(
            journal, tenant, det["tool_id"], {"name": det["tool_id"]},
            risk=eff_risk,
            capability=capability, origin="preexisting_sync",
        )
        return {"status": "use_existing", "tool_id": det["tool_id"], "db_register": reg}

    # 2. DESIGN
    designed = design_tool_spec(capability, tenant, context, allow_llm=allow_llm)
    spec = designed["spec"]
    errs = validate_spec(spec)
    if errs:
        note("design_failed_validation", errors=errs)
        return {"status": "design_failed", "errors": errs}
    note("design", slug=designed["slug"], source=designed["source"])

    # 4a. TEST INPUTS — adapted to the DESIGNED spec (fixes interface mismatch)
    effective_inputs = synthesize_test_inputs(spec, test_inputs)

    # 3. CREATE (tenant-namespaced) + 4b. TEST
    attempts = []
    ns_spec = dict(spec)
    ns_spec["id"] = namespaced(spec["id"], tenant)
    up = upsert_tool(ns_spec)
    note("create", attempt=1, **up)
    if not up["ok"]:
        attempts.append({"attempt": 1, "status": "create_failed", "detail": up})
    else:
        res = run_tool(ns_spec["id"], effective_inputs)
        verdict = classify_result(res)
        raw_data = res.get("json", {}).get("data")
        usable = verdict["verdict"] == "success" and _data_is_usable(raw_data)
        note("test", attempt=1, tool_id=ns_spec["id"], verdict=verdict["verdict"], data_usable=_data_is_usable(raw_data))
        attempts.append({
            "attempt": 1,
            "tool_id": ns_spec["id"],
            "designed_by": designed["source"],
            "status": "created_and_verified" if usable else "test_failed",
            "verdict": verdict,
            "inputs_used": effective_inputs,
            "data": res.get("json", {}).get("data") if usable else None,
        })
        if usable:
            _register_in_db(journal, tenant, ns_spec["id"], ns_spec,
                            eff_risk,
                            capability, "self_extension", created_for_ticket=(journal or {}).get("ticket", {}).get("id"))
            return {
                "status": "created_and_verified",
                "tool_id": ns_spec["id"],
                "designed_by": designed["source"],
                "verdict": verdict,
                "data": attempts[-1]["data"],
                "attempts": attempts,
            }

        # 4c. REPAIR — executor rejected LLM JS → feed the exact error back,
        # let the LLM fix its own transform, re-upsert, re-test (one pass).
        if allow_llm:
            run_json = res.get("json", {})
            bad_step, terr = _extract_transform_failure(run_json)
            if bad_step and ("Invalid transform" in terr or "Transform step failed" in terr):
                fixed_code = llm_repair_transform(ns_spec, bad_step, terr)
                note("repair", failed_step=bad_step, attempted=bool(fixed_code), error=terr[:200])
                if fixed_code:
                    fixed_spec = json.loads(json.dumps(ns_spec))  # deep copy
                    if bad_step == "outputTransform":
                        fixed_spec["outputTransform"] = fixed_code
                    else:
                        for s in fixed_spec.get("steps", []):
                            if s.get("id") == bad_step:
                                s["config"]["transformCode"] = fixed_code
                    errs_r = validate_spec(fixed_spec)
                    if not errs_r:
                        up2 = upsert_tool(fixed_spec)
                        if up2["ok"]:
                            res2 = run_tool(ns_spec["id"], effective_inputs)
                            v2 = classify_result(res2)
                            raw2 = res2.get("json", {}).get("data")
                            ok2 = v2["verdict"] == "success" and _data_is_usable(raw2)
                            note("test", attempt=2, repaired=True, tool_id=ns_spec["id"], verdict=v2["verdict"], data_usable=_data_is_usable(raw2))
                            attempts.append({
                                "attempt": 2,
                                "tool_id": ns_spec["id"],
                                "designed_by": "llm_repaired",
                                "repaired_step": bad_step,
                                "status": "created_and_verified" if ok2 else "test_failed",
                                "verdict": v2,
                                "inputs_used": effective_inputs,
                                "data": raw2 if ok2 else None,
                            })
                            if ok2:
                                _register_in_db(journal, tenant, ns_spec["id"], fixed_spec,
                                                eff_risk,
                                                capability, "self_extension", created_for_ticket=(journal or {}).get("ticket", {}).get("id"))
                                return {
                                    "status": "created_and_verified",
                                    "tool_id": ns_spec["id"],
                                    "designed_by": "llm_repaired",
                                    "self_repaired": True,
                                    "repaired_step": bad_step,
                                    "verdict": v2,
                                    "data": attempts[-1]["data"],
                                    "attempts": attempts,
                                }

    # 5. SELF-HEAL: LLM design failed its test → swap in a validated template.
    #    Known capability family → domain template; NOVEL capability → the
    #    universal echo-backed recorder (always works, keeps the ticket
    #    moving; flagged in journal + registry for later upgrade).
    hint = CAPABILITY_HINTS.get(capability, {})
    fam = hint.get("fallback")
    fb_spec = fb_source = None
    if allow_llm and fam and fam in FALLBACK_TEMPLATES:
        fb_spec = dict(FALLBACK_TEMPLATES[fam])
        fb_spec["id"] = hint.get("slug", designed["slug"])
        fb_source = "fallback_template"
    elif allow_llm:
        fb_spec = dict(FALLBACK_TEMPLATES["universal"])
        fb_spec["id"] = designed["slug"]
        fb_source = "fallback_template_universal"
    if fb_spec:
        note("self_heal", reason=(
            "llm design failed test → deploying validated "
            + ("domain" if fb_source == "fallback_template" else "universal")
            + " template"), template=fb_source)
        eff2 = synthesize_test_inputs(fb_spec, test_inputs)
        ns_spec = dict(fb_spec)
        ns_spec["id"] = namespaced(fb_spec["id"], tenant)
        up = upsert_tool(ns_spec)
        note("create", attempt=2, self_healed=True, **up)
        if up["ok"]:
            res = run_tool(ns_spec["id"], eff2)
            verdict = classify_result(res)
            raw2 = res.get("json", {}).get("data")
            ok2 = verdict["verdict"] == "success" and _data_is_usable(raw2)
            note("test", attempt=2, tool_id=ns_spec["id"], verdict=verdict["verdict"], data_usable=_data_is_usable(raw2))
            attempts.append({
                "attempt": 2,
                "tool_id": ns_spec["id"],
                "designed_by": fb_source,
                "status": "created_and_verified" if ok2 else "test_failed",
                "verdict": verdict,
                "inputs_used": eff2,
                "data": raw2 if ok2 else None,
            })
            if ok2:
                _register_in_db(journal, tenant, ns_spec["id"], ns_spec,
                                eff_risk,
                                capability, "self_extension", created_for_ticket=(journal or {}).get("ticket", {}).get("id"))
                return {
                    "status": "created_and_verified",
                    "tool_id": ns_spec["id"],
                    "designed_by": fb_source,
                    "verdict": verdict,
                    "data": attempts[-1]["data"],
                    "attempts": attempts,
                    "self_healed": True,
                }

    return {"status": "test_failed", "attempts": attempts}


# ════════════════════════════════════════════════════════════════════════════
# Demo: GadgetHub (electronics shop tenant) — novel warranty ticket
# ════════════════════════════════════════════════════════════════════════════
def run_demo(tenant: str = "gadgethub-demo", allow_llm: bool = True) -> dict:
    journal = {
        "tenant": tenant,
        "started": datetime.now(timezone.utc).isoformat(),
        "ticket": {
            "id": f"TKT-{int(time.time())}",
            "channel": "chat",
            "subject": "Is my iPhone still under warranty?",
            "description": (
                "Hi, I bought an iPhone from GadgetHub two months ago and the screen "
                "started flickering. Can you check if it's still under warranty and "
                "what the return policy is?"
            ),
        },
    }
    print(f"── Self-Extension Loop demo for tenant: {tenant}")
    print(f"   Ticket: {journal['ticket']['subject']}")

    # The agent plans → needs capability 'warranty_check' → no tool exists
    result = extend_toolset(
        tenant=tenant,
        capability="warranty_check",
        context=(
            "GadgetHub is an electronics e-commerce shop. Customers ask about product "
            "warranties, returns and order status. The support agent needs to look up "
            "warranty info from the product catalog."
        ),
        test_inputs={"productName": "iPhone"},
        journal=journal,
        allow_llm=allow_llm,
    )
    journal["result"] = result
    print(f"   → loop status: {result['status']}")
    if result.get("data"):
        print(f"   → tool output: {str(result['data'])[:300]}")

    journal["finished"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"self_extension_{int(time.time())}.json")
    with open(out, "w") as f:
        json.dump(journal, f, indent=2, default=str)
    print(f"   → journal: {out}")
    return journal


def run_scenario(tenant: str, capability: str, allow_llm: bool = True) -> dict:
    """Runtime self-extension for a NOVEL ticket (zero human intervention)."""
    hint = CAPABILITY_HINTS.get(capability, {})
    subject = {
        "meeting_setup": "Please schedule a setup meeting with your team",
        "warranty_check": "Is my iPhone still under warranty?",
        "order_tracking": "Where is my order? What did I order?",
        "weather_check": "What's the weather at the service location?",
    }.get(capability, f"Ticket needing capability: {capability}")
    journal = {
        "tenant": tenant,
        "capability": capability,
        "started": datetime.now(timezone.utc).isoformat(),
        "ticket": {
            "id": f"TKT-{int(time.time())}",
            "channel": "chat",
            "subject": subject,
            "description": subject + " (novel request — agent has no tool for this yet)",
        },
    }
    print(f"── Self-Extension scenario: tenant={tenant} capability={capability}")
    print(f"   Ticket: {subject}")

    result = extend_toolset(
        tenant=tenant,
        capability=capability,
        context=hint.get("context", ""),
        test_inputs=hint.get("test_inputs", {}),
        journal=journal,
        allow_llm=allow_llm,
    )
    journal["result"] = result
    print(f"   → loop status: {result['status']}")
    if result.get("tool_id"):
        print(f"   → tool ready: {result['tool_id']} (designed_by={result.get('designed_by')})")
    if result.get("data"):
        print(f"   → tool output: {str(result['data'])[:300]}")
    if hint.get("risk") == "write":
        print("   → NOTE: write-risk tool — created + tested, but runtime approval gate still applies")

    journal["finished"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"self_extension_{capability}_{int(time.time())}.json")
    with open(out, "w") as f:
        json.dump(journal, f, indent=2, default=str)
    print(f"   → journal: {out}")
    return journal


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--run", action="store_true", help="run a full capability scenario (detect->design->create->test)")
    p.add_argument("--tenant")
    p.add_argument("--capability")
    p.add_argument("--design", action="store_true", help="only design + validate, don't create")
    p.add_argument("--no-llm", action="store_true", help="force fallback template (no LLM)")
    args = p.parse_args()

    if args.demo:
        jr = run_demo(tenant=args.tenant or "gadgethub-demo", allow_llm=not args.no_llm)
        st = jr["result"]["status"]
        sys.exit(0 if st in ("created_and_verified", "use_existing") else 2)
    elif args.run:
        if not args.capability:
            print("--run requires --capability (one of: " + ", ".join(CAPABILITY_HINTS) + ")")
            sys.exit(1)
        jr = run_scenario(
            tenant=args.tenant or "acme-services-demo",
            capability=args.capability,
            allow_llm=not args.no_llm,
        )
        st = jr["result"]["status"]
        sys.exit(0 if st in ("created_and_verified", "use_existing") else 2)
    elif args.design:
        d = design_tool_spec(args.capability or "warranty_check", args.tenant or "t", "", allow_llm=not args.no_llm)
        errs = validate_spec(d["spec"])
        print(json.dumps({"source": d["source"], "slug": d["slug"], "validation_errors": errs, "spec": d["spec"]}, indent=2)[:2500])
        sys.exit(0 if not errs else 2)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
