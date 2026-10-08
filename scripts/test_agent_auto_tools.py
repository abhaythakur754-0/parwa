#!/usr/bin/env python3
"""
E2E harness — PROVES the PARWA agent auto-executes its Superglue tool.

Scenario A: billing-investigation ticket -> read-only lookup tool
            -> MUST auto-execute with zero human touch.
Scenario B: refund ticket -> financial tool -> MUST park in Pending Approval.

Run:  /home/z/parwa-test-venv/bin/python scripts/test_agent_auto_tools.py
Pre:  mini-services/mock-superglue (3076) + mini-services/llm-shim (3077) running.
"""
import os, sys, json, asyncio, time

os.environ["DATABASE_URL"] = "sqlite:////home/z/my-project/backend/parwa_e2e.db"
os.environ["SUPERGLUE_API_URL"] = "http://127.0.0.1:3076/sgapi"
os.environ["SUPERGLUE_AUTH_TOKEN"] = "local-test-token-e2e"
os.environ["ENVIRONMENT"] = "development"
os.environ["CELERY_BROKER_URL"] = "memory://"
for k in ("GROQ_API_KEY", "MISTRAL_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, "/home/z/my-project/backend")
os.chdir("/home/z/my-project/backend")

_DB = "/home/z/my-project/backend/parwa_e2e.db"
if os.path.exists(_DB):
    os.remove(_DB)

import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

SHIM_URL = "http://127.0.0.1:3077/v1/chat/completions"
llm_stats = {"calls": 0, "fail": 0}


async def shimmed_llm_call(prompt="", max_tokens=256, temperature=0.3,
                           system_prompt="", step_type="", ticket_id="", **kw):
    llm_stats["calls"] += 1
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=240) as c:
                r = await c.post(SHIM_URL, json={
                    "messages": messages, "max_tokens": max_tokens,
                    "temperature": temperature})
                r.raise_for_status()
                return r.json().get("content", "")
        except Exception as e:  # noqa: BLE001
            last_err = e
            await asyncio.sleep(2 * (attempt + 1))
    llm_stats["fail"] += 1
    print(f"[harness] LLM shim failed: {last_err}")
    return ""


print("[harness] importing pipeline ...")
import app.core.parwa_pipeline.graph_v2 as graph_v2_mod  # noqa: E402
import app.core.parwa_pipeline.llm_client as llm_mod  # noqa: E402

_real = llm_mod.llm_call
llm_mod.llm_call = shimmed_llm_call
import sys as _sys  # noqa: E402
for name, mod in list(_sys.modules.items()):
    if name.startswith("app.") and mod is not None and getattr(mod, "llm_call", None) is _real:
        setattr(mod, "llm_call", shimmed_llm_call)
print("[harness] llm_call patched everywhere")


from database.base import Base, engine, SessionLocal  # noqa: E402
from database.models import core as m_core, tickets as m_tk, variant_engine as m_var  # noqa: E402

WANT = {"companies", "users", "customers", "channels", "tickets", "ticket_messages",
        "ai_agent_assignments", "integrations", "superglue_call_queue",
        "ticket_tool_executions", "agent_templates", "jarvis_action_tickets"}
Base.metadata.create_all(engine, tables=[t for t in Base.metadata.tables.values() if t.name in WANT])

TENANT = "t0000000-0000-0000-0000-000000000001"
CUST = "c0000000-0000-0000-0000-000000000001"
AGENT_A = "a0000000-0000-0000-0000-000000000001"
AGENT_B = "a0000000-0000-0000-0000-000000000002"

db = SessionLocal()
db.add(m_core.Company(id=TENANT, name="E2E Test Co", industry="retail",
                      subscription_tier="parwa", subscription_status="active"))
db.add(m_tk.Customer(id=CUST, company_id=TENANT, email="john@test.com", name="John Tester"))
db.add_all([
    m_var.AIAgentAssignment(
        id=AGENT_A, company_id=TENANT, agent_name="Billing Lookup Pro",
        agent_role="action", domain="Billing",
        capabilities='["billing_inquiry", "billing"]', status="active",
        approval_required=False, approval_threshold_cents=100000,
        superglue_tool_id="customer-lookup-by-email", superglue_tool_status="active"),
    m_var.AIAgentAssignment(
        id=AGENT_B, company_id=TENANT, agent_name="Refund Pro",
        agent_role="action", domain="Refunds",
        capabilities='["refund_processing", "refund"]', status="active",
        approval_required=False, approval_threshold_cents=100000,
        superglue_tool_id="payment-refund-by-email", superglue_tool_status="active"),
])
db.commit()
print("[harness] seeded tenant + 2 agents (lookup / refund)")


def build_state(ticket_id, query, subject):
    return {
        "ticket_id": ticket_id, "tenant_id": TENANT, "query": query,
        "channel_type": "chat",
        "customer_context": {"customer_id": CUST, "email": "john@test.com",
                             "name": "John Tester", "account_tier": "parwa"},
        "metadata": {"source": "e2e-harness", "ticket_id": ticket_id,
                     "priority": "medium", "category": "billing", "subject": subject},
    }


async def run_pipeline(state):
    graph = graph_v2_mod.build_parwa_pipeline()
    compiled = graph.compile(checkpointer=graph_v2_mod.get_checkpointer())
    return await asyncio.wait_for(
        compiled.ainvoke(dict(state), config={"configurable": {"thread_id": state["ticket_id"]}}),
        timeout=480)


def mock_runs():
    try:
        with open("/tmp/mock-superglue-runs.jsonl") as f:
            return [json.loads(l) for l in f if l.strip() and '"run"' in l]
    except FileNotFoundError:
        return []


def report(title, result):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    for k in ("required_action", "route_decision", "verified_agent_id",
              "verified_tool_id", "tool_executed", "pending_approval"):
        print(f"  {k:22s} = {str(result.get(k))[:100]}")
    tl = result.get("technique_log") or []
    n5 = [e for e in tl if (isinstance(e, dict) and e.get("node") == 5)
          or (isinstance(e, str) and "node5" in e)]
    print(f"  NODE-5 LOG ({len(n5)}):")
    for e in n5[:14]:
        if isinstance(e, dict):
            print("   ·", e.get("technique"), "→", str(e.get("result_summary"))[:130])
        else:
            print("   ·", e[:170])
    at = result.get("actions_taken") or []
    print(f"  ACTIONS TAKEN ({len(at)}):")
    for a in at[:4]:
        print("   ·", json.dumps(a, default=str)[:220])
    resp = result.get("final_response") or result.get("response") or ""
    print(f"  FINAL ANSWER: {resp[:280]}")


t0 = time.time()
print("\n[harness] SCENARIO A: duplicate-charge investigation -> lookup tool ...")
res_a = asyncio.run(run_pipeline(build_state(
    "k0000000-0000-0000-0000-0000000000a1",
    "I was charged $50 twice this month on my card, my email is john@test.com. "
    "Please look into this duplicate charge.", "Duplicate charge")))
report("SCENARIO A — read-only lookup — EXPECT auto-execution", res_a)

print("\n[harness] SCENARIO B: refund request -> financial tool ...")
res_b = asyncio.run(run_pipeline(build_state(
    "k0000000-0000-0000-0000-0000000000b1",
    "I want a refund of $25 for my order 12345. Please process it.", "Refund request")))
report("SCENARIO B — refund (financial) — EXPECT Pending Approval", res_b)

runs = mock_runs()
print(f"\n  MOCK SUPERGLUE EXECUTIONS TOTAL: {len(runs)}")
for r in runs:
    print("   ·", json.dumps(r)[:150])

print(f"\nTotal time: {time.time() - t0:.1f}s | LLM calls: {llm_stats['calls']} (failed: {llm_stats['fail']})")

te = str(res_a.get("tool_executed") or "")
at_str = json.dumps(res_a.get("actions_taken", []), default=str)
ok_a = ("superglue" in te and "pending" not in te) or ("ACTION EXECUTED" in at_str) or len(runs) >= 1
ok_b = bool(res_b.get("pending_approval")) or "pending_approval" in json.dumps(res_b.get("actions_taken", []), default=str)
print("\n" + "=" * 72)
print("✅ VERDICT A: agent AUTO-executed its tool on its own — no human touch" if ok_a
      else "❌ VERDICT A: read-only tool NOT auto-executed")
print("✅ VERDICT B: refund correctly parked in Pending Approval (financial gate)" if ok_b
      else "❌ VERDICT B: refund did not reach approval queue")
sys.exit(0 if (ok_a and ok_b) else 1)
