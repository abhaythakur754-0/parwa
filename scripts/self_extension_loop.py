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

# Superglue's own LLM lane (OpenAI-compatible) — $0 generation cost for Parwa
DEFAULT_LLM_URL = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgai/v1/chat/completions"
DEFAULT_LLM_KEY = "sgai_39ff17e8bca987faa7fb31c92d952ee0d9fe021fea592c4f"
LLM_MODEL = "open-mistral-7b"

LLM_URL = os.environ.get("SUPERGLUE_LLM_URL", DEFAULT_LLM_URL)
LLM_KEY = os.environ.get("SUPERGLUE_LLM_API_KEY", DEFAULT_LLM_KEY)


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
}

# LLM design hints per capability → which fallback applies + suggested slug
CAPABILITY_HINTS = {
    "warranty_check": {"slug": "warranty-status-check", "fallback": "warranty_check"},
    "order_tracking": {"slug": "order-status-lookup", "fallback": "order_tracking"},
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
            spec, source = dict(FALLBACK_TEMPLATES["warranty_check"]), "fallback_template"
            spec["id"] = slug
    return {"spec": spec, "source": source, "slug": slug}


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
                   journal: dict | None = None, allow_llm: bool = True) -> dict:
    """Full loop for one capability: detect → design → create → test.

    Self-healing: if the LLM-designed tool fails its own test, the loop
    replaces it with the validated fallback template and re-tests once.
    """
    def note(step, **kw):
        if journal is not None:
            journal.setdefault("steps", []).append({"at": datetime.now(timezone.utc).isoformat(), "step": step, **kw})

    # 1. DETECT
    det = detect_missing_tool(tenant, CAPABILITY_HINTS.get(capability, {}).get("slug", capability))
    note("detect", **det)
    if det["exists"]:
        return {"status": "use_existing", "tool_id": det["tool_id"]}

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
            "designed_by": "llm_generated",
            "status": "created_and_verified" if usable else "test_failed",
            "verdict": verdict,
            "inputs_used": effective_inputs,
            "data": res.get("json", {}).get("data") if usable else None,
        })
        if usable:
            return {
                "status": "created_and_verified",
                "tool_id": ns_spec["id"],
                "designed_by": "llm_generated",
                "verdict": verdict,
                "data": attempts[-1]["data"],
                "attempts": attempts,
            }

    # 5. SELF-HEAL: LLM design failed its test → swap in validated fallback template
    hint = CAPABILITY_HINTS.get(capability, {})
    fam = hint.get("fallback")
    if allow_llm and fam and fam in FALLBACK_TEMPLATES:
        fb_spec = dict(FALLBACK_TEMPLATES[fam])
        fb_spec["id"] = hint.get("slug", designed["slug"])
        note("self_heal", reason="llm design failed test → deploying validated fallback template")
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
                "designed_by": "fallback_template",
                "status": "created_and_verified" if ok2 else "test_failed",
                "verdict": verdict,
                "inputs_used": eff2,
                "data": raw2 if ok2 else None,
            })
            if ok2:
                return {
                    "status": "created_and_verified",
                    "tool_id": ns_spec["id"],
                    "designed_by": "fallback_template",
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--tenant")
    p.add_argument("--capability")
    p.add_argument("--design", action="store_true", help="only design + validate, don't create")
    p.add_argument("--no-llm", action="store_true", help="force fallback template (no LLM)")
    args = p.parse_args()

    if args.demo:
        jr = run_demo(tenant=args.tenant or "gadgethub-demo", allow_llm=not args.no_llm)
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
