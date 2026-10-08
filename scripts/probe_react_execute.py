#!/usr/bin/env python3
"""Isolated probe of node_5._react_execute — why doesn't the agent-aware path fire?"""
import os, sys, json, asyncio, logging

os.environ["DATABASE_URL"] = "sqlite:////home/z/my-project/backend/parwa_probe.db"
os.environ["SUPERGLUE_API_URL"] = "http://127.0.0.1:3076/sgapi"
os.environ["SUPERGLUE_AUTH_TOKEN"] = "local-test-token-e2e"
os.environ["ENVIRONMENT"] = "development"
for k in ("GROQ_API_KEY", "MISTRAL_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, "/home/z/my-project/backend")
os.chdir("/home/z/my-project/backend")
_DB = "/home/z/my-project/backend/parwa_probe.db"
if os.path.exists(_DB):
    os.remove(_DB)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

import httpx

SHIM = "http://127.0.0.1:3077/v1/chat/completions"
async def shim(prompt="", max_tokens=256, temperature=0.3, system_prompt="", **kw):
    print(f"[probe] llm_call -> {str(prompt)[:80]!r}")
    messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
               [{"role": "user", "content": prompt}]
    async with httpx.AsyncClient(timeout=240) as c:
        r = await c.post(SHIM, json={"messages": messages, "max_tokens": max_tokens})
        return r.json().get("content", "")

import app.core.parwa_pipeline.nodes.node_5_act_verify as n5
import app.core.parwa_pipeline.llm_client as llm_mod
_real = llm_mod.llm_call
llm_mod.llm_call = shim
n5.llm_call = shim  # top-level binding in this module

from database.base import Base, engine, SessionLocal
from database.models import core as m_core, tickets as m_tk, variant_engine as m_var
WANT = {"companies", "customers", "tickets", "ai_agent_assignments", "superglue_call_queue",
        "ticket_tool_executions", "users", "channels", "integrations"}
Base.metadata.create_all(engine, tables=[t for t in Base.metadata.tables.values() if t.name in WANT])

TENANT, CUST, TICKET, AGENT = ("p0000000-0000-0000-0000-00000000000%d" % i for i in range(1, 5))
db = SessionLocal()
db.add(m_core.Company(id=TENANT, name="ProbeCo", industry="retail", subscription_tier="parwa"))
db.add(m_tk.Customer(id=CUST, company_id=TENANT, email="john@test.com", name="John"))
db.add(m_tk.Ticket(id=TICKET, company_id=TENANT, customer_id=CUST, channel="chat", status="open"))
db.add(m_var.AIAgentAssignment(
    id=AGENT, company_id=TENANT, agent_name="Refund Pro", agent_role="action", domain="Refunds",
    capabilities='["refund_processing"]', status="active", approval_required=False,
    approval_threshold_cents=100000, superglue_tool_id="payment-refund-by-email",
    superglue_tool_status="active"))
db.commit()

state = {"verified_agent_id": AGENT, "ticket_id": TICKET, "tenant_id": TENANT,
         "query": "I want a refund of $25 for my order 12345", "builder_agent_id": None}
logs = []
result = asyncio.run(asyncio.wait_for(
    n5._react_execute("execute_refund", {"amount": 25.0}, "kb", {}, tenant_id=TENANT,
                      state=state, logs=logs), timeout=300))

print("\n=== _react_execute RESULT ===")
print(json.dumps(result, indent=1, default=str)[:1500])
print("\n=== STATE AFTER (mutation visibility) ===")
print(json.dumps({k: v for k, v in state.items() if k.startswith("pending")}, indent=1, default=str))
print("\n=== logs ===")
for l in logs:
    print(" ·", str(l)[:200])
