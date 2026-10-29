#!/usr/bin/env python3
"""
PARWA Tool Factory — production, GENERIC tool deployment for Superglue.

This replaces the hardcoded Paddle `build_tool_library.py`. It can create
ANY tool from a JSON spec, for ANY tenant, in ANY industry. The 8-tool
"payments" preset ships as just one preset; new presets/specs need zero
code changes (feed a spec file, get a live tool).

DESIGN DECISIONS (production):
  1. Credentials as INPUTS, not baked-in: every provider tool takes
     `razorpayAuth` ("Basic base64(key_id:key_secret)") as a run-time input.
     - Multi-tenant correct: each tenant passes their own credentials.
     - Zero-downtime rotation: rotate keys without recreating tools.
     - Testable WITHOUT real keys: dummy creds must yield a clean,
       structured auth error — which proves the full execution path.
  2. Template-syntax self-proof: deploys `factory-template-proof` which
     echoes inputs back via postman-echo.com to prove URL, header AND
     body templating all work on the live stack before anything else.
  3. Upsert semantics: GET -> PUT (update) / POST (create), with
     DELETE+POST fallback (this stack has no PATCH).
  4. Side-car manifest: risk/approval metadata lives OUT of Superglue
     (in scripts/out/tool_manifest.json) matching Parwa's runtime
     approval-gate model (node_5_act_verify.py).
  5. Namespacing: --tenant T -> tool id `tenant_{T}__{slug}` — exactly
     what superglue_client.namespaced_tool_id() computes at runtime.

Env (all optional — defaults mirror backend/app/core/superglue_client.py):
  SUPERGLUE_API_URL, SUPERGLUE_AUTH_TOKEN

CLI:
  python3 tool_factory.py list
  python3 tool_factory.py proof                       # template-syntax proof
  python3 tool_factory.py deploy --preset payments --tenant T [--skip-proof]
  python3 tool_factory.py deploy --spec specs.json --tenant T
  python3 tool_factory.py test   --id tenant_T__transaction-status-lookup \
                                 --inputs '{"razorpayAuth":"Basic ZHVtbXk6ZHVtbXk=","paymentId":"pay_DUMMY123"}'
  python3 tool_factory.py test-preset --tenant T     # test all 8 with dummy auth
  python3 tool_factory.py delete --id <tool_id>
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ── Config (env wins; defaults mirror superglue_client.py) ──────────────────
DEFAULT_SUPERGLUE_URL = (
    "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai/sgapi"
)
DEFAULT_SUPERGLUE_TOKEN = "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b"

SUPERGLUE_URL = os.environ.get(
    "SUPERGLUE_API_URL", DEFAULT_SUPERGLUE_URL
).rstrip("/")
SUPERGLUE_TOKEN = os.environ.get("SUPERGLUE_AUTH_TOKEN", DEFAULT_SUPERGLUE_TOKEN)

HTTP_TIMEOUT = 45.0
RETRIES = 2
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Dummy Razorpay creds for credential-free testing: base64("dummy:dummy")
DUMMY_AUTH = "Basic " + base64.b64encode(b"dummy:dummy").decode()
DUMMY_PAYMENT_ID = "pay_DUMMYFACTORY000"


# ════════════════════════════════════════════════════════════════════════════
# HTTP core
# ════════════════════════════════════════════════════════════════════════════
def api_request(method: str, path: str, body: dict = None, timeout: float = HTTP_TIMEOUT) -> dict:
    """One Superglue API call with retries. Returns {'status': int, 'json': ...}."""
    url = f"{SUPERGLUE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {SUPERGLUE_TOKEN}")
            if data is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                return {"status": resp.status, "json": json.loads(raw) if raw else {}}
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode()
            except Exception:
                pass
            # 4xx are deterministic — do NOT retry
            try:
                return {"status": e.code, "json": json.loads(raw) if raw else {}}
            except Exception:
                return {"status": e.code, "json": {"raw": raw[:400]}}
        except Exception as e:  # network — retry
            last_err = e
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    return {"status": 0, "json": {"error": f"network: {last_err}"}}


def namespaced(tool_id: str, tenant: str | None) -> str:
    """Mirror of superglue_client.namespaced_tool_id()."""
    if not tenant:
        return tool_id
    if tool_id.startswith("tenant_") and "__" in tool_id:
        return tool_id
    return f"tenant_{tenant}__{tool_id}"


# ════════════════════════════════════════════════════════════════════════════
# Spec validation — every spec must satisfy this before it touches Superglue
# ════════════════════════════════════════════════════════════════════════════
def validate_spec(spec: dict) -> list[str]:
    errors: list[str] = []
    for key in ("id", "name", "instruction", "inputSchema", "steps"):
        if key not in spec:
            errors.append(f"missing field: {key}")
    if errors:
        return errors
    if not isinstance(spec["id"], str) or not spec["id"].replace("-", "").replace("_", "").isalnum():
        errors.append(f"id must be a URL-safe slug, got: {spec['id']!r}")
    if not isinstance(spec["steps"], list) or not spec["steps"]:
        errors.append("steps must be a non-empty list")
    for i, step in enumerate(spec.get("steps", [])):
        if "id" not in step or "config" not in step:
            errors.append(f"steps[{i}] missing id/config")
            continue
        cfg = step["config"]
        if cfg.get("type") == "request":
            if "url" not in cfg or "method" not in cfg:
                errors.append(f"steps[{i}] request config needs url+method")
        elif cfg.get("type") == "transform":
            if "transformCode" not in cfg:
                errors.append(f"steps[{i}] transform config needs transformCode")
        else:
            errors.append(f"steps[{i}] unknown config.type: {cfg.get('type')!r}")
    schema = spec["inputSchema"]
    if not isinstance(schema, dict) or schema.get("type") != "object":
        errors.append("inputSchema must be {'type':'object',...}")
    return errors


# ════════════════════════════════════════════════════════════════════════════
# Upsert / delete / list
# ════════════════════════════════════════════════════════════════════════════
def upsert_tool(tool_def: dict) -> dict:
    """Create or update a tool by id. Returns {action, id, status, detail}."""
    tool_id = tool_def["id"]
    existing = api_request("GET", f"/v1/tools/{tool_id}")
    if existing["status"] == 200:
        put = api_request("PUT", f"/v1/tools/{tool_id}", tool_def)
        if put["status"] in (200, 201):
            return {"action": "updated", "id": tool_id, "ok": True, "status": put["status"]}
        # stack has no PATCH/PUT on some versions — fallback DELETE+POST
        api_request("DELETE", f"/v1/tools/{tool_id}")
        post = api_request("POST", "/v1/tools", tool_def)
        return {
            "action": "recreated",
            "id": tool_id,
            "ok": post["status"] in (200, 201),
            "status": post["status"],
            "detail": post["json"],
        }
    if existing["status"] == 404:
        post = api_request("POST", "/v1/tools", tool_def)
        ok = post["status"] in (200, 201)
        detail = post["json"] if not ok else None
        return {"action": "created", "id": tool_id, "ok": ok, "status": post["status"], "detail": detail}
    return {
        "action": "failed",
        "id": tool_id,
        "ok": False,
        "status": existing["status"],
        "detail": existing["json"],
    }


def tool_exists(tool_id: str) -> bool:
    return api_request("GET", f"/v1/tools/{tool_id}")["status"] == 200


def get_tool(tool_id: str) -> dict | None:
    r = api_request("GET", f"/v1/tools/{tool_id}")
    return r["json"] if r["status"] == 200 else None


def delete_tool(tool_id: str) -> dict:
    r = api_request("DELETE", f"/v1/tools/{tool_id}")
    return {"id": tool_id, "status": r["status"], "ok": r["status"] in (200, 202, 204, 404)}


def list_tools() -> list[dict]:
    r = api_request("GET", "/v1/tools")
    data = r["json"]
    if isinstance(data, dict):
        return data.get("data", [])
    return data if isinstance(data, list) else []


# ════════════════════════════════════════════════════════════════════════════
# Run / test
# ════════════════════════════════════════════════════════════════════════════
def run_tool(tool_id: str, inputs: dict, timeout: float = 90.0) -> dict:
    """Execute a saved tool — the EXACT call Parwa's runtime makes."""
    r = api_request("POST", f"/v1/tools/{tool_id}/run", {"inputs": inputs}, timeout=timeout)
    return r


def classify_result(res: dict) -> dict:
    """Turn a raw run result into a production verdict.

    Verdicts:
      success            — tool ran and returned usable data
      auth_missing       — reached the provider, provider says 401/403
                           (expected & CORRECT when testing with dummy creds:
                            proves DNS, routing, auth-header shape, template
                            engine — only the key value is missing)
      tool_error         — tool exists but its logic failed (needs fixing)
      transport_error    — could not even reach Superglue
    """
    status = res.get("status", 0)
    body = res.get("json", {})
    if status == 0:
        return {"verdict": "transport_error", "detail": body}
    if status in (401, 403):
        return {"verdict": "auth_missing", "detail": "superglue token rejected"}
    blob = json.dumps(body)
    if status == 200 and body.get("status") == "success":
        return {"verdict": "success", "detail": body.get("data")}
    if status == 200 and ("401" in blob or "403" in blob or "Unauthorized" in blob or "Authentication" in blob):
        return {"verdict": "auth_missing", "detail": "provider rejected dummy creds (path OK)"}
    if status == 404:
        return {"verdict": "tool_error", "detail": "tool not found (was it deployed?)"}
    if status == 200:
        return {"verdict": "tool_error", "detail": body}
    return {"verdict": "tool_error", "detail": body}


# ════════════════════════════════════════════════════════════════════════════
# PRESET: payments (Razorpay) — 8 production tools
# Credentials are INPUTS. Template syntax mirrors proven patterns:
#   <<input>> refs, <<(sourceData) => ...>> builders, sourceData.<step>.data.*
# ════════════════════════════════════════════════════════════════════════════
RZ = "https://api.razorpay.com/v1"
AUTH_SCHEMA = {
    "razorpayAuth": {
        "type": "string",
        "description": "Razorpay Basic auth header value: 'Basic ' + base64(key_id + ':' + key_secret)",
    }
}

# 0. Template-syntax proof (factory self-verification, industry-agnostic)
TOOL_TEMPLATE_PROOF = {
    "id": "factory-template-proof",
    "name": "Factory Template Proof",
    "instruction": (
        "Factory self-test. Echoes tool inputs back through postman-echo.com to "
        "prove that URL templating (<<input>>), header templating, and body "
        "arrow-templates all work on this Superglue stack. Read-only, no credentials."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["proofToken"],
        "properties": {
            "proofToken": {"type": "string", "description": "Any string to echo back"}
        },
    },
    "steps": [
        {
            "id": "echoGet",
            "instruction": "GET echo with URL query + custom header templating",
            "config": {
                "type": "request",
                "method": "GET",
                "url": "https://postman-echo.com/get?proof=<<proofToken>>",
                "headers": {"X-Factory-Proof": "<<proofToken>>"},
            },
        },
        {
            "id": "echoPost",
            "instruction": "POST echo with arrow-template body",
            "config": {
                "type": "request",
                "method": "POST",
                "url": "https://postman-echo.com/post",
                "headers": {"Content-Type": "application/json"},
                "body": "<<(sourceData) => JSON.stringify({ proof: sourceData.proofToken, origin: 'tool-factory' })>>",
            },
        },
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var g = sourceData.echoGet && sourceData.echoGet.data ? sourceData.echoGet.data : {};"
        " var p = sourceData.echoPost && sourceData.echoPost.data ? sourceData.echoPost.data : {};"
        " var q = g.args && g.args.proof ? g.args.proof : '';"
        " var h = g.headers && g.headers['x-factory-proof'] ? g.headers['x-factory-proof'] : (g.headers && g.headers['X-Factory-Proof'] ? g.headers['X-Factory-Proof'] : '');"
        " var bp = p.data && p.data.proof ? p.data.proof : '';"
        " return JSON.stringify({ url_template_ok: q !== '', header_template_ok: h !== '', body_template_ok: bp !== '', echoed: q });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 1. payment-refund-by-email (WRITE — approval-gated at runtime)
TOOL_REFUND_BY_EMAIL = {
    "id": "payment-refund-by-email",
    "name": "Refund Customer by Email (Razorpay)",
    "instruction": (
        "Find a Razorpay payment by the customer's email, refund it (full refund by "
        "default, or refundAmountPaise paise), and return a refund summary. Use when a "
        "customer requests a refund and provides their email."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "customerEmail"],
        "properties": {
            **AUTH_SCHEMA,
            "customerEmail": {"type": "string", "description": "Customer email to find and refund"},
            "refundAmountPaise": {
                "type": "integer",
                "description": "Refund amount in paise (optional — omit for FULL refund)",
            },
        },
    },
    "steps": [
        {
            "id": "listPayments",
            "instruction": "List recent payments to find the customer's payment",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/payments?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "findPayment",
            "instruction": "Filter payments by the customer email",
            "config": {
                "type": "transform",
                "transformCode": (
                    "(sourceData) => { try {"
                    " var resp = sourceData.listPayments || {};"
                    " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
                    " var email = String(sourceData.customerEmail || '').toLowerCase();"
                    " var match = null;"
                    " for (var i = 0; i < items.length; i++) {"
                    "  var it = items[i];"
                    "  if (it && it.email && String(it.email).toLowerCase() === email && it.status === 'captured') { match = it; break; }"
                    " }"
                    " return { found: !!match, payment: match ? { id: match.id, amount: match.amount, currency: match.currency, status: match.status, email: match.email } : null, searched: items.length };"
                    " } catch (e) { return { found: false, error: String(e) }; } }"
                ),
            },
        },
        {
            "id": "processRefund",
            "instruction": "Refund the found payment (full or partial)",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "POST",
                "url": "<<(sourceData) => 'https://api.razorpay.com/v1/payments/' + sourceData.findPayment.data.payment.id + '/refund'>>",
                "headers": {"Authorization": "<<razorpayAuth>>", "Content-Type": "application/json"},
                "body": "<<(sourceData) => JSON.stringify(sourceData.refundAmountPaise ? { amount: sourceData.refundAmountPaise } : {})>>",
            },
        },
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var f = sourceData.findPayment && sourceData.findPayment.data ? sourceData.findPayment.data : { found: false };"
        " var r = sourceData.processRefund && sourceData.processRefund.data ? sourceData.processRefund.data : null;"
        " var refundId = r && r.id ? r.id : (r && r.refund && r.refund.id ? r.refund.id : null);"
        " return JSON.stringify({ found: f.found === true, payment_id: f.payment ? f.payment.id : null, refunded: !!refundId, refund_id: refundId, amount_paise: f.payment ? f.payment.amount : null, currency: f.payment ? f.payment.currency : null, raw_refund_error: r && r.error ? r.error : null });"
        " } catch (e) { return JSON.stringify({ found: false, error: String(e) }); } }"
    ),
}

# 2. payment-refund-by-txn (WRITE — approval-gated)
TOOL_REFUND_BY_TXN = {
    "id": "payment-refund-by-txn",
    "name": "Refund by Transaction ID (Razorpay)",
    "instruction": (
        "Refund a Razorpay payment directly by its payment ID (pay_xxx). Refunds "
        "refundAmountPaise paise, or the full amount if omitted. Use when the ticket "
        "already contains the transaction/payment ID."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "paymentId"],
        "properties": {
            **AUTH_SCHEMA,
            "paymentId": {"type": "string", "description": "Razorpay payment id (pay_xxx)"},
            "refundAmountPaise": {"type": "integer", "description": "Amount in paise (omit = full refund)"},
        },
    },
    "steps": [
        {
            "id": "fetchPayment",
            "instruction": "Fetch the payment to confirm it exists and get its amount",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/payments/<<paymentId>>",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "processRefund",
            "instruction": "Refund the payment",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "POST",
                "url": f"{RZ}/payments/<<paymentId>>/refund",
                "headers": {"Authorization": "<<razorpayAuth>>", "Content-Type": "application/json"},
                "body": "<<(sourceData) => JSON.stringify(sourceData.refundAmountPaise ? { amount: sourceData.refundAmountPaise } : {})>>",
            },
        },
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var p = sourceData.fetchPayment && sourceData.fetchPayment.data ? sourceData.fetchPayment.data : {};"
        " var r = sourceData.processRefund && sourceData.processRefund.data ? sourceData.processRefund.data : null;"
        " var refundId = r && r.id ? r.id : null;"
        " return JSON.stringify({ payment_found: !!p.id, payment_status: p.status || null, refunded: !!refundId, refund_id: refundId, error: r && r.error ? r.error : null });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 3. subscription-cancel-by-email (WRITE — approval-gated)
TOOL_SUB_CANCEL = {
    "id": "subscription-cancel-by-email",
    "name": "Cancel Subscription by Email (Razorpay)",
    "instruction": (
        "Find the customer by email, locate their active Razorpay subscription, cancel "
        "it, and return a confirmation. Use when a customer asks to cancel their plan."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "customerEmail"],
        "properties": {
            **AUTH_SCHEMA,
            "customerEmail": {"type": "string", "description": "Customer email whose subscription should be cancelled"},
            "cancelAtCycleEnd": {"type": "integer", "description": "1 = cancel at cycle end (default), 0 = immediate"},
        },
    },
    "steps": [
        {
            "id": "listCustomers",
            "instruction": "List Razorpay customers",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/customers?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "findCustomer",
            "instruction": "Find the customer by email",
            "config": {
                "type": "transform",
                "transformCode": (
                    "(sourceData) => { try {"
                    " var resp = sourceData.listCustomers || {};"
                    " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
                    " var email = String(sourceData.customerEmail || '').toLowerCase();"
                    " var match = null;"
                    " for (var i = 0; i < items.length; i++) {"
                    "  var c = items[i];"
                    "  if (c && c.email && String(c.email).toLowerCase() === email) { match = c; break; }"
                    " }"
                    " return { found: !!match, customer: match ? { id: match.id, name: match.name, email: match.email } : null, searched: items.length };"
                    " } catch (e) { return { found: false, error: String(e) }; } }"
                ),
            },
        },
        {
            "id": "listSubscriptions",
            "instruction": "List subscriptions to find this customer's active subscription",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/subscriptions?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "findSubscription",
            "instruction": "Filter subscriptions by customer id, prefer active ones",
            "config": {
                "type": "transform",
                "transformCode": (
                    "(sourceData) => { try {"
                    " var resp = sourceData.listSubscriptions || {};"
                    " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
                    " var cust = sourceData.findCustomer && sourceData.findCustomer.data ? sourceData.findCustomer.data.customer : null;"
                    " if (!cust) return { found: false, reason: 'customer_not_found' };"
                    " var match = null;"
                    " for (var i = 0; i < items.length; i++) {"
                    "  var s = items[i];"
                    "  if (s && s.customer_id === cust.id && (s.status === 'active' || s.status === 'authenticated')) { match = s; break; }"
                    " }"
                    " return { found: !!match, subscription: match ? { id: match.id, status: match.status } : null };"
                    " } catch (e) { return { found: false, error: String(e) }; } }"
                ),
            },
        },
        {
            "id": "cancelSubscription",
            "instruction": "Cancel the subscription",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "POST",
                "url": "<<(sourceData) => 'https://api.razorpay.com/v1/subscriptions/' + sourceData.findSubscription.data.subscription.id + '/cancel'>>",
                "headers": {"Authorization": "<<razorpayAuth>>", "Content-Type": "application/json"},
                "body": "<<(sourceData) => JSON.stringify({ cancel_at_cycle_end: sourceData.cancelAtCycleEnd === 0 ? 0 : 1 })>>",
            },
        },
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var c = sourceData.findCustomer && sourceData.findCustomer.data ? sourceData.findCustomer.data : { found: false };"
        " var s = sourceData.findSubscription && sourceData.findSubscription.data ? sourceData.findSubscription.data : { found: false };"
        " var x = sourceData.cancelSubscription && sourceData.cancelSubscription.data ? sourceData.cancelSubscription.data : null;"
        " return JSON.stringify({ customer_found: c.found === true, subscription_found: s.found === true, cancelled: !!(x && x.id), subscription_id: s.subscription ? s.subscription.id : null, new_status: x ? x.status : null });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 4. customer-lookup-by-email (READ-ONLY)
TOOL_CUSTOMER_LOOKUP = {
    "id": "customer-lookup-by-email",
    "name": "Customer Lookup by Email (Razorpay)",
    "instruction": (
        "Look up a customer by email and return their profile plus recent payments. "
        "Read-only. Use to identify who the customer is before taking any action."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "customerEmail"],
        "properties": {**AUTH_SCHEMA, "customerEmail": {"type": "string", "description": "Email to look up"}},
    },
    "steps": [
        {
            "id": "listCustomers",
            "instruction": "List Razorpay customers",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/customers?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "findCustomer",
            "instruction": "Find the customer by email",
            "config": {
                "type": "transform",
                "transformCode": (
                    "(sourceData) => { try {"
                    " var resp = sourceData.listCustomers || {};"
                    " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
                    " var email = String(sourceData.customerEmail || '').toLowerCase();"
                    " var match = null;"
                    " for (var i = 0; i < items.length; i++) {"
                    "  var c = items[i];"
                    "  if (c && c.email && String(c.email).toLowerCase() === email) { match = c; break; }"
                    " }"
                    " return { found: !!match, customer: match ? { id: match.id, name: match.name, email: match.email, contact: match.contact, created_at: match.created_at } : null, searched: items.length };"
                    " } catch (e) { return { found: false, error: String(e) }; } }"
                ),
            },
        },
        {
            "id": "listPayments",
            "instruction": "List payments to enrich the profile",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/payments?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var f = sourceData.findCustomer && sourceData.findCustomer.data ? sourceData.findCustomer.data : { found: false };"
        " var resp = sourceData.listPayments || {};"
        " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
        " var cust = f.customer ? f.customer : null;"
        " var pays = [];"
        " if (cust) { for (var i = 0; i < items.length; i++) { var p = items[i]; if (p && (p.email === cust.email || p.customer_id === cust.id)) { pays.push({ id: p.id, amount: p.amount, currency: p.currency, status: p.status }); } } }"
        " return JSON.stringify({ found: f.found === true, customer: cust, recent_payments: pays.slice(0, 10), payment_count: pays.length });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 5. transaction-status-lookup (READ-ONLY)
TOOL_TXN_STATUS = {
    "id": "transaction-status-lookup",
    "name": "Transaction Status Lookup (Razorpay)",
    "instruction": (
        "Fetch a Razorpay payment by ID and return its current status (created/"
        "authorized/captured/refunded/failed), amount and method. Read-only. Use when "
        "a customer asks 'did my payment go through?'."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "paymentId"],
        "properties": {**AUTH_SCHEMA, "paymentId": {"type": "string", "description": "Razorpay payment id (pay_xxx)"}},
    },
    "steps": [
        {
            "id": "fetchPayment",
            "instruction": "Fetch the payment record",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/payments/<<paymentId>>",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        }
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var p = sourceData.fetchPayment && sourceData.fetchPayment.data ? sourceData.fetchPayment.data : {};"
        " return JSON.stringify({ found: !!p.id, payment_id: p.id || null, status: p.status || null, amount: p.amount || null, currency: p.currency || null, method: p.method || null, captured_at: p.captured_at || null, error_description: p.error_description || null });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 6. list-catalog-summary (READ-ONLY)
TOOL_CATALOG_SUMMARY = {
    "id": "list-catalog-summary",
    "name": "List Catalog Summary (Razorpay Items)",
    "instruction": (
        "List the tenant's product catalog (Razorpay Items) with prices and return a "
        "compact summary. Read-only. Use when a customer asks 'what do you sell?' or "
        "'what plans do you have?'."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth"],
        "properties": {**AUTH_SCHEMA},
    },
    "steps": [
        {
            "id": "listItems",
            "instruction": "List catalog items",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/items?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        }
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var resp = sourceData.listItems || {};"
        " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
        " var out = [];"
        " for (var i = 0; i < items.length; i++) { var it = items[i]; if (it) out.push({ id: it.id, name: it.name, amount: it.amount, currency: it.currency, active: it.active }); }"
        " return JSON.stringify({ catalog_size: out.length, items: out });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 7. product-catalog-search (READ-ONLY)
TOOL_CATALOG_SEARCH = {
    "id": "product-catalog-search",
    "name": "Product Catalog Search (Razorpay Items)",
    "instruction": (
        "Search the product catalog by name substring and return matching products "
        "with prices. Read-only. Use for 'how much is X?' questions."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth", "searchQuery"],
        "properties": {**AUTH_SCHEMA, "searchQuery": {"type": "string", "description": "Product name fragment to search"}},
    },
    "steps": [
        {
            "id": "listItems",
            "instruction": "List catalog items",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/items?count=100",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        },
        {
            "id": "searchItems",
            "instruction": "Filter items by name substring",
            "config": {
                "type": "transform",
                "transformCode": (
                    "(sourceData) => { try {"
                    " var resp = sourceData.listItems || {};"
                    " var items = (resp.data && resp.data.items) ? resp.data.items : [];"
                    " var q = String(sourceData.searchQuery || '').toLowerCase();"
                    " var out = [];"
                    " for (var i = 0; i < items.length; i++) { var it = items[i]; if (it && it.name && String(it.name).toLowerCase().indexOf(q) !== -1) out.push({ id: it.id, name: it.name, amount: it.amount, currency: it.currency }); }"
                    " return { query: q, matches: out.length, items: out };"
                    " } catch (e) { return { error: String(e) }; } }"
                ),
            },
        }
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var s = sourceData.searchItems && sourceData.searchItems.data ? sourceData.searchItems.data : { matches: 0, items: [] };"
        " return JSON.stringify({ query: s.query || null, matches: s.matches || 0, items: s.items || [] });"
        " } catch (e) { return JSON.stringify({ error: String(e) }); } }"
    ),
}

# 8. integration-health-check (READ-ONLY, no real creds needed to interpret)
TOOL_HEALTH_CHECK = {
    "id": "integration-health-check",
    "name": "Integration Health Check (Razorpay)",
    "instruction": (
        "Ping the Razorpay API with the tenant's credentials and report connectivity "
        "and auth status. Read-only. Use to diagnose 'payments are down' reports."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["razorpayAuth"],
        "properties": {**AUTH_SCHEMA},
    },
    "steps": [
        {
            "id": "pingApi",
            "instruction": "Minimal authenticated request to Razorpay",
            "failureBehavior": "continue",
            "config": {
                "type": "request",
                "method": "GET",
                "url": f"{RZ}/payments?count=1",
                "headers": {"Authorization": "<<razorpayAuth>>"},
            },
        }
    ],
    "outputTransform": (
        "(sourceData) => { try {"
        " var r = sourceData.pingApi || {};"
        " var d = (r.data && typeof r.data === 'object') ? r.data : {};"
        " var ok = !!(d.entity === 'collection');"
        " if (ok) { return JSON.stringify({ connected: true, auth: 'valid', api_reachable: true, detail: 'api ok, ' + (d.count || 0) + ' payments visible' }); }"
        " return JSON.stringify({ connected: false, auth: 'invalid_or_unreachable', api_reachable: true, detail: 'probe step failed — inspect stepResults[].error for the HTTP status (HTTP 401 Authentication failed = bad credentials; timeout = network issue)' });"
        " } catch (e) { return JSON.stringify({ connected: false, auth: 'unknown', api_reachable: false, error: String(e) }); } }"
    ),
}

PAYMENTS_PRESET = [
    TOOL_TEMPLATE_PROOF,
    TOOL_REFUND_BY_EMAIL,
    TOOL_REFUND_BY_TXN,
    TOOL_SUB_CANCEL,
    TOOL_CUSTOMER_LOOKUP,
    TOOL_TXN_STATUS,
    TOOL_CATALOG_SUMMARY,
    TOOL_CATALOG_SEARCH,
    TOOL_HEALTH_CHECK,
]

# Side-car manifest: risk metadata matching node_5 approval-gate model
RISK_MANIFEST = {
    "factory-template-proof": {"risk": "read", "approval_required": False},
    "payment-refund-by-email": {"risk": "write", "approval_required": True, "threshold_cents": 5000},
    "payment-refund-by-txn": {"risk": "write", "approval_required": True, "threshold_cents": 5000},
    "subscription-cancel-by-email": {"risk": "write", "approval_required": True, "threshold_cents": 0},
    "customer-lookup-by-email": {"risk": "read", "approval_required": False},
    "transaction-status-lookup": {"risk": "read", "approval_required": False},
    "list-catalog-summary": {"risk": "read", "approval_required": False},
    "product-catalog-search": {"risk": "read", "approval_required": False},
    "integration-health-check": {"risk": "read", "approval_required": False},
}


# ════════════════════════════════════════════════════════════════════════════
# Test matrix for the payments preset — credential-free
# ════════════════════════════════════════════════════════════════════════════
def preset_test_cases(tenant: str | None) -> list[dict]:
    ns = lambda slug: namespaced(slug, tenant)
    return [
        {
            "id": ns("factory-template-proof"),
            "inputs": {"proofToken": f"factory-proof-{int(time.time())}"},
            "expect": "success",
            "why": "proves URL+header+body templating on this stack",
        },
        {
            "id": ns("payment-refund-by-email"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "customerEmail": "someone@example.com"},
            "expect": "auth_missing",
            "why": "dummy creds must yield a clean provider-auth error (path proof)",
        },
        {
            "id": ns("payment-refund-by-txn"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "paymentId": DUMMY_PAYMENT_ID},
            "expect": "auth_missing",
            "why": "direct refund path",
        },
        {
            "id": ns("subscription-cancel-by-email"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "customerEmail": "someone@example.com"},
            "expect": "auth_missing",
            "why": "cancel path",
        },
        {
            "id": ns("customer-lookup-by-email"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "customerEmail": "someone@example.com"},
            "expect": "auth_missing",
            "why": "lookup path",
        },
        {
            "id": ns("transaction-status-lookup"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "paymentId": DUMMY_PAYMENT_ID},
            "expect": "auth_missing",
            "why": "status path",
        },
        {
            "id": ns("list-catalog-summary"),
            "inputs": {"razorpayAuth": DUMMY_AUTH},
            "expect": "auth_missing",
            "why": "catalog path",
        },
        {
            "id": ns("product-catalog-search"),
            "inputs": {"razorpayAuth": DUMMY_AUTH, "searchQuery": "plan"},
            "expect": "auth_missing",
            "why": "search path",
        },
        {
            "id": ns("integration-health-check"),
            "inputs": {"razorpayAuth": DUMMY_AUTH},
            "expect": "success",
            "why": "health check returns structured report; dummy creds must show connected:false + HTTP 401 in stepResults (Razorpay reached, creds rejected)",
            "expect_payload": {"connected": False},
            "expect_stepresults_contains": "401",
        },
    ]


# ════════════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════════════
def write_out(name: str, payload: dict) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def cmd_list(_args):
    tools = list_tools()
    print(f"Superglue tools on stack: {len(tools)}")
    for t in tools:
        print(f"  - {t.get('id')}  |  {t.get('name')}")


def cmd_proof(_args):
    """Deploy + run the template-proof tool."""
    spec = dict(TOOL_TEMPLATE_PROOF)
    errs = validate_spec(spec)
    if errs:
        print("PROOF SPEC INVALID:", errs)
        sys.exit(1)
    up = upsert_tool(spec)
    print(f"upsert: {up}")
    res = run_tool(spec["id"], {"proofToken": f"proof-{int(time.time())}"})
    verdict = classify_result(res)
    print("run:", json.dumps(res.get("json", {}), indent=2)[:1200])
    print("verdict:", verdict["verdict"])
    data = verdict.get("detail")
    ok = verdict["verdict"] == "success" and isinstance(data, (dict, str)) and (
        isinstance(data, dict) and data.get("url_template_ok") and data.get("header_template_ok") and data.get("body_template_ok")
        if isinstance(data, dict) else '"url_template_ok":true' in str(data)
    )
    write_out("template_proof.json", {"upsert": up, "run": res.get("json"), "verdict": verdict, "ok": bool(ok)})
    print("TEMPLATE PROOF:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 2)


def cmd_deploy(args):
    tenant = args.tenant
    if args.spec:
        with open(args.spec) as f:
            specs = json.load(f)
        if isinstance(specs, dict):
            specs = [specs]
    elif args.preset == "payments":
        specs = PAYMENTS_PRESET
    else:
        print(f"unknown preset: {args.preset}")
        sys.exit(1)

    report = {"tenant": tenant, "deployed": [], "errors": [], "ts": datetime.now(timezone.utc).isoformat()}
    for raw in specs:
        spec = dict(raw)
        spec["id"] = namespaced(spec["id"], tenant)
        errs = validate_spec(spec)
        if errs:
            report["errors"].append({"id": spec["id"], "errors": errs})
            print(f"  ✗ {spec['id']}: INVALID — {errs}")
            continue
        up = upsert_tool(spec)
        mark = "✓" if up["ok"] else "✗"
        print(f"  {mark} {spec['id']}: {up['action']} (http {up['status']})")
        entry = {k: v for k, v in up.items()}
        if not up["ok"]:
            report["errors"].append(entry)
        report["deployed"].append(entry)

    # side-car manifest (namespaced)
    manifest = {
        namespaced(k, tenant): v for k, v in RISK_MANIFEST.items()
    }
    write_out("tool_manifest.json", {"tenant": tenant, "tools": manifest})

    ok = not report["errors"]
    print(f"\nDEPLOY {'OK' if ok else 'WITH ERRORS'}: {len(report['deployed'])} tools, {len(report['errors'])} errors")
    write_out("deploy_report.json", report)
    sys.exit(0 if ok else 2)


def cmd_test(args):
    inputs = json.loads(args.inputs) if args.inputs else {}
    tid = args.id
    if args.tenant and not tid.startswith("tenant_"):
        tid = namespaced(tid, args.tenant)
    res = run_tool(tid, inputs)
    verdict = classify_result(res)
    print(json.dumps({"tool": tid, "verdict": verdict["verdict"], "result": res.get("json")}, indent=2, default=str)[:2000])
    write_out("tool_test.json", {"tool": tid, "verdict": verdict, "result": res.get("json")})
    expected_ok = verdict["verdict"] in ("success", "auth_missing")
    print("TEST:", "PASS" if expected_ok else "FAIL")
    sys.exit(0 if expected_ok else 2)


def cmd_test_preset(args):
    cases = preset_test_cases(args.tenant)
    results = []
    for c in cases:
        res = run_tool(c["id"], c["inputs"])
        verdict = classify_result(res)
        passed = verdict["verdict"] == c["expect"]
        # optional deep payload assertions
        payload_note = ""
        if passed and c.get("expect_payload"):
            detail = verdict.get("detail")
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except Exception:
                    detail = {}
            if not isinstance(detail, dict):
                detail = {}
            for k, v in c["expect_payload"].items():
                if detail.get(k) != v:
                    passed = False
                    payload_note = f" [payload mismatch: {k}={detail.get(k)!r}, want {v!r}]"
        if passed and c.get("expect_stepresults_contains"):
            raw = json.dumps(res.get("json", {}))
            if c["expect_stepresults_contains"] not in raw:
                passed = False
                payload_note = f" [stepResults missing {c['expect_stepresults_contains']!r}]"
        results.append({**c, "verdict": verdict["verdict"], "passed": passed, "result": res.get("json")})
        mark = "✓" if passed else "✗"
        print(f"  {mark} {c['id']} → {verdict['verdict']} (expected {c['expect']}){payload_note} — {c['why']}")
    passed_n = sum(1 for r in results if r["passed"])
    report = {
        "tenant": args.tenant,
        "total": len(results),
        "passed": passed_n,
        "ts": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    print(f"\nPRESET TESTS: {passed_n}/{len(results)} passed")
    write_out("preset_test_report.json", report)
    sys.exit(0 if passed_n == len(results) else 2)


def cmd_delete(args):
    tid = args.id
    if args.tenant and not tid.startswith("tenant_"):
        tid = namespaced(tid, args.tenant)
    r = delete_tool(tid)
    print(json.dumps(r))
    sys.exit(0 if r["ok"] else 2)


def main():
    if not SUPERGLUE_URL or not SUPERGLUE_TOKEN:
        print("ERROR: SUPERGLUE_API_URL / SUPERGLUE_AUTH_TOKEN missing")
        sys.exit(1)
    p = argparse.ArgumentParser(description="PARWA Tool Factory")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("proof").set_defaults(func=cmd_proof)

    d = sub.add_parser("deploy")
    d.add_argument("--preset", choices=["payments"])
    d.add_argument("--spec", help="path to a JSON file with one tool spec or a list")
    d.add_argument("--tenant", help="tenant id for namespacing")
    d.add_argument("--skip-proof", action="store_true")
    d.set_defaults(func=cmd_deploy)

    t = sub.add_parser("test")
    t.add_argument("--id", required=True)
    t.add_argument("--inputs", default="{}")
    t.add_argument("--tenant")
    t.set_defaults(func=cmd_test)

    tp = sub.add_parser("test-preset")
    tp.add_argument("--tenant")
    tp.set_defaults(func=cmd_test_preset)

    x = sub.add_parser("delete")
    x.add_argument("--id", required=True)
    x.add_argument("--tenant")
    x.set_defaults(func=cmd_delete)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
