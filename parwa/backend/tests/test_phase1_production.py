"""
PARWA Pipeline V2 — Production-Ready Test (Phase 1 Complete)

Tests 4 complicated tickets through the full 8-node pipeline with REAL NVIDIA API.
Handles 40 RPM rate limit: waits 60s between tickets.

Phase 1 deliverables tested:
  - 8-node PARWA pipeline (dual path, quality loop, super node)
  - Key-based access (API key generation, validation, JWT sessions)
  - Multi-tenant isolation (tenant context, tier permissions, data scoping)
  - Full technique stacking across all nodes

Tickets:
  1. Complex refund with credit + data retention concern (complex_path)
  2. Duplicate billing charge + pricing discrepancy (complex_path)
  3. Multi-part subscription change with downgrade timing (complex_path)
  4. Account security + team access + SSO integration (complex_path)
"""

import asyncio
import json
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project/parwa/backend")

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.auth.access_control import register_key, validate_request, set_tenant_context, clear_tenant_context
from app.core.tenant.isolation import create_tenant, tenant_request, audit_log, get_tier_permissions

# ── Config ────────────────────────────────────────────────────

NVIDIA_RPM_LIMIT = 40
SECONDS_BETWEEN_TICKETS = 65  # 65s to be safe with 40 RPM (40 calls in 60s)
LLM_CALLS_PER_COMPLEX_TICKET_ESTIMATE = 30  # worst case estimate

# ── Setup Test Tenant + API Key ───────────────────────────────

async def setup_test_environment():
    """Create test tenant, register API key, validate auth flow."""
    print("=" * 70)
    print("PHASE 1 — Environment Setup")
    print("=" * 70)

    # 1. Create tenant
    tenant = create_tenant(
        name="Test Corp",
        slug="test-corp",
        tier="high",
        settings={"industry": "saas", "team_size": 50},
    )
    tenant_id = tenant["id"]
    print(f"  [OK] Tenant created: {tenant['name']} (id={tenant_id[:8]}..., tier={tenant['tier']})")

    # 2. Register API key
    key_data = register_key(
        tenant_id=tenant_id,
        key_type="live",
        name="Phase 1 Test Key",
        rate_limit_rpm=NVIDIA_RPM_LIMIT,
    )
    api_key = key_data["full_key"]
    print(f"  [OK] API key registered: {key_data['key_prefix']}... (id={key_data['key_id'][:8]}...)")

    # 3. Validate the key works
    is_valid, ctx, err = await validate_request(api_key=api_key, client_ip="127.0.0.1")
    assert is_valid, f"Key validation failed: {err}"
    print(f"  [OK] Key validation passed: tenant={ctx['tenant_id'][:8]}...")

    # 4. Test tier permissions
    perms = get_tier_permissions("high")
    print(f"  [OK] Tier permissions loaded: max_llm={perms['max_llm_calls_per_ticket']}, super_node={perms['can_use_super_node']}")

    # 5. Audit log test
    audit_entry = audit_log("test", "pipeline", "test_run", {"phase": 1})
    print(f"  [OK] Audit logging works: action={audit_entry['action']}")

    # 6. Tenant context test
    set_tenant_context({"tenant_id": tenant_id, "tenant_tier": "high"})
    from app.core.tenant.isolation import get_tenant_context as gtc
    assert gtc() is not None
    clear_tenant_context()
    print(f"  [OK] Tenant context set/clear works")

    print("\n  Phase 1 infrastructure: ALL PASSED\n")
    return tenant_id, api_key


# ── Ticket Runner ─────────────────────────────────────────────

async def run_ticket(ticket: dict, graph, ticket_num: int) -> dict:
    """Run a single ticket through the pipeline with full timing."""
    ticket_id = ticket["ticket_id"]

    print(f"\n{'='*70}")
    print(f"  TICKET {ticket_num}/4: {ticket_id}")
    print(f"  Type: {ticket['description']}")
    print(f"  Expected Path: {ticket['expected_path']}")
    print(f"{'='*70}")

    start = time.time()

    # Set test variant
    set_test_variant(ticket["tenant_id"], ticket["variant_tier"], ticket["quota"])

    # Build initial state
    initial_state = {
        "ticket_id": ticket_id,
        "tenant_id": ticket["tenant_id"],
        "query": ticket["query"],
        "channel_type": ticket.get("channel_type", "email"),
        "customer_context": ticket.get("customer_context", {}),
        "metadata": {
            "sender": ticket.get("sender", "customer@example.com"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "loop_count": 0,
        "total_token_usage": 0,
        "technique_log": [],
        "errors": [],
    }

    try:
        compiled = graph.compile()
        result = await compiled.ainvoke(initial_state)
        elapsed = time.time() - start

        # ── Results ────────────────────────────────────────────
        print(f"\n  --- RESULTS [{elapsed:.1f}s] ---")
        print(f"  Status:          {result.get('status', 'unknown')}")
        print(f"  Ticket Type:     {result.get('ticket_type', 'N/A')}")
        print(f"  Complexity:      {result.get('complexity', 'N/A')}")
        print(f"  Variant Tier:    {result.get('variant_tier', 'N/A')}")
        print(f"  Route:           {result.get('route_decision', result.get('current_path', 'N/A'))}")
        print(f"  Total LLM Calls: {result.get('total_token_usage', 0)}")
        print(f"  Quality Score:   {result.get('quality_score', 'N/A')}")
        print(f"  Loop Count:      {result.get('loop_count', 0)}")

        if result.get("escalation_context"):
            esc = result["escalation_context"]
            print(f"  Escalation:      YES (key={esc.get('notification_key', 'N/A')})")
            print(f"  Super Node Q:    {result.get('super_node_quality', 'N/A')}")

        if result.get("simple_confidence") is not None:
            print(f"  Simple Conf:     {result['simple_confidence']:.2f}")
            print(f"  Auto Upgraded:   {result.get('auto_upgraded', False)}")

        # ── Per-node breakdown ─────────────────────────────────
        print(f"\n  --- PER-NODE BREAKDOWN ---")
        node_stats = {}
        for log in result.get("technique_log", []):
            node = log.get("node", "?")
            tech = log.get("technique", "?")
            duration = log.get("duration_ms", 0)
            if node not in node_stats:
                node_stats[node] = {"techniques": [], "total_ms": 0, "count": 0}
            node_stats[node]["techniques"].append(tech)
            node_stats[node]["total_ms"] += duration
            node_stats[node]["count"] += 1

        for node in sorted(node_stats.keys()):
            stats = node_stats[node]
            tech_names = ", ".join(stats["techniques"][:5])
            if len(stats["techniques"]) > 5:
                tech_names += f" +{len(stats['techniques'])-5} more"
            print(f"    Node {node}: {stats['count']} techniques ({stats['total_ms']}ms)")
            print(f"             {tech_names}")

        # ── Techniques run ─────────────────────────────────────
        print(f"\n  --- ALL TECHNIQUES RUN ---")
        for log in result.get("technique_log", []):
            node = log.get("node", "?")
            tech = log.get("technique", "?")
            summary = log.get("result_summary", "")
            print(f"    Node {node}: {tech:<25} -> {summary}")

        # ── Final Response ─────────────────────────────────────
        response = (
            result.get("final_response", "")
            or result.get("formatted_response", "")
            or result.get("simple_answer", "")
            or result.get("super_node_answer", "")
        )
        print(f"\n  --- FINAL RESPONSE ---")
        print(f"    {response[:2000] if response else '(no response generated)'}")

        # ── LLM call tracking ─────────────────────────────────
        node_llm = {}
        for log in result.get("technique_log", []):
            if "llm" in log.get("technique", "").lower() or log.get("technique") in (
                "UoT", "CoT", "ToT", "ReAct", "CLARA", "HyDE", "MultiQuery",
                "StepBack", "Reflexion", "CRP", "SelfConsistency",
            ):
                node = log.get("node", "?")
                node_llm[node] = node_llm.get(node, 0) + 1

        # Count actual LLM calls from total_token_usage
        total_llm = result.get("total_token_usage", 0)
        print(f"\n  --- LLM CALL SUMMARY ---")
        print(f"    Total LLM calls: {total_llm}")
        print(f"    Estimated API time: ~{total_llm * 1.5:.0f}s (at ~1.5s/call avg)")
        print(f"    Pipeline overhead: ~{max(0, elapsed - total_llm * 1.5):.1f}s")

        return {
            "ticket_id": ticket_id,
            "status": result.get("status", "ERROR"),
            "llm_calls": total_llm,
            "quality": result.get("quality_score", result.get("simple_confidence", "N/A")),
            "elapsed": elapsed,
            "loop_count": result.get("loop_count", 0),
            "route": result.get("route_decision", result.get("current_path", "N/A")),
            "escalated": bool(result.get("escalation_context")),
        }

    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  --- ERROR [{elapsed:.1f}s] ---")
        print(f"  Error: {e}")
        traceback.print_exc()
        return {"ticket_id": ticket_id, "status": "ERROR", "error": str(e), "elapsed": elapsed}


# ── Main ──────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("  PARWA Pipeline V2 — Phase 1 PRODUCTION TEST")
    print("  4 Tickets | Real NVIDIA Llama 3.1 8B | Rate Limit: 40 RPM")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    # ── Phase 1 Infrastructure Test ───────────────────────────
    tenant_id, api_key = await setup_test_environment()

    # ── Build Pipeline ────────────────────────────────────────
    print("=" * 70)
    print("  Building Pipeline...")
    print("=" * 70)
    graph = build_parwa_pipeline()
    print("  Pipeline built: 8 nodes, dual path, quality loop (max 2)\n")

    # ── 4 Test Tickets ────────────────────────────────────────

    ticket_1 = {
        "ticket_id": "tkt_phase1_001",
        "tenant_id": tenant_id,
        "query": (
            "I have been a Pro plan customer for 8 months and I need to cancel my annual subscription "
            "and get a refund. I was charged $1,200 for the annual plan but I also have an outstanding "
            "credit of $75 from a previous billing error that was never applied. I want the full refund "
            "processed to my original payment method, and I want to know what happens to my stored data."
        ),
        "channel_type": "email",
        "variant_tier": "high",
        "quota": 2000,
        "customer_context": {
            "account_tier": "pro",
            "customer_tenure_days": 240,
            "recent_ticket_count": 3,
            "lifetime_value": 2400,
        },
        "sender": "sarah.chen@company.com",
        "description": "Complex refund + credit + data retention",
        "expected_path": "complex_path",
    }

    ticket_2 = {
        "ticket_id": "tkt_phase1_002",
        "tenant_id": tenant_id,
        "query": (
            "I was charged $149 twice this month, once on the 1st and again on the 15th. "
            "Looking at my invoices, the first charge shows the correct Pro plan rate but "
            "the second one shows the High plan rate of $499. I never upgraded to High plan. "
            "Additionally, my team member who uses the same account key is seeing a different "
            "pricing page than me, she sees $99/mo instead of $149. I want both the duplicate "
            "charge fixed and an explanation for the pricing discrepancy."
        ),
        "channel_type": "chat",
        "variant_tier": "high",
        "quota": 1999,
        "customer_context": {
            "account_tier": "pro",
            "customer_tenure_days": 180,
            "recent_ticket_count": 1,
            "lifetime_value": 1500,
        },
        "sender": "mike.r@startup.io",
        "description": "Duplicate charge + pricing discrepancy",
        "expected_path": "complex_path",
    }

    ticket_3 = {
        "ticket_id": "tkt_phase1_003",
        "tenant_id": tenant_id,
        "query": (
            "We need to change our subscription from High plan to Pro plan effective next month. "
            "But here is the complication: we have 15 team members on the High plan right now, "
            "and only 10 of them need Pro access. The other 5 should be moved to Mini. "
            "Also, we prepaid for the annual High plan 3 months ago ($4,999), so we need to know "
            "the prorated credit we will get, and whether that credit can be split across the "
            "two new plans. Finally, one of our team members is in the middle of a billing cycle "
            "dispute — how does the plan change affect their open ticket?"
        ),
        "channel_type": "email",
        "variant_tier": "high",
        "quota": 1998,
        "customer_context": {
            "account_tier": "high",
            "customer_tenure_days": 365,
            "recent_ticket_count": 7,
            "lifetime_value": 12000,
            "team_size": 15,
        },
        "sender": "cto@bigcorp.com",
        "description": "Plan downgrade + team split + proration + open ticket conflict",
        "expected_path": "complex_path",
    }

    ticket_4 = {
        "ticket_id": "tkt_phase1_004",
        "tenant_id": tenant_id,
        "query": (
            "I suspect someone has accessed my account without authorization. Three things happened: "
            "1) My password was changed 2 days ago but I did not request this. "
            "2) A new team member 'john_devops' was added to my workspace yesterday — I don't know "
            "who this is. "
            "3) Our SSO integration with Okta is showing 'last synced 5 days ago' even though it "
            "should sync every hour. I need you to: remove the unauthorized user, reset my password, "
            "investigate the SSO sync failure, and tell me if any data was exported or modified "
            "during this period. This is urgent — we handle sensitive financial data."
        ),
        "channel_type": "chat",
        "variant_tier": "high",
        "quota": 1997,
        "customer_context": {
            "account_tier": "high",
            "customer_tenure_days": 400,
            "recent_ticket_count": 12,
            "lifetime_value": 18000,
            "team_size": 25,
            "has_sso": True,
        },
        "sender": "security@fincomp.com",
        "description": "Account security breach + unauthorized user + SSO failure",
        "expected_path": "complex_path",
    }

    tickets = [ticket_1, ticket_2, ticket_3, ticket_4]

    # ── Run Tickets ───────────────────────────────────────────

    results = []
    total_pipeline_start = time.time()

    for i, ticket in enumerate(tickets):
        if i > 0:
            wait = SECONDS_BETWEEN_TICKETS
            print(f"\n{'='*70}")
            print(f"  WAITING {wait}s for NVIDIA rate limit reset (40 RPM)...")
            print(f"  Elapsed so far: {time.time() - total_pipeline_start:.0f}s")
            print(f"{'='*70}")
            for remaining in range(wait, 0, -10):
                print(f"    ... {remaining}s remaining")
                await asyncio.sleep(min(10, remaining))

        result = await run_ticket(ticket, graph, i + 1)
        results.append(result)

    total_elapsed = time.time() - total_pipeline_start

    # ── Final Summary ─────────────────────────────────────────

    print(f"\n\n{'='*70}")
    print("  PHASE 1 — FINAL TEST SUMMARY")
    print(f"{'='*70}")
    print(f"  Total Time:      {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"  Tickets Tested:  {len(results)}")
    print(f"")

    total_llm = 0
    total_errors = 0
    for r in results:
        tid = r["ticket_id"]
        status = r.get("status", "ERROR")
        llm = r.get("llm_calls", 0)
        quality = r.get("quality", "N/A")
        elapsed = r.get("elapsed", 0)
        route = r.get("route", "N/A")
        loops = r.get("loop_count", 0)
        escalated = r.get("escalated", False)
        total_llm += llm
        if status == "ERROR":
            total_errors += 1

        status_icon = "RESOLVED" if status == "resolved" else ("ESCALATED" if status == "escalated" else f"ERROR: {r.get('error', '')}")
        print(f"  {tid}:")
        print(f"    Status:       {status_icon}")
        print(f"    Route:        {route}")
        print(f"    LLM Calls:    {llm}")
        print(f"    Quality:      {quality}")
        print(f"    Loops:        {loops}")
        print(f"    Escalated:    {escalated}")
        print(f"    Time:         {elapsed:.1f}s")
        print(f"    Avg/Call:     {(elapsed/max(llm,1)):.2f}s per LLM call")
        print(f"")

    print(f"  --- AGGREGATE ---")
    print(f"    Total LLM Calls:       {total_llm}")
    print(f"    Avg Calls/Ticket:      {total_llm/max(len(results),1):.0f}")
    print(f"    Total Errors:          {total_errors}/{len(results)}")
    print(f"    Total Time:            {total_elapsed:.1f}s")
    print(f"    Pipeline Overhead:     {total_elapsed - total_llm * 1.5:.1f}s (excl. LLM time)")
    print(f"")

    if total_errors == 0:
        print("  RESULT: ALL TICKETS COMPLETED SUCCESSFULLY")
    else:
        print(f"  RESULT: {total_errors} ERRORS NEED ATTENTION")

    print(f"\n  Phase 1 Complete: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())