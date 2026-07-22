"""
Debug endpoint for testing LLM connectivity.

GET /api/v1/debug/llm-test
Returns: { cerebras: {ok, error?}, groq: {ok, error?}, smart_router: {ok, error?} }

This endpoint is for debugging only — it makes a real LLM call to each
provider and reports whether it succeeded or failed.
"""
from __future__ import annotations

import os
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.api.debug")

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm-test")
async def llm_test() -> Dict[str, Any]:
    """Test LLM connectivity to all configured providers."""
    results: Dict[str, Any] = {}
    # Test messages
    messages = [{"role": "user", "content": "Reply with the single word: ok"}]

    # ── 1. Test Cerebras directly ──
    cerebras_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not cerebras_key:
        results["cerebras"] = {"ok": False, "error": "CEREBRAS_API_KEY not set"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    json={
                        "model": "gpt-oss-120b",
                        "messages": messages,
                        "max_tokens": 10,
                        "temperature": 0,
                    },
                    headers={
                        "Authorization": f"Bearer {cerebras_key}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code == 200:
                    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    results["cerebras"] = {"ok": True, "response": content[:50]}
                else:
                    results["cerebras"] = {"ok": False, "status": r.status_code, "error": r.text[:300]}
        except Exception as exc:
            results["cerebras"] = {"ok": False, "error": str(exc)[:300]}

    # ── 2. Test Groq directly ──
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        results["groq"] = {"ok": False, "error": "GROQ_API_KEY not set"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": messages,
                        "max_tokens": 10,
                        "temperature": 0,
                    },
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code == 200:
                    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    results["groq"] = {"ok": True, "response": content[:50]}
                else:
                    results["groq"] = {"ok": False, "status": r.status_code, "error": r.text[:300]}
        except Exception as exc:
            results["groq"] = {"ok": False, "error": str(exc)[:300]}

    # ── 3. Test Smart Router ──
    try:
        from app.core.smart_router import SmartRouter, AtomicStepType
        router_sr = SmartRouter()
        routing = router_sr.route(
            company_id="debug",
            variant_type="parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_SIMPLE,
        )
        result = await router_sr.async_execute_llm_call(
            company_id="debug",
            routing_decision=routing,
            messages=messages,
            temperature=0,
            max_tokens=10,
        )
        content = result.get("content", "")
        error = result.get("error", "")
        results["smart_router"] = {
            "ok": bool(content and len(content) > 0),
            "content": content[:50] if content else "",
            "error": error[:300] if error else "",
            "model": result.get("model", ""),
            "provider": result.get("provider", ""),
            "fallback_used": result.get("fallback_used", False),
        }
    except Exception as exc:
        results["smart_router"] = {"ok": False, "error": str(exc)[:300]}

    # ── 4. Check litellm ──
    try:
        import litellm
        results["litellm"] = {"ok": True, "version": litellm.__version__}
    except Exception as exc:
        results["litellm"] = {"ok": False, "error": str(exc)[:300]}

    # ── 5. List available models from each provider ──
    # This tells us EXACTLY what model names Cerebras and Groq accept.
    if cerebras_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    "https://api.cerebras.ai/v1/models",
                    headers={"Authorization": f"Bearer {cerebras_key}"},
                )
                if r.status_code == 200:
                    models = r.json().get("data", [])
                    results["cerebras_models"] = [m.get("id", "") for m in models[:20]]
                else:
                    results["cerebras_models"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            results["cerebras_models"] = f"Error: {str(exc)[:200]}"

    if groq_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq_key}"},
                )
                if r.status_code == 200:
                    models = r.json().get("data", [])
                    results["groq_models"] = [m.get("id", "") for m in models[:20]]
                else:
                    results["groq_models"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            results["groq_models"] = f"Error: {str(exc)[:200]}"

    return results


@router.post("/test-user-keys")
async def test_user_keys(request: Request) -> Dict[str, Any]:
    """Test user-provided Cerebras + Groq API keys from Render's server.

    This lets users verify their keys work BEFORE updating Render env vars.
    """
    import httpx
    import time as _time

    body = await request.json()
    cerebras_key = body.get("cerebras_key", "")
    groq_key = body.get("groq_key", "")

    results: Dict[str, Any] = {}
    messages = [{"role": "user", "content": "Reply with: ok"}]

    # Test Cerebras
    if cerebras_key:
        t0 = _time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    json={"model": "gpt-oss-120b", "messages": messages, "max_tokens": 10},
                    headers={"Authorization": f"Bearer {cerebras_key}", "Content-Type": "application/json"},
                )
            latency_ms = int((_time.time() - t0) * 1000)
            if r.status_code == 200:
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                results["cerebras"] = {"ok": True, "response": content[:50], "latency_ms": latency_ms, "model": "gpt-oss-120b"}
            else:
                results["cerebras"] = {"ok": False, "status": r.status_code, "error": r.text[:300], "latency_ms": latency_ms}
        except Exception as exc:
            results["cerebras"] = {"ok": False, "error": str(exc)[:300]}
    else:
        results["cerebras"] = {"ok": False, "error": "No cerebras_key provided"}

    # Test Groq
    if groq_key:
        t0 = _time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={"model": "llama-3.1-8b-instant", "messages": messages, "max_tokens": 10},
                    headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                )
            latency_ms = int((_time.time() - t0) * 1000)
            if r.status_code == 200:
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                results["groq"] = {"ok": True, "response": content[:50], "latency_ms": latency_ms, "model": "llama-3.1-8b-instant"}
            else:
                results["groq"] = {"ok": False, "status": r.status_code, "error": r.text[:300], "latency_ms": latency_ms}
        except Exception as exc:
            results["groq"] = {"ok": False, "error": str(exc)[:300]}
    else:
        results["groq"] = {"ok": False, "error": "No groq_key provided"}

    return results


@router.post("/test-google-models")
async def test_google_models(request: Request) -> Dict[str, Any]:
    """Test multiple Google AI models to see which share quota.

    Tests gemma-3-27b-it, gemini-2.5-flash, gemini-2.5-flash-lite,
    and gemini-3.5-flash — all with the same API key.

    This answers: if one Google model runs out of quota, do ALL stop?
    """
    import httpx
    import asyncio

    body = await request.json()
    google_key = body.get("google_key", "")

    if not google_key:
        return {"error": "No google_key provided"}

    models_to_test = [
        ("gemma-3-27b-it", "Gemma 3 27B (14,400 RPD)"),
        ("gemma-3-12b-it", "Gemma 3 12B (14,400 RPD)"),
        ("gemma-3-4b-it", "Gemma 3 4B (14,400 RPD)"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash (20 RPD)"),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite (20 RPD)"),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite (500 RPD)"),
        ("gemini-3-flash", "Gemini 3 Flash (20 RPD)"),
        ("gemini-3.5-flash", "Gemini 3.5 Flash (20 RPD)"),
    ]

    results: Dict[str, Any] = {}
    messages = [{"role": "user", "content": "Reply with: ok"}]

    for model_id, display_name in models_to_test:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={google_key}",
                    json={
                        "contents": [{"parts": [{"text": "Reply with: ok"}]}],
                        "generationConfig": {"maxOutputTokens": 10},
                    },
                )
            if r.status_code == 200:
                content = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                results[model_id] = {"ok": True, "response": content[:30], "name": display_name}
            else:
                error = r.text[:200]
                results[model_id] = {"ok": False, "status": r.status_code, "error": error, "name": display_name}
        except Exception as exc:
            results[model_id] = {"ok": False, "error": str(exc)[:200], "name": display_name}

        await asyncio.sleep(0.5)  # Small delay to not trigger rate limits

    # Summary
    working = [k for k, v in results.items() if v.get("ok")]
    failed = [k for k, v in results.items() if not v.get("ok")]
    results["_summary"] = {
        "working_models": working,
        "failed_models": failed,
        "total_tested": len(models_to_test),
        "total_working": len(working),
        "total_failed": len(failed),
    }

    return results


@router.post("/test-google-quota-isolation")
async def test_google_quota_isolation(request: Request) -> Dict[str, Any]:
    """Exhaust one Google model's quota, then test if other models still work.

    This answers: "If I use up all 20 RPD of gemini-2.5-flash, can I still
    use gemini-3.1-flash-lite (500 RPD) and gemini-3.5-flash (20 RPD)?"

    Steps:
    1. Fire 25 calls to gemini-2.5-flash (limit is 20 RPD) — exhaust it
    2. Test gemini-3.1-flash-lite — does it still work?
    3. Test gemini-3.5-flash — does it still work?
    4. Report results
    """
    import httpx
    import asyncio

    body = await request.json()
    google_key = body.get("google_key", "")

    if not google_key:
        return {"error": "No google_key provided"}

    results: Dict[str, Any] = {}

    # ── Step 1: Exhaust gemini-2.5-flash (20 RPD limit) ──
    results["step1_exhaust_gemini_2_5_flash"] = {
        "model": "gemini-2.5-flash",
        "limit": "20 RPD",
        "calls_made": 0,
        "calls_succeeded": 0,
        "calls_failed": 0,
        "first_error": None,
    }

    for i in range(25):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={google_key}",
                    json={
                        "contents": [{"parts": [{"text": f"Reply with the number {i}"}]}],
                        "generationConfig": {"maxOutputTokens": 5},
                    },
                )
            results["step1_exhaust_gemini_2_5_flash"]["calls_made"] += 1
            if r.status_code == 200:
                results["step1_exhaust_gemini_2_5_flash"]["calls_succeeded"] += 1
            else:
                results["step1_exhaust_gemini_2_5_flash"]["calls_failed"] += 1
                if results["step1_exhaust_gemini_2_5_flash"]["first_error"] is None:
                    results["step1_exhaust_gemini_2_5_flash"]["first_error"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            results["step1_exhaust_gemini_2_5_flash"]["calls_made"] += 1
            results["step1_exhaust_gemini_2_5_flash"]["calls_failed"] += 1
            if results["step1_exhaust_gemini_2_5_flash"]["first_error"] is None:
                results["step1_exhaust_gemini_2_5_flash"]["first_error"] = str(exc)[:200]

        await asyncio.sleep(0.3)

    # ── Step 2: Test gemini-3.1-flash-lite AFTER exhausting 2.5-flash ──
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={google_key}",
                json={
                    "contents": [{"parts": [{"text": "Reply with: ok"}]}],
                    "generationConfig": {"maxOutputTokens": 10},
                },
            )
        if r.status_code == 200:
            content = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            results["step2_test_gemini_3_1_flash_lite"] = {"ok": True, "response": content[:30], "verdict": "QUOTA IS INDEPENDENT — this model still works after 2.5-flash was exhausted"}
        else:
            results["step2_test_gemini_3_1_flash_lite"] = {"ok": False, "status": r.status_code, "error": r.text[:200], "verdict": "QUOTA MAY BE SHARED — this model also failed"}
    except Exception as exc:
        results["step2_test_gemini_3_1_flash_lite"] = {"ok": False, "error": str(exc)[:200]}

    # ── Step 3: Test gemini-3.5-flash AFTER exhausting 2.5-flash ──
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={google_key}",
                json={
                    "contents": [{"parts": [{"text": "Reply with: ok"}]}],
                    "generationConfig": {"maxOutputTokens": 10},
                },
            )
        if r.status_code == 200:
            content = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            results["step3_test_gemini_3_5_flash"] = {"ok": True, "response": content[:30], "verdict": "QUOTA IS INDEPENDENT — this model still works after 2.5-flash was exhausted"}
        else:
            results["step3_test_gemini_3_5_flash"] = {"ok": False, "status": r.status_code, "error": r.text[:200], "verdict": "QUOTA MAY BE SHARED — this model also failed"}
    except Exception as exc:
        results["step3_test_gemini_3_5_flash"] = {"ok": False, "error": str(exc)[:200]}

    # ── Summary ──
    step1 = results["step1_exhaust_gemini_2_5_flash"]
    step2_ok = results.get("step2_test_gemini_3_1_flash_lite", {}).get("ok", False)
    step3_ok = results.get("step3_test_gemini_3_5_flash", {}).get("ok", False)

    if step2_ok or step3_ok:
        results["_conclusion"] = "QUOTA IS PER-MODEL (INDEPENDENT). You can exhaust one model and still use others."
    else:
        results["_conclusion"] = "QUOTA MAY BE SHARED across Google models. Exhausting one affects others."

    return results


@router.get("/test-connector-fetch")
async def test_connector_fetch(
    action: str = "get_invoice",
    invoice_id: str = "INV-2026-001",
) -> Dict[str, Any]:
    """Test if Node 3's connector fetch actually works.

    This simulates exactly what Node 3 does: call_custom_action with
    the tenant's company_id and the action name.
    """
    from app.api.deps import get_current_user
    from app.core.react_tools.custom_connector_client import (
        call_custom_action,
        has_action,
        has_any_connector,
        _list_connectors,
        _find_action,
    )

    # Get company_id from JWT
    from fastapi import Request as _Req
    # We need the user's company_id — use the settings approach
    from app.config import get_settings
    settings = get_settings()

    # Use the test tenant's company_id directly (hardcoded for testing)
    company_id = "6dc85e4f-ce81-45c0-a995-12b410cee2c7"

    results: Dict[str, Any] = {}

    # Step 1: List connectors
    connectors = _list_connectors(company_id)
    results["connectors_found"] = len(connectors)
    for c in connectors:
        results[f"connector_{c.get('name','?')}"] = {
            "base_url": c.get("base_url", ""),
            "auth_type": c.get("auth_type", ""),
            "actions": [a.get("name") for a in c.get("actions", [])],
        }

    # Step 2: Check if action exists
    results["has_get_invoice"] = await has_action(company_id, "get_invoice")
    results["has_any_connector"] = await has_any_connector(company_id)

    # Step 3: Actually call the connector — with detailed error capture
    params = {"id": invoice_id, "invoice_id": invoice_id}

    # Manual call to see exactly what happens
    connectors = _list_connectors(company_id)
    found = _find_action(connectors, action)
    if found:
        connector, act = found
        base_url = connector["base_url"].rstrip("/")
        path_template = act.get("path", "")
        # Substitute path params
        import re as _re2
        path = path_template
        for k, v in params.items():
            path = path.replace(f"{{{k}}}", str(v))
        url = f"{base_url}{path}"
        method = act.get("method", "GET").upper()
        auth_type = connector["auth_type"]
        auth_config = connector["auth_config"]

        results["debug_url"] = url
        results["debug_method"] = method
        results["debug_auth_type"] = auth_type
        results["debug_auth_config"] = auth_config
        results["debug_path_template"] = path_template
        results["debug_path_resolved"] = path

        # Build headers
        from app.core.react_tools.custom_connector_client import _build_auth_headers
        headers = _build_auth_headers(auth_type, auth_config)
        headers["Origin"] = "https://parwa.buzz"
        results["debug_headers"] = headers

        # Make the call
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers)
            results["debug_response_status"] = resp.status_code
            results["debug_response_body"] = resp.text[:500]
            if 200 <= resp.status_code < 300:
                results["call_result"] = resp.json()
                results["call_success"] = True
            else:
                results["call_result"] = None
                results["call_success"] = False
                results["debug_error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as exc:
            results["call_result"] = None
            results["call_success"] = False
            results["debug_error"] = str(exc)[:300]
    else:
        results["call_result"] = None
        results["call_success"] = False
        results["debug_error"] = "Action not found in any connector"

    return results


# ═══════════════════════════════════════════════════════════════════════
# REAL SUPABASE CRM — queries the tenant's real Supabase database
# This is NOT mock data. Real SQL queries against real Postgres.
# Delete these endpoints after testing is complete.
# ═══════════════════════════════════════════════════════════════════════

import os as _os
import json as _json

_SUPABASE_HOST = _os.environ.get("TEST_SUPABASE_HOST", "aws-1-ap-northeast-1.pooler.supabase.com")
_SUPABASE_PORT = int(_os.environ.get("TEST_SUPABASE_PORT", "6543"))
_SUPABASE_DB = _os.environ.get("TEST_SUPABASE_DB", "postgres")
_SUPABASE_USER = _os.environ.get("TEST_SUPABASE_USER", "postgres.fmpibdauppnzfisodkhp")
_SUPABASE_PASS = _os.environ.get("TEST_SUPABASE_PASS", "Durgamaa@754")
_SUPABASE_API_KEY = "parwa-supabase-crm-2026"  # simple API key for testing


def _verify_supabase_key(authorization: Optional[str]) -> None:
    """Verify the Supabase CRM API key."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if token != _SUPABASE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _supabase_query(sql: str, params: tuple = ()) -> list:
    """Execute a real SQL query against Supabase Postgres."""
    import psycopg2
    conn = psycopg2.connect(
        host=_SUPABASE_HOST, port=_SUPABASE_PORT, dbname=_SUPABASE_DB,
        user=_SUPABASE_USER, password=_SUPABASE_PASS,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [desc[0] for desc in cur.description] if cur.description else []
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def _supabase_execute(sql: str, params: tuple = ()) -> str:
    """Execute a real INSERT/UPDATE/DELETE against Supabase Postgres."""
    import psycopg2
    conn = psycopg2.connect(
        host=_SUPABASE_HOST, port=_SUPABASE_PORT, dbname=_SUPABASE_DB,
        user=_SUPABASE_USER, password=_SUPABASE_PASS,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.statusmessage
    cur.close()
    conn.close()
    return result


@router.get("/supabase-crm/invoices/{invoice_id}")
async def supabase_get_invoice(invoice_id: str, authorization: Optional[str] = Header(None)):
    """Real Supabase CRM: get invoice by ID from the real database."""
    _verify_supabase_key(authorization)
    rows = _supabase_query(
        "SELECT id, customer_id, customer_email, amount, currency, status, items, created_at FROM parwa_invoices WHERE id = %s",
        (invoice_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    row = rows[0]
    # Convert Decimal to float for JSON
    if row.get("amount"):
        row["amount"] = float(row["amount"])
    if row.get("items") and isinstance(row["items"], str):
        row["items"] = _json.loads(row["items"])
    return row


@router.get("/supabase-crm/orders/{order_id}")
async def supabase_get_order(order_id: str, authorization: Optional[str] = Header(None)):
    """Real Supabase CRM: get order by ID from the real database."""
    _verify_supabase_key(authorization)
    rows = _supabase_query(
        "SELECT id, customer_id, customer_email, order_name, total_price, currency, financial_status, fulfillment_status, line_items, created_at FROM parwa_orders WHERE id = %s",
        (order_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    row = rows[0]
    if row.get("total_price"):
        row["total_price"] = float(row["total_price"])
    if row.get("line_items") and isinstance(row["line_items"], str):
        row["line_items"] = _json.loads(row["line_items"])
    return row


@router.get("/supabase-crm/payments")
async def supabase_get_payments(authorization: Optional[str] = Header(None)):
    """Real Supabase CRM: get payment history from the real database."""
    _verify_supabase_key(authorization)
    rows = _supabase_query(
        "SELECT id, invoice_id, customer_id, amount, currency, status, method, created_at FROM parwa_payments ORDER BY created_at DESC"
    )
    for row in rows:
        if row.get("amount"):
            row["amount"] = float(row["amount"])
    total_succeeded = sum(r["amount"] for r in rows if r.get("status") == "succeeded")
    return {"payments": rows, "total_count": len(rows), "total_succeeded_amount": round(total_succeeded, 2)}


@router.post("/supabase-crm/refunds")
async def supabase_process_refund(request: Request, authorization: Optional[str] = Header(None)):
    """Real Supabase CRM: process a refund — INSERT into real database."""
    _verify_supabase_key(authorization)
    body = await request.json()
    import uuid as _uuid
    refund_id = f"REF-{_uuid.uuid4().hex[:10].upper()}"
    _supabase_execute(
        "INSERT INTO parwa_refunds (id, order_id, amount, reason, status) VALUES (%s, %s, %s, %s, 'processed')",
        (refund_id, body.get("order_id", ""), float(body.get("amount", 0)), body.get("reason", "Customer requested")),
    )
    return {
        "refund_id": refund_id,
        "order_id": body.get("order_id", ""),
        "amount": float(body.get("amount", 0)),
        "reason": body.get("reason", "Customer requested"),
        "status": "processed",
        "processed_at": "2026-07-11T18:00:00Z",
    }


@router.post("/test-groq-quota")
async def test_groq_quota(request: Request) -> Dict[str, Any]:
    """Fire 50 rapid calls to Groq llama-3.1-8b-instant to find the real RPM limit.

    Groq doesn't show rate limit headers, so we have to test by brute force.
    """
    import httpx
    import asyncio
    import time as _time

    body = await request.json()
    groq_key = body.get("groq_key", "")

    if not groq_key:
        return {"error": "No groq_key provided"}

    results: Dict[str, Any] = {
        "model": "llama-3.1-8b-instant",
        "calls_made": 0,
        "calls_succeeded": 0,
        "calls_failed": 0,
        "first_error": None,
        "first_error_call": None,
        "rate_limit_found": False,
        "max_rpm_before_limit": 0,
        "call_timeline": [],
    }

    start_time = _time.time()

    for i in range(50):
        call_start = _time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": f"Reply with: {i}"}],
                        "max_tokens": 5,
                    },
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                )
            elapsed = round(_time.time() - call_start, 2)
            results["calls_made"] += 1

            if r.status_code == 200:
                results["calls_succeeded"] += 1
                results["max_rpm_before_limit"] += 1
                results["call_timeline"].append({"call": i, "status": 200, "elapsed_ms": int(elapsed * 1000)})
            elif r.status_code == 429:
                results["calls_failed"] += 1
                results["rate_limit_found"] = True
                if results["first_error"] is None:
                    results["first_error"] = f"HTTP 429: {r.text[:300]}"
                    results["first_error_call"] = i
                    # Check headers for rate limit info
                    rate_headers = {}
                    for h in r.headers:
                        if "rate" in h.lower() or "limit" in h.lower() or "remaining" in h.lower() or "reset" in h.lower():
                            rate_headers[h] = r.headers[h]
                    results["rate_limit_headers"] = rate_headers
                results["call_timeline"].append({"call": i, "status": 429, "elapsed_ms": int(elapsed * 1000)})
            else:
                results["calls_failed"] += 1
                if results["first_error"] is None:
                    results["first_error"] = f"HTTP {r.status_code}: {r.text[:300]}"
                    results["first_error_call"] = i
                results["call_timeline"].append({"call": i, "status": r.status_code, "elapsed_ms": int(elapsed * 1000)})
        except Exception as exc:
            results["calls_made"] += 1
            results["calls_failed"] += 1
            if results["first_error"] is None:
                results["first_error"] = str(exc)[:200]
                results["first_error_call"] = i
            results["call_timeline"].append({"call": i, "status": "error", "elapsed_ms": 0})

        # NO delay — fire as fast as possible to find the real RPM limit

    total_time = round(_time.time() - start_time, 2)
    results["total_time_seconds"] = total_time
    results["actual_rpm_observed"] = round(results["calls_succeeded"] / total_time * 60) if total_time > 0 else 0
    results["conclusion"] = (
        f"Made {results['calls_succeeded']} successful calls in {total_time}s "
        f"before hitting rate limit at call #{results['first_error_call']}. "
        f"Observed rate: ~{results['actual_rpm_observed']} RPM."
        if results["rate_limit_found"]
        else f"Made {results['calls_succeeded']} successful calls in {total_time}s with NO rate limit hit. "
    )

    return results
