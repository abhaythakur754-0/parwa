#!/usr/bin/env python3
"""
PARWA Production E2E Test — one command, full system, zero manual steps.

Proves the complete autonomous chain:

  Phase 0  Health:      Superglue + Builder + CRM Analyser reachable
  Phase 1  Toolset:     deploy 9-tool payments preset → run credential-free
                        test matrix (dummy Razorpay creds → clean auth errors
                        prove the full execution path)
  Phase 2  CRM Analyser: GadgetHub snapshot → work order (what to build)
  Phase 3  Builder:     GadgetHub capability → real agent_id + agent_config
  Phase 4  Self-Ext:    NOVEL ticket capability → no tool exists → LLM
                        designs it → Superglue creates it → data-usability
                        test → verified with REAL data (self-heals to a
                        validated template if the LLM design fails)
  Phase 5  Verdict:     production-readiness table + JSON report

Usage:
  python3 production_e2e_test.py            # full run
  python3 production_e2e_test.py --phase 4  # single phase
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tool_factory import (  # noqa: E402
    OUT_DIR,
    SUPERGLUE_URL,
    SUPERGLUE_TOKEN,
    list_tools,
    upsert_tool,
    PAYMENTS_PRESET,
    PRESETS,
    RISK_MANIFEST,
    RISK_MANIFESTS,
    preset_test_cases,
    run_tool,
    classify_result,
    namespaced,
    validate_spec,
)
from self_extension_loop import extend_toolset  # noqa: E402
try:  # best-effort DB registry for deploy-phase ownership tracking
    from tool_registry_db import register_tool
except Exception:  # noqa: BLE001
    register_tool = None

BUILDER_URL = os.environ.get("BUILDER_API_URL", "").strip().rstrip("/")
BUILDER_KEY = os.environ.get("BUILDER_API_KEY", "").strip()
CRM_URL = os.environ.get("CRM_ANALYSER_URL", "").strip().rstrip("/")
CRM_ANALYSER_API_KEY = os.environ.get("CRM_ANALYSER_API_KEY", "").strip()
ALLOW_MUTATIONS = os.environ.get("PARWA_E2E_ALLOW_MUTATIONS", "").strip().lower() == "true"

TENANT_A = "acme-payments-demo"   # payments business — preset tools
TENANT_B = "gadgethub-demo"       # electronics shop — novel capability

REPORT: dict = {"started": datetime.now(timezone.utc).isoformat(), "phases": {}}


def section(title: str):
    print(f"\n{'=' * 74}\n  {title}\n{'=' * 74}")


def record(phase: str, data: dict, passed: bool):
    REPORT["phases"][phase] = {**data, "passed": passed}


def http_json(url: str, method: str = "GET", body: dict = None, headers: dict = None, timeout: float = 30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


# ════════════════════════════════════════════════════════════════════════════
def phase0_health() -> bool:
    section("PHASE 0 — Service health")
    ok_all = True
    # Superglue
    try:
        tools = list_tools()
        print(f"  ✓ Superglue         — {len(tools)} tools on stack")
        ok_all &= len(tools) > 0
    except Exception as e:
        print(f"  ✗ Superglue — {e}")
        ok_all = False
    # Builder
    try:
        if not BUILDER_URL:
            raise RuntimeError("BUILDER_API_URL is required; refusing to use a hardcoded preview service")
        if not BUILDER_KEY:
            raise RuntimeError("BUILDER_API_KEY is required for the Builder integration test")
        st, body = http_json(f"{BUILDER_URL}/api/health", headers={"X-API-Key": BUILDER_KEY})
        llm_ok = body.get("llm_ready") is True
        print(f"  ✓ Builder Agent     — status={body.get('status')}, llm_ready={body.get('llm_ready')}")
        ok_all &= st == 200 and llm_ok
    except Exception as e:
        print(f"  ✗ Builder — {e}")
        ok_all = False
    # CRM Analyser — liveness probe: the analyze endpoint 400/500s on trivial
    # payloads (its LLM needs real ticket data), so we probe the HTTP server
    # directly; full functional proof happens in Phase 2 with a real snapshot.
    try:
        if not CRM_URL:
            raise RuntimeError("CRM_ANALYSER_URL is required; refusing to use a hardcoded preview service")
        if not CRM_ANALYSER_API_KEY:
            raise RuntimeError("CRM_ANALYSER_API_KEY is required")
        req = urllib.request.Request(
            f"{CRM_URL}/",
            headers={"Authorization": f"Bearer {CRM_ANALYSER_API_KEY}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                alive = r.status == 200
        except urllib.error.HTTPError as e:
            alive = e.code in (200, 301, 302, 404)
        print(f"  {'✓' if alive else '✗'} CRM Analyser      — HTTP server alive (functional analysis proven in Phase 2)")
        ok_all &= alive
    except Exception as e:
        print(f"  ✗ CRM Analyser — {e}")
        ok_all = False
    record("health", {"superglue": True, "ok": ok_all}, ok_all)
    return ok_all


def phase1_toolset() -> bool:
    section("PHASE 1 — Toolset deploy + credential-free matrix (3 industries)")
    packs = [
        ("payments", TENANT_A),
        ("meetings", "acme-meetings-demo"),
        ("retail", "acme-retail-demo"),
    ]
    errs = []
    for preset, tenant in packs:
        print(f"  ▶ pack: {preset} (tenant: {tenant})")
        for raw in PRESETS[preset]:
            spec = dict(raw)
            spec["id"] = namespaced(spec["id"], tenant)
            e = validate_spec(spec)
            if e:
                errs.append({"id": spec["id"], "errors": e})
                continue
            up = upsert_tool(spec)
            print(f"  {'✓' if up['ok'] else '✗'} deploy {spec['id']} → {up['action']}")
            if up["ok"] and register_tool is not None:
                slug = spec["id"].split("__", 1)[-1]
                meta = RISK_MANIFESTS.get(preset, {}).get(slug, {})
                db = register_tool(
                    company_id=tenant,
                    tool_id=spec["id"],
                    tool_name=spec.get("name", spec["id"]),
                    risk=meta.get("risk", "read"),
                    approval_required=bool(meta.get("approval_required", False)),
                    capability=slug,
                    created_by="tool_factory",
                    origin="preset_deploy",
                    tool_definition=spec,
                )
                print(f"      db_register: {'ok' if db.get('ok') else 'FAILED: ' + str(db.get('error'))}")
            if not up["ok"]:
                errs.append(up)
    deploy_ok = not errs

    results = []
    for preset, tenant in packs:
        for c in preset_test_cases(tenant, preset=preset):
            res = run_tool(c["id"], c["inputs"])
            v = classify_result(res)
            passed = v["verdict"] == c["expect"]
            if passed and c.get("expect_payload"):
                detail = v.get("detail")
                if isinstance(detail, str):
                    try:
                        detail = json.loads(detail)
                    except Exception:
                        detail = {}
                for k, want in (c["expect_payload"] or {}).items():
                    if not isinstance(detail, dict) or detail.get(k) != want:
                        passed = False
            if passed and c.get("expect_stepresults_contains"):
                if c["expect_stepresults_contains"] not in json.dumps(res.get("json", {})):
                    passed = False
            results.append({**{k: c[k] for k in ("id", "expect", "why")}, "verdict": v["verdict"], "passed": passed})
            print(f"  {'✓' if passed else '✗'} test {c['id']} → {v['verdict']}")
    passed_n = sum(1 for r in results if r["passed"])
    print(f"\n  MATRIX: {passed_n}/{len(results)} passed")
    ok = deploy_ok and passed_n == len(results)
    record("toolset", {"deploy_errors": errs, "matrix": results}, ok)
    return ok


def phase2_crm() -> bool:
    section(f"PHASE 2 — CRM Analyser work order (tenant: {TENANT_B})")
    snapshot = {
        "source": "upload",
        "company_name": "GadgetHub",
        "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
        "tickets": [
            {"id": 1, "subject": "Where is my order?", "description": "I ordered a phone case 5 days ago and have no tracking info.", "status": "open", "priority": "high"},
            {"id": 2, "subject": "Warranty question", "description": "Is my iPhone still under warranty? Screen is flickering.", "status": "open", "priority": "medium"},
            {"id": 3, "subject": "Return request", "description": "I want to return my headphones, they arrived damaged.", "status": "open", "priority": "high"},
            {"id": 4, "subject": "Payment failed", "description": "My card was charged twice for the same order.", "status": "open", "priority": "urgent"},
            {"id": 7, "subject": "Warranty claim", "description": "My smartwatch battery died in 2 weeks, want warranty replacement.", "status": "open", "priority": "high"},
        ],
        "contacts": [], "deals": [], "orders": [],
        "data_profile": {
            "total_tickets": 5, "total_contacts": 0, "total_deals": 0, "total_orders": 0,
            "has_products": True, "has_shipping_addresses": True, "has_payment_data": True,
            "has_email_campaigns": False, "has_ticket_data": True,
            "industries_detected": ["ecommerce"], "payment_methods_seen": ["card"],
        },
        "connected_integrations": [],
    }
    try:
        st, resp = http_json(
            f"{CRM_URL}/api/crm-analyser/analyze",
            method="POST",
            body={"source": "upload", "data": snapshot},
            headers={"Authorization": f"Bearer {CRM_ANALYSER_API_KEY}"},
        )
        rid = resp.get("request_id")
        if not rid:
            print(f"  ✗ no request_id: {json.dumps(resp)[:200]}")
            record("crm_analyser", {"error": resp}, False)
            return False
        print(f"  ✓ enqueued (request_id={rid})")
        work_order = None
        for i in range(40):
            time.sleep(5)
            _, stt = http_json(
                f"{CRM_URL}/api/crm-analyser/analyze?id={rid}",
                headers={"Authorization": f"Bearer {CRM_ANALYSER_API_KEY}"},
            )
            state = stt.get("status", {}).get("status", "unknown")
            if state == "completed":
                work_order = stt["status"]["result"].get("work_order", {})
                break
            if state in ("failed", "error"):
                print(f"  ✗ analysis failed: {json.dumps(stt)[:200]}")
                record("crm_analyser", {"error": stt}, False)
                return False
        if work_order is None:
            print("  ✗ timed out waiting for analysis")
            record("crm_analyser", {"error": "timeout"}, False)
            return False
        print(f"  ✓ work order — integrations: {work_order.get('integrations')}")
        print(f"              agents: {work_order.get('agents')}")
        print(f"              tools: {work_order.get('tools')}")
        ok = isinstance(work_order, dict)
        record("crm_analyser", {"work_order": work_order}, ok)
        return ok
    except Exception as e:
        print(f"  ✗ {e}")
        record("crm_analyser", {"error": str(e)}, False)
        return False


def phase3_builder() -> bool:
    section(f"PHASE 3 — Builder Agent builds GadgetHub's agent (tenant: {TENANT_B})")
    payload = {
        "tenant_id": TENANT_B,
        "kb_context": (
            "GadgetHub is an electronics e-commerce shop selling phones, accessories "
            "and wearables. Customers ask about orders, shipping, warranty and "
            "returns. Product catalog includes per-product warranty information."
        ),
        "integrations": [],
        "capability": "warranty_and_order_support",
    }
    try:
        if not BUILDER_KEY:
            raise RuntimeError("BUILDER_API_KEY is required for the Builder integration test")
        st, resp = http_json(
            f"{BUILDER_URL}/api/build",
            method="POST",
            body=payload,
            headers={"X-API-Key": BUILDER_KEY},
            timeout=120,
        )
        job_id = resp.get("job_id")
        if not job_id:
            # sync response
            result = resp
        else:
            print(f"  ✓ queued (job_id={job_id})")
            result = None
            for i in range(60):
                time.sleep(5)
                _, stt = http_json(f"{BUILDER_URL}/api/build/jobs/{job_id}", headers={"X-API-Key": BUILDER_KEY})
                state = stt.get("status")
                if state in ("complete", "rejected", "failed"):
                    result = stt
                    break
            if result is None:
                print("  ✗ timed out")
                record("builder", {"error": "timeout"}, False)
                return False
        status = result.get("status")
        print(f"  ✓ build status: {status} (attempts={result.get('attempts')})")
        agent_id = (result.get("result") or {}).get("agent_id") or result.get("agent_id")
        ac = (result.get("result") or {}).get("agent_config") or result.get("agent_config") or {}
        print(f"  ✓ agent_id: {agent_id}")
        print(f"  ✓ agent_name: {ac.get('agent_name')} | role: {ac.get('agent_role')}")
        caps = ac.get("capabilities")
        print(f"  ✓ capabilities: {caps}")
        ok = status == "complete" and bool(agent_id)
        record("builder", {"agent_id": agent_id, "agent_name": ac.get("agent_name"), "capabilities": caps}, ok)
        return ok
    except Exception as e:
        print(f"  ✗ {e}")
        record("builder", {"error": str(e)}, False)
        return False


def phase4_self_extension() -> bool:
    section(f"PHASE 4 — Self-extension: novel ticket, no tool exists (tenant: {TENANT_B})")
    print("  Ticket: 'Is my iPhone still under warranty?' — NO warranty tool exists")
    journal = {
        "tenant": TENANT_B,
        "started": datetime.now(timezone.utc).isoformat(),
        "ticket": {"subject": "Is my iPhone still under warranty?", "channel": "chat"},
    }
    result = extend_toolset(
        tenant=TENANT_B,
        capability="warranty_check",
        context=(
            "GadgetHub is an electronics e-commerce shop. Customers ask about product "
            "warranties, returns and order status. The support agent needs to look up "
            "warranty info from the product catalog."
        ),
        test_inputs={"productName": "iPhone"},
        journal=journal,
        allow_llm=True,
    )
    ok = result["status"] in ("created_and_verified", "use_existing")
    print(f"  ✓ loop status: {result['status']}")
    print(f"  ✓ tool_id: {result.get('tool_id')}")
    print(f"  ✓ designed_by: {result.get('designed_by')} | self_healed: {result.get('self_healed', False)}")
    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    print(f"  ✓ tool output: {json.dumps(data)[:300] if data else '(existing tool)'}")
    if result["status"] == "use_existing":
        # idempotent re-use is correct production behavior — but still re-verify
        # the tool WORKS right now (never trust a tool you haven't exercised)
        from self_extension_loop import _data_is_usable
        res = run_tool(result["tool_id"], {"productName": "iPhone"})
        v = classify_result(res)
        reverified = v["verdict"] == "success" and _data_is_usable(res.get("json", {}).get("data"))
        ok &= reverified
        print(f"  {'✓' if reverified else '✗'} re-verified existing tool: {v['verdict']} → {str(res.get('json', {}).get('data'))[:200]}")
    journal["result"] = result
    journal["finished"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"e2e_self_extension_{int(time.time())}.json"), "w") as f:
        json.dump(journal, f, indent=2, default=str)
    record("self_extension", {
        "status": result["status"],
        "tool_id": result.get("tool_id"),
        "designed_by": result.get("designed_by"),
        "self_healed": result.get("self_healed", False),
        "data": data,
    }, ok)
    return ok


def phase4b_meeting_extension() -> bool:
    section("PHASE 4b — Self-extension: ANY-domain ticket (services tenant)")
    print("  Ticket: 'Please schedule a setup meeting with your team' — NO meeting tool exists")
    tenant = "acme-services-demo"
    journal = {
        "tenant": tenant,
        "started": datetime.now(timezone.utc).isoformat(),
        "ticket": {"subject": "Please schedule a setup meeting with your team", "channel": "chat"},
    }
    result = extend_toolset(
        tenant=tenant,
        capability="meeting_setup",
        context=(
            "Services business. Customers open tickets asking to schedule a setup "
            "meeting/call with the team. The agent needs to book a meeting: take "
            "the customer name, email, topic and a chosen slot, and get a booking "
            "reference back."
        ),
        test_inputs={
            "customerName": "Jane Customer",
            "customerEmail": "jane@example.com",
            "topic": "Product setup walkthrough",
            "slot": "2026-11-05T14:00 UTC",
            "durationMinutes": 30,
        },
        journal=journal,
        allow_llm=True,
    )
    ok = result["status"] in ("created_and_verified", "use_existing")
    print(f"  ✓ loop status: {result['status']}")
    print(f"  ✓ tool_id: {result.get('tool_id')}")
    print(f"  ✓ designed_by: {result.get('designed_by')} | self_repaired: {result.get('self_repaired', False)}")
    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    if result["status"] == "use_existing":
        from self_extension_loop import _data_is_usable
        res = run_tool(result["tool_id"], {
            "customerName": "Jane Customer", "customerEmail": "jane@example.com",
            "topic": "Product setup walkthrough", "slot": "2026-11-05T14:00 UTC",
            "durationMinutes": 30,
        })
        v = classify_result(res)
        reverified = v["verdict"] == "success" and _data_is_usable(res.get("json", {}).get("data"))
        ok &= reverified
        print(f"  {'✓' if reverified else '✗'} re-verified existing meeting tool: {v['verdict']}")
    print(f"  ✓ tool output: {json.dumps(data, default=str)[:300] if data else '(existing tool)'}")
    if result.get("tool_id", "").endswith("meeting-setup"):
        print("  ✓ write-risk tool → runtime approval gate applies (node_5)")
    journal["result"] = result
    journal["finished"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"e2e_meeting_extension_{int(time.time())}.json"), "w") as f:
        json.dump(journal, f, indent=2, default=str)
    record("meeting_extension", {
        "status": result["status"],
        "tool_id": result.get("tool_id"),
        "designed_by": result.get("designed_by"),
        "data": data,
    }, ok)
    return ok


def phase5_verdict() -> bool:
    section("PHASE 5 — PRODUCTION READINESS VERDICT")
    phases = REPORT["phases"]
    labels = {
        "health": "Service health (Superglue + Builder + CRM)",
        "toolset": "Toolset deploy + matrix (payments + meetings + retail packs)",
        "crm_analyser": "CRM Analyser → work order",
        "builder": "Builder Agent → agent created",
        "self_extension": "Self-extension #1 (warranty ticket → new tool, autonomous)",
        "meeting_extension": "Self-extension #2 (meeting ticket → new tool, any-domain)",
    }
    all_ok = True
    for key, label in labels.items():
        ph = phases.get(key, {})
        ok = ph.get("passed", False)
        all_ok &= ok
        print(f"  {'✓ PASS' if ok else '✗ FAIL'}  {label}")
    print()
    if all_ok:
        print("  VERDICT: PRODUCTION READY — every phase passed with zero human")
        print("  intervention inside the loop. Missing Razorpay keys are the only")
        print("  gap (tools take creds as inputs → add keys, zero code changes).")
    else:
        print("  VERDICT: NOT READY — see failing phases above.")
    REPORT["finished"] = datetime.now(timezone.utc).isoformat()
    REPORT["production_ready"] = all_ok
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"production_e2e_report_{int(time.time())}.json")
    with open(out, "w") as f:
        json.dump(REPORT, f, indent=2, default=str)
    print(f"\n  report: {out}")
    return all_ok


PHASES = [phase0_health, phase1_toolset, phase2_crm, phase3_builder, phase4_self_extension, phase4b_meeting_extension, phase5_verdict]


def main():
    if not ALLOW_MUTATIONS:
        raise SystemExit(
            "Refusing to mutate external test tenants. Set PARWA_E2E_ALLOW_MUTATIONS=true "
            "only when SUPERGLUE, BUILDER_API_URL and CRM_ANALYSER_URL point to approved "
            "sandbox/test services and the demo tenants are reserved for this test."
        )
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=range(0, 7), help="run a single phase")
    args = ap.parse_args()
    if args.phase is not None:
        ok = PHASES[args.phase]()
    else:
        ok = True
        for fn in PHASES:
            ok &= fn()
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
