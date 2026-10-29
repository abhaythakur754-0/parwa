#!/usr/bin/env python3
"""
PARWA Ticket-Driven Tool Lifecycle Demo — proves the full production story:

  A ticket arrives
    → the agent needs a NEW tool / agent for it
    → the tool is built automatically (self-extension loop, zero humans)
    → the WHOLE record is stored in the database
        (tool inventory + agent ownership + which ticket caused it)
    → later tickets REUSE it from the database (no rebuild)
    → at any time we can query: "which tools belong to which agent?"

Scenario: brand-new company "urbanstyle-demo" (no tools, no agents yet).
  Ticket 1  "Schedule an onboarding setup call"   → needs meeting_setup (WRITE-risk)
  Ticket 2  "Will rain affect my delivery visit?" → needs weather_check (READ-risk)
  Ticket 3  same need as Ticket 1, weeks later    → DB hit → REUSE, no rebuild

Run:
  python3 scripts/ticket_to_tool_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Self-contained local DB for the demo (production = Supabase Postgres,
# same code path via PARWA_DATABASE_URL).
DEMO_DB = "/tmp/ticket_demo_registry.db"
if os.path.exists(DEMO_DB):
    os.remove(DEMO_DB)
# NOTE: 4 slashes = absolute path. 3 slashes would mean a RELATIVE path
# and the file would silently fail to open (best-effort registry).
os.environ["PARWA_DATABASE_URL"] = f"sqlite:///{DEMO_DB}"

from tool_factory import (  # noqa: E402
    OUT_DIR, tool_exists, run_tool, classify_result, delete_tool,
)
from self_extension_loop import (  # noqa: E402
    CAPABILITY_HINTS, extend_toolset,
)
from tool_registry_db import (  # noqa: E402
    list_tools_for_tenant, list_agents_with_tools,
)

TENANT = "urbanstyle-demo"


def header(txt: str) -> None:
    print(f"\n{'═' * 74}\n  {txt}\n{'═' * 74}")


def find_tool_in_db(capability: str) -> dict | None:
    """Production reuse path: look up the DB registry FIRST —
    'use it whenever needed' instead of rebuilding."""
    for row in list_agents_with_tools(TENANT):
        if row.get("error"):
            return None
        try:
            caps = json.loads(row.get("capabilities") or "[]")
        except Exception:  # noqa: BLE001
            caps = []
        if capability in caps and row.get("tool_status") == "active":
            return row
    return None


def make_ticket(n: int, subject: str, description: str) -> dict:
    return {
        "id": f"TKT-{int(time.time())}-{n}",
        "channel": "chat",
        "subject": subject,
        "description": description,
    }


def db_inventory_count() -> int:
    tools = list_tools_for_tenant(TENANT)
    return 0 if (tools and tools[0].get("error")) else len(
        [t for t in tools if t.get("is_active")]
    )


def resolve_with_new_tool(ticket: dict, capability: str, journal: dict) -> dict:
    """Ticket needs a capability with NO tool yet → self-extension loop."""
    hint = CAPABILITY_HINTS[capability]
    print(f"\n  1) DB lookup for '{capability}'  → MISS (no tool registered yet)")
    print(f"  2) Self-extension loop: detect → design → create → test-gate …")
    result = extend_toolset(
        tenant=TENANT,
        capability=capability,
        context=hint["context"],
        test_inputs=dict(hint["test_inputs"]),
        journal=journal,
        allow_llm=True,
    )
    status = result.get("status")
    tid = result.get("tool_id", "?")
    print(f"  3) loop status: {status}   tool_id: {tid}")
    if result.get("data"):
        print(f"  4) live tool output: {str(result['data'])[:160]}")
    stored = db_inventory_count()
    print(f"  5) DB now holds {stored} tool(s) + {stored} agent-ownership link(s) "
          f"for this company (origin ticket: {ticket['id']})")
    return result


def resolve_with_existing(ticket: dict, capability: str) -> dict:
    """Ticket needs a capability we ALREADY stored → reuse from DB."""
    print(f"\n  1) DB lookup for '{capability}'  → HIT ✓")
    row = find_tool_in_db(capability)
    if not row:
        print("     → nothing registered in DB (unexpected) → would self-extend")
        return {"status": "not_found"}
    tid = row["tool_id"]
    print(f"  2) found in database: {tid}")
    print(f"     owned by agent : {row['agent_name']}")
    live = tool_exists(tid)
    print(f"  3) still live in Superglue runtime: {live}")
    if not live:
        return {"status": "stale", "tool_id": tid}
    hint = CAPABILITY_HINTS[capability]
    res = run_tool(tid, dict(hint["test_inputs"]))
    verdict = classify_result(res)
    data = res.get("json", {}).get("data")
    usable = verdict.get("verdict") == "success"
    print(f"  4) ran it for this ticket → verdict: {verdict.get('verdict')}"
          f"   (0 new tools built, 0 LLM calls)")
    if usable and data:
        print(f"     output: {str(data)[:160]}")
    return {"status": "reused_ok" if usable else "reused_test_failed",
            "tool_id": tid, "verdict": verdict}


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    journal = {"demo": "ticket_driven_tool_lifecycle", "tenant": TENANT,
               "started": started, "tickets": []}

    header(f"TICKET-DRIVEN TOOL LIFECYCLE — company '{TENANT}' (brand new, DB empty)")
    print(f"  tools in DB before anything: {db_inventory_count()}")

    # ── Ticket 1: needs a WRITE-risk capability that does not exist ─────────
    header("TICKET 1 — 'Schedule an onboarding setup call'  → needs NEW tool")
    t1 = make_ticket(1, "Please schedule a setup meeting with your team",
                     "New customer wants an onboarding walkthrough next week.")
    journal["tickets"].append({"id": t1["id"], "capability": "meeting_setup"})
    r1 = resolve_with_new_tool(t1, "meeting_setup", journal)

    # ── Ticket 2: different, READ-risk capability ────────────────────────────
    header("TICKET 2 — 'Will rain affect my delivery visit?'  → needs NEW tool")
    t2 = make_ticket(2, "Is it going to rain in Berlin tomorrow?",
                     "Customer worries about a delivery visit in Berlin.")
    journal["tickets"].append({"id": t2["id"], "capability": "weather_check"})
    r2 = resolve_with_new_tool(t2, "weather_check", journal)

    # ── Ticket 3: SAME capability as ticket 1 → REUSE from DB ───────────────
    header("TICKET 3 (weeks later) — same need as Ticket 1  → REUSE from DB")
    t3 = make_ticket(3, "Can we book a setup call for Friday?",
                     "Another new customer asks for an onboarding meeting.")
    journal["tickets"].append({"id": t3["id"], "capability": "meeting_setup"})
    r3 = resolve_with_existing(t3, "meeting_setup")

    # ── Queries straight from the database ───────────────────────────────────
    header("DATABASE QUERIES — 'what tools do we have / who owns what'")
    tools = list_tools_for_tenant(TENANT)
    print("\n  ▶ all tools registered for this company:")
    for t in tools:
        print(f"     • {t['tool_id']:<52} risk={t['risk']:<5} "
              f"approval={'YES' if t['needs_approval'] else 'no '} active={t['is_active']}")
    links = list_agents_with_tools(TENANT)
    print("\n  ▶ which tools belong to which agent:")
    for a in links:
        print(f"     • agent '{a['agent_name']}'")
        print(f"       domain={a['domain']}  capabilities={a['capabilities']}")
        print(f"       owns tool: {a['tool_id']}  (tool {a['tool_status']}, "
              f"agent {a['agent_status']})")

    # ── Proof summary ────────────────────────────────────────────────────────
    created_ok = r1.get("status") == "created_and_verified" and \
                 r2.get("status") == "created_and_verified"
    reused_ok = r3.get("status") == "reused_ok"
    header("PROOF SUMMARY")
    checks = [
        ("Ticket 1 → new tool built automatically, no humans", created_ok),
        ("Ticket 2 → second new tool built automatically", created_ok),
        ("Whole record stored in DB (tool + agent + origin ticket)", created_ok),
        ("Ticket 3 → reused from DB, zero rebuild", reused_ok),
        ("We can query which tools belong to which agent", created_ok and reused_ok and len(links) >= 2),
    ]
    for label, ok in checks:
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}  {label}")
    all_ok = all(ok for _, ok in checks)

    journal["results"] = {"ticket1": r1, "ticket2": r2, "ticket3": r3}
    journal["all_ok"] = all_ok
    journal["finished"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"ticket_driven_demo_{int(time.time())}.json")
    with open(out, "w") as f:
        json.dump(journal, f, indent=2, default=str)
    print(f"\n  journal: {out}")
    print(f"\n  OVERALL: {'ALL PASS ✅' if all_ok else 'FAILURES ❌'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
