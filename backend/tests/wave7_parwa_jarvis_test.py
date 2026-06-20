"""
Wave 7 — Run 3 Tickets Through PARWA + Verify Jarvis Integration

1. Starts the backend server
2. Runs 3 new tickets through the PARWA pipeline (NVIDIA LLM)
3. After each ticket, checks that:
   - Quality scores were written to Jarvis DB
   - Notifications were created
   - Audit trail has entries
4. Verifies all data flows PARWA → Jarvis DB → API endpoints

Usage: cd /home/z/my-project/parwa/backend && python tests/wave7_parwa_jarvis_test.py
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project/parwa/backend")

API = "http://localhost:8100"
TENANT = "default_tenant"
server_proc = None
server_ready = threading.Event()

results = {"total": 0, "passed": 0, "failed": 0, "tests": []}


def start_server():
    global server_proc
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--host", "0.0.0.0", "--port", "8100", "--log-level", "warning"],
        cwd="/home/z/my-project/parwa/backend",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{API}/api/health", timeout=2)
            server_ready.set()
            return
        except:
            time.sleep(1)


def stop_server():
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except:
            server_proc.kill()


def api_get(path, params=""):
    url = f"{API}{path}"
    if params:
        url += f"?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, {}
    except Exception as e:
        return 0, {}


def api_post(path, body_dict):
    url = f"{API}{path}"
    body = json.dumps(body_dict).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, {}
    except Exception as e:
        return 0, {}


def record(name, passed, detail=""):
    results["total"] += 1
    if passed:
        results["passed"] += 1
        print(f"  \033[92m✓\033[0m {name}")
    else:
        results["failed"] += 1
        print(f"  \033[91m✗\033[0m {name}: {detail[:200]}")
    results["tests"].append({"name": name, "pass": passed, "detail": detail[:300]})


async def run_tickets_and_verify():
    """Run 3 tickets through PARWA pipeline and verify data flows to Jarvis."""

    from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
    from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
    from app.core.parwa_pipeline.llm_client import get_stats, reset_stats, set_pipeline_timeout

    TICKETS = [
        {
            "ticket_id": "tkt_wave7_001",
            "tenant_id": TENANT,
            "query": (
                "I was charged $89 twice this month — once on Jan 3 and again on Jan 17. "
                "I never authorized the second charge. The second charge shows as 'plan_upgrade' "
                "but I never upgraded. I need the duplicate charge refunded to my Visa ending in 4242."
            ),
            "channel_type": "chat",
            "variant_tier": "high",
            "quota": 2000,
            "customer_context": {"account_tier": "pro", "customer_tenure_days": 90,
                                 "recent_ticket_count": 2, "lifetime_value": 800},
            "sender": "alex.m@gmail.com",
            "description": "Duplicate charge dispute - $89",
        },
        {
            "ticket_id": "tkt_wave7_002",
            "tenant_id": TENANT,
            "query": (
                "Hi, I want to cancel my Pro plan subscription at $149/month. "
                "I've been on it for 6 months. I need: 1) Prorated refund for remaining 18 days? "
                "2) What happens to my stored data? 3) Can I reactivate later without losing data?"
            ),
            "channel_type": "email",
            "variant_tier": "high",
            "quota": 1999,
            "customer_context": {"account_tier": "pro", "customer_tenure_days": 180,
                                 "recent_ticket_count": 1, "lifetime_value": 894},
            "sender": "jenny.t@outlook.com",
            "description": "Subscription cancellation + refund request",
        },
        {
            "ticket_id": "tkt_wave7_003",
            "tenant_id": TENANT,
            "query": (
                "We are a team of 8 on the High plan ($499/month). We want to add 4 more members "
                "and need API access for our internal tools. Questions: 1) Cost for 4 more members? "
                "2) Is API access included? 3) Volume discounts for 10+ teams? 4) Enterprise billing?"
            ),
            "channel_type": "email",
            "variant_tier": "high",
            "quota": 1998,
            "customer_context": {"account_tier": "high", "customer_tenure_days": 300,
                                 "recent_ticket_count": 5, "lifetime_value": 5988, "team_size": 8},
            "sender": "ops@techcorp.io",
            "description": "Plan upgrade + API access inquiry",
        },
    ]

    reset_stats()
    set_pipeline_timeout(120)  # 2 min per ticket

    for i, ticket in enumerate(TICKETS):
        ticket_id = ticket["ticket_id"]
        print(f"\n  {'─'*50}")
        print(f"  TICKET {i+1}/3: {ticket_id}")
        print(f"  {ticket['description']}")
        print(f"  {'─'*50}")

        set_test_variant(TENANT, ticket["variant_tier"], ticket["quota"])

        initial_state = {
            "ticket_id": ticket_id,
            "tenant_id": TENANT,
            "query": ticket["query"],
            "channel_type": ticket.get("channel_type", "email"),
            "customer_context": ticket.get("customer_context", {}),
            "metadata": {
                "sender": ticket.get("sender", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "loop_count": 0,
            "total_token_usage": 0,
            "technique_log": [],
            "errors": [],
        }

        try:
            start_time = time.time()
            graph = build_parwa_pipeline()
            compiled = graph.compile()
            result = await compiled.ainvoke(initial_state)
            elapsed = time.time() - start_time

            status = result.get("status", "unknown")
            quality = result.get("quality_score", "N/A")
            route = result.get("route_decision", result.get("current_path", "N/A"))
            loops = result.get("loop_count", 0)
            escalated = bool(result.get("escalation_context"))
            response = (
                result.get("final_response", "")
                or result.get("formatted_response", "")
                or result.get("simple_answer", "")
                or result.get("super_node_answer", "")
            )

            print(f"  Status: {status} | Quality: {quality} | Route: {route}")
            print(f"  Loops: {loops} | Escalated: {escalated} | Time: {elapsed:.1f}s")
            print(f"  Response: {response[:200]}...")

            record(f"PARWA Ticket {i+1}: {ticket_id}",
                   status in ("resolved", "escalated", "completed"),
                   f"status={status}, quality={quality}, route={route}, time={elapsed:.1f}s")

            # Save result
            result_file = f"/home/z/my-project/parwa/backend/tests/results/wave7_parwa_ticket_{i+1}.json"
            with open(result_file, "w") as f:
                json.dump({
                    "ticket_id": ticket_id,
                    "description": ticket["description"],
                    "status": status,
                    "quality_score": quality,
                    "route": route,
                    "loop_count": loops,
                    "escalated": escalated,
                    "elapsed_seconds": round(elapsed, 2),
                    "final_response": response[:3000],
                    "errors": result.get("errors", []),
                }, f, indent=2, default=str)

        except Exception as e:
            print(f"  ERROR: {e}")
            record(f"PARWA Ticket {i+1}: {ticket_id}", False, str(e))

        # After each ticket, verify Jarvis picked up data
        print(f"\n  --- Verify Jarvis data after ticket {i+1} ---")
        time.sleep(0.5)  # Give DB time to settle

        # Check quality scores via API
        code, data = api_get("/api/quality/scores", f"tenant_id={TENANT}&days=1")
        total_scores = data.get("total_scores", 0) if isinstance(data, dict) else 0
        record(f"After ticket {i+1}: quality scores available", total_scores > 0,
               f"total={total_scores}")

        # Check notifications via API
        code, data = api_get("/api/jarvis/notifications", f"tenant_id={TENANT}&include_resolved=true")
        notif_count = data.get("count", 0) if isinstance(data, dict) else 0
        record(f"After ticket {i+1}: notifications exist", notif_count > 0,
               f"count={notif_count}")

        # Check audit trail
        code, data = api_get("/api/jarvis/audit", f"tenant_id={TENANT}&limit=20")
        audit_count = data.get("count", 0) if isinstance(data, dict) else 0
        record(f"After ticket {i+1}: audit trail", audit_count > 0,
               f"count={audit_count}")

    # LLM stats
    stats = get_stats()
    print(f"\n  LLM Stats: {stats['total_calls']} calls, {stats['total_tokens']} tokens, {stats['total_errors']} errors")


async def test_parwa_jarvis_bridge():
    """Test the bidirectional PARWA-Jarvis bridge."""
    print("\n" + "=" * 60)
    print("  PARWA ↔ JARVIS BRIDGE TEST")
    print("=" * 60)

    from app.core.parwa_pipeline.parwa_bridge import (
        load_system_flags,
        write_quality_score_to_jarvis,
        write_to_jarvis_inbox,
        score_confidence,
        route_by_sentiment,
        check_approval_gate,
        recommend_variant,
    )

    # Bridge: load flags
    flags = await load_system_flags(TENANT)
    record("Bridge: load_system_flags", isinstance(flags, dict),
           f"keys={list(flags.keys())}")

    # Bridge: write quality score
    score = await write_quality_score_to_jarvis(
        tenant_id=TENANT, ticket_id="tkt_bridge_001",
        quality_score=0.92, resolution_path="complex_path",
        nodes_reached=["node_1","node_2","node_3","node_4","node_5","node_6"],
        llm_calls=8, tokens_used=3200,
    )
    record("Bridge: write_quality_score", score is not None)

    # Bridge: write to inbox
    msg = await write_to_jarvis_inbox(
        tenant_id=TENANT, ticket_id="tkt_stuck_001",
        stuck_reason="Quality below threshold", quality_score=0.65,
        what_was_tried="Reflexion + CRP applied",
    )
    record("Bridge: write_to_jarvis_inbox", msg is not None)

    # Bridge: confidence scoring
    conf = await score_confidence(
        tenant_id=TENANT, ticket_id="tkt_conf_001",
        ticket_type="refund", query="I need a refund",
        required_action="refund", value_usd=89.0,
    )
    record("Bridge: score_confidence", conf is not None,
           f"routing={conf.get('routing') if conf else 'N/A'}")

    # Bridge: sentiment routing
    sent = await route_by_sentiment(
        tenant_id=TENANT, ticket_id="tkt_sent_001",
        query="This is absolutely unacceptable! I've been waiting 3 weeks!",
    )
    record("Bridge: route_by_sentiment", sent is not None,
           f"route={sent.get('route') if sent else 'N/A'}")

    # Bridge: approval gate
    gate = await check_approval_gate(
        tenant_id=TENANT, action="refund",
        confidence=0.75, value_usd=500.0,
    )
    record("Bridge: check_approval_gate", gate is not None,
           f"required={gate.get('required') if gate else 'N/A'}")

    # Bridge: variant recommendation
    var = await recommend_variant(
        tenant_id=TENANT, ticket_id="tkt_var_001",
        query="Complex billing dispute with multiple charges",
        current_variant="mini", required_action="refund",
    )
    record("Bridge: recommend_variant", var is not None,
           f"upgrade={var.get('upgrade_needed') if var else 'N/A'}")

    # Verify bridge data appears in API
    code, data = api_get("/api/quality/scores", f"tenant_id={TENANT}&days=1")
    total = data.get("total_scores", 0) if isinstance(data, dict) else 0
    record("Bridge data visible via API", total > 0, f"total_scores={total}")

    code, data = api_get("/api/jarvis/notifications", f"tenant_id={TENANT}&include_resolved=true")
    count = data.get("count", 0) if isinstance(data, dict) else 0
    record("Notifications visible via API", count > 0, f"count={count}")


async def async_main():
    print("\n" + "=" * 60)
    print("  WAVE 7 — PARWA TICKETS + JARVIS INTEGRATION")
    print("=" * 60)

    await run_tickets_and_verify()
    await test_parwa_jarvis_bridge()


def main():
    print("\n" + "=" * 60)
    print("  Starting server...")
    print("=" * 60)

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    server_ready.wait(timeout=35)

    if not server_ready.is_set():
        print("  FATAL: Server failed to start")
        sys.exit(1)

    print("  Server ready on port 8100!")

    try:
        asyncio.run(async_main())
    finally:
        stop_server()

    # Summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    total = results["total"]
    passed = results["passed"]
    failed = results["failed"]
    rate = passed / max(total, 1) * 100
    print(f"  Total:  {total}")
    print(f"  Passed: \033[92m{passed}\033[0m")
    print(f"  Failed: \033[91m{failed}\033[0m")
    print(f"  Rate:   {rate:.1f}%")

    if failed > 0:
        print("\n  FAILED TESTS:")
        for t in results["tests"]:
            if not t["pass"]:
                print(f"    ✗ {t['name']}: {t['detail']}")

    os.makedirs("/home/z/my-project/parwa/backend/tests/results", exist_ok=True)
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open("/home/z/my-project/parwa/backend/tests/results/wave7_parwa_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: wave7_parwa_results.json")


if __name__ == "__main__":
    main()
