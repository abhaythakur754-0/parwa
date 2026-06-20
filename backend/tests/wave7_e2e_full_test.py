"""
Wave 7 — Full End-to-End Integration Test

Tests EVERYTHING is connected and working:
1. Run 3 tickets through PARWA pipeline (creates quality scores, notifications)
2. Run Jarvis SENSE→EVALUATE→NOTIFY pipeline after each ticket
3. Test ALL API endpoints (30+ routes)
4. Test ALL button actions (approve/reject batch, set flag, resolve notification, chat)
5. Test SSE streaming
6. Verify data flows between PARWA → Jarvis → Frontend

Usage:
    cd /home/z/my-project/parwa/backend
    python tests/wave7_e2e_full_test.py
"""
import asyncio
import json
import os
import sys
import time
import traceback
import httpx
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project/parwa/backend")

API_BASE = "http://localhost:8100"
TENANT = "default_tenant"

# ── Test Results Tracker ──────────────────────────────────────────
results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "tests": [],
    "start_time": None,
    "end_time": None,
}


def record_test(name, passed, detail="", response_data=None):
    results["total"] += 1
    if passed:
        results["passed"] += 1
        status = "PASS"
    else:
        results["failed"] += 1
        status = "FAIL"
    results["tests"].append({
        "name": name,
        "status": status,
        "detail": detail[:500] if detail else "",
        "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else None,
    })
    symbol = "\033[92m✓\033[0m" if passed else "\033[91m✗\033[0m"
    print(f"  {symbol} {name}: {detail if not passed else 'OK'}")


async def api_get(path, params=None):
    """GET request to the API."""
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text


async def api_post(path, body=None):
    """POST request to the API."""
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text


# ═══════════════════════════════════════════════════════════════
# PHASE 1: Server Health Check
# ═══════════════════════════════════════════════════════════════

async def test_server_health():
    print("\n" + "=" * 60)
    print("  PHASE 1: SERVER HEALTH CHECK")
    print("=" * 60)

    # 1. Health endpoint
    code, data = await api_get("/api/health")
    record_test("GET /api/health", code == 200, f"status={code}", data)

    # 2. OpenAPI docs available
    code, _ = await api_get("/docs")
    record_test("GET /docs (OpenAPI)", code == 200, f"status={code}")

    # 3. Jarvis status endpoint
    code, data = await api_get("/api/jarvis/status", {"tenant_id": TENANT})
    record_test("GET /api/jarvis/status", code == 200, f"status={code}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}", data)


# ═══════════════════════════════════════════════════════════════
# PHASE 2: Run 3 Tickets Through PARWA Pipeline
# ═══════════════════════════════════════════════════════════════

async def run_parwa_tickets():
    print("\n" + "=" * 60)
    print("  PHASE 2: RUN 3 TICKETS THROUGH PARWA PIPELINE")
    print("=" * 60)

    from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
    from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
    from app.core.parwa_pipeline.llm_client import get_stats, reset_stats, set_pipeline_timeout

    NEW_TICKETS = [
        {
            "ticket_id": "tkt_wave7_001",
            "tenant_id": TENANT,
            "query": (
                "I was charged $89 twice this month — once on Jan 3 and again on Jan 17. "
                "I never authorized the second charge. I checked my billing history and "
                "the second charge shows as 'plan_upgrade' but I never upgraded anything. "
                "I need the duplicate charge refunded immediately to my Visa ending in 4242."
            ),
            "channel_type": "chat",
            "variant_tier": "high",
            "quota": 2000,
            "customer_context": {"account_tier": "pro", "customer_tenure_days": 90, "recent_ticket_count": 2, "lifetime_value": 800},
            "sender": "alex.m@gmail.com",
            "description": "Duplicate charge dispute - $89",
        },
        {
            "ticket_id": "tkt_wave7_002",
            "tenant_id": TENANT,
            "query": (
                "Hi, I want to cancel my subscription. I've been on the Pro plan for 6 months "
                "at $149/month. I just lost my job and can't afford it anymore. I need to know: "
                "1) Will I get a prorated refund for the remaining 18 days? 2) What happens to "
                "my stored data and history? 3) Can I reactivate later without losing anything?"
            ),
            "channel_type": "email",
            "variant_tier": "high",
            "quota": 1999,
            "customer_context": {"account_tier": "pro", "customer_tenure_days": 180, "recent_ticket_count": 1, "lifetime_value": 894},
            "sender": "jenny.t@outlook.com",
            "description": "Subscription cancellation + refund request",
        },
        {
            "ticket_id": "tkt_wave7_003",
            "tenant_id": TENANT,
            "query": (
                "We are a team of 8 and currently on the High plan at $499/month. "
                "We want to add 4 more team members and also need API access for our "
                "internal tools. Can you help us with: 1) How much will adding 4 members cost? "
                "2) Is API access included or an add-on? 3) Do you offer volume discounts "
                "for teams over 10? 4) What is the process for enterprise billing?"
            ),
            "channel_type": "email",
            "variant_tier": "high",
            "quota": 1998,
            "customer_context": {"account_tier": "high", "customer_tenure_days": 300, "recent_ticket_count": 5, "lifetime_value": 5988, "team_size": 8},
            "sender": "ops@techcorp.io",
            "description": "Plan upgrade + API access inquiry",
        },
    ]

    reset_stats()
    set_pipeline_timeout(120)  # 2 min timeout per ticket

    for i, ticket in enumerate(NEW_TICKETS):
        ticket_id = ticket["ticket_id"]
        print(f"\n  --- Ticket {i+1}/3: {ticket_id} ---")
        print(f"  Description: {ticket['description']}")

        set_test_variant(ticket["tenant_id"], ticket["variant_tier"], ticket["quota"])

        initial_state = {
            "ticket_id": ticket_id,
            "tenant_id": ticket["tenant_id"],
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
            start = time.time()
            graph = build_parwa_pipeline()
            compiled = graph.compile()
            result = await compiled.ainvoke(initial_state)
            elapsed = time.time() - start

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
            print(f"  Response: {response[:150]}...")

            record_test(
                f"PARWA Ticket {i+1}: {ticket_id}",
                status in ("resolved", "escalated", "completed"),
                f"status={status}, quality={quality}, route={route}, time={elapsed:.1f}s",
                {"status": status, "quality": quality, "route": route, "loops": loops, "escalated": escalated}
            )

            # Save individual result
            result_file = f"/home/z/my-project/parwa/backend/tests/results/wave7_ticket_{i+1}.json"
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
                    "llm_stats": get_stats(),
                    "final_response": response[:2000],
                    "errors": [e.get("error", str(e)) for e in result.get("errors", [])],
                }, f, indent=2, default=str)

        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
            record_test(f"PARWA Ticket {i+1}: {ticket_id}", False, str(e))

    # Show LLM stats
    stats = get_stats()
    print(f"\n  LLM Stats: {stats['total_calls']} calls, {stats['total_tokens']} tokens, {stats['total_errors']} errors")


# ═══════════════════════════════════════════════════════════════
# PHASE 3: Run Jarvis Pipeline (SENSE → EVALUATE → NOTIFY)
# ═══════════════════════════════════════════════════════════════

async def test_jarvis_pipeline():
    print("\n" + "=" * 60)
    print("  PHASE 3: JARVIS SENSE→EVALUATE→NOTIFY PIPELINE")
    print("=" * 60)

    # Test 1: Chat with "what is the system status?"
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "What is the system status?",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })
    has_response = isinstance(data, dict) and ("chat_response" in data or "response" in data)
    record_test("Jarvis Chat: system status query", code == 200 and has_response,
                f"status={code}, has_response={has_response}", data)

    # Test 2: Chat with "show me quality scores"
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "Show me quality scores",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })
    has_response = isinstance(data, dict) and ("chat_response" in data or "response" in data)
    record_test("Jarvis Chat: quality scores query", code == 200 and has_response,
                f"status={code}, has_response={has_response}", data)

    # Test 3: Control command - "pause refunds"
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "Pause all refund processing",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })
    has_response = isinstance(data, dict)
    record_test("Jarvis Chat: pause refunds command", code == 200 and has_response,
                f"status={code}", data)

    # Test 4: Control command - "resume refunds"
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "Resume refund processing",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })
    has_response = isinstance(data, dict)
    record_test("Jarvis Chat: resume refunds command", code == 200 and has_response,
                f"status={code}", data)

    # Test 5: Control command - "switch to supervised mode"
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "Switch to supervised mode",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })
    has_response = isinstance(data, dict)
    record_test("Jarvis Chat: switch mode command", code == 200 and has_response,
                f"status={code}", data)


# ═══════════════════════════════════════════════════════════════
# PHASE 4: Test ALL GET Endpoints
# ═══════════════════════════════════════════════════════════════

async def test_all_get_endpoints():
    print("\n" + "=" * 60)
    print("  PHASE 4: TEST ALL GET ENDPOINTS")
    print("=" * 60)

    get_endpoints = [
        ("/api/jarvis/status", "Jarvis Status"),
        ("/api/jarvis/metrics", "Jarvis Metrics"),
        ("/api/jarvis/notifications", "Notifications"),
        ("/api/jarvis/flags", "System Flags"),
        ("/api/quality/scores", "Quality Scores"),
        ("/api/quality/alerts", "Quality Alerts"),
        ("/api/quality/recommendations", "Quality Recommendations"),
        ("/api/quality/weekly-report", "Weekly Report"),
        ("/api/quality/health-score", "Health Score"),
        ("/api/quality/drift-check", "Drift Check"),
        ("/api/sla/status", "SLA Status"),
        ("/api/sla/credits", "SLA Credits"),
        ("/api/approvals/pending", "Pending Approvals"),
        ("/api/jarvis/audit", "Audit Trail"),
        ("/api/jarvis/customer-health", "Customer Health"),
        ("/api/jarvis/roi", "ROI Calculator"),
    ]

    for path, name in get_endpoints:
        code, data = await api_get(path, {"tenant_id": TENANT})
        is_json = isinstance(data, dict)
        has_data = is_json and len(data) > 0
        record_test(f"GET {name} ({path})", code == 200,
                    f"status={code}, json={is_json}, data_keys={list(data.keys()) if is_json else 'N/A'}", data)


# ═══════════════════════════════════════════════════════════════
# PHASE 5: Test ALL Button Actions (POST endpoints)
# ═══════════════════════════════════════════════════════════════

async def test_button_actions():
    print("\n" + "=" * 60)
    print("  PHASE 5: TEST ALL BUTTON ACTIONS (POST)")
    print("=" * 60)

    # ── Notification Resolve Button ──
    print("\n  --- Notification Buttons ---")

    # First create a notification by running a chat that generates one
    code, data = await api_post("/api/jarvis/chat", {
        "tenant_id": TENANT,
        "question": "Show me any stuck tickets or errors",
        "user_email": "admin@parwa.ai",
        "user_role": "admin",
    })

    # Get notifications
    code, data = await api_get("/api/jarvis/notifications", {"tenant_id": TENANT, "include_resolved": "true"})
    notifs = data.get("notifications", []) if isinstance(data, dict) else []
    record_test("GET notifications for resolve test", code == 200,
                f"status={code}, count={len(notifs)}", data)

    if notifs:
        # Resolve first notification
        notif_key = notifs[0].get("key", notifs[0].get("id", ""))
        if notif_key:
            code, data = await api_post(f"/api/jarvis/notifications/{notif_key}/resolve", {})
            record_test(f"POST resolve notification ({notif_key[:20]}...)", code == 200,
                        f"status={code}", data)

    # ── Batch Approve/Reject Buttons ──
    print("\n  --- Batch Approval Buttons ---")

    code, data = await api_post("/api/jarvis/notifications/batch/approve", {
        "tenant_id": TENANT,
        "batch_key": "test_batch_wave7",
    })
    record_test("POST batch approve", code == 200, f"status={code}", data)

    code, data = await api_post("/api/jarvis/notifications/batch/reject", {
        "tenant_id": TENANT,
        "batch_key": "test_batch_wave7_reject",
    })
    record_test("POST batch reject", code == 200, f"status={code}", data)

    # ── Set Flag Button ──
    print("\n  --- Flag Buttons ---")

    code, data = await api_post("/api/jarvis/flags", {
        "tenant_id": TENANT,
        "flag_type": "pause_action",
        "flag_value": "refund",
        "scope": "global",
        "reason": "Wave 7 E2E test",
    })
    record_test("POST set flag (pause_action:refund)", code == 200, f"status={code}", data)

    # Verify flag appears
    code, data = await api_get("/api/jarvis/flags", {"tenant_id": TENANT})
    flags = data.get("flags", []) if isinstance(data, dict) else []
    record_test("GET flags after setting", code == 200 and len(flags) > 0,
                f"status={code}, flags_count={len(flags)}", data)

    # Revoke the flag
    if flags:
        flag_id = flags[0].get("id", "")
        if flag_id:
            code, data = await api_post(f"/api/jarvis/flags/{flag_id}/revoke", {})
            record_test(f"POST revoke flag ({flag_id[:20]}...)", code == 200, f"status={code}", data)

    # ── Pause/Resume Command Buttons ──
    print("\n  --- Control Command Buttons ---")

    code, data = await api_post("/api/jarvis/command/pause", {
        "tenant_id": TENANT,
        "target": "returns",
        "user_email": "admin@parwa.ai",
    })
    record_test("POST pause returns", code == 200, f"status={code}", data)

    code, data = await api_post("/api/jarvis/command/resume", {
        "tenant_id": TENANT,
        "target": "returns",
        "user_email": "admin@parwa.ai",
    })
    record_test("POST resume returns", code == 200, f"status={code}", data)

    # ── Redirect Command Button ──
    code, data = await api_post("/api/jarvis/command/redirect", {
        "tenant_id": TENANT,
        "target": "instagram",
        "handler": "ai",
        "user_email": "admin@parwa.ai",
    })
    record_test("POST redirect instagram→ai", code == 200, f"status={code}", data)

    # ── Mode Command Button ──
    code, data = await api_post("/api/jarvis/command/mode", {
        "tenant_id": TENANT,
        "mode": "supervised",
        "user_email": "admin@parwa.ai",
    })
    record_test("POST mode→supervised", code == 200, f"status={code}", data)

    # ── Approval Batch Button ──
    code, data = await api_post("/api/approvals/batch", {
        "tenant_id": TENANT,
        "action": "approve",
        "batch_key": "wave7_test_batch",
    })
    record_test("POST approvals batch approve", code == 200, f"status={code}", data)

    # ── Quality Feedback Button ──
    code, data = await api_post("/api/quality/feedback", {
        "tenant_id": TENANT,
        "ticket_id": "tkt_wave7_001",
        "signal_type": "approved",
        "ai_response": "Your refund has been processed",
        "quality_score": 0.85,
        "ticket_type": "refund",
    })
    record_test("POST quality feedback (approved)", code == 200, f"status={code}", data)

    # ── Quality Alert Resolve Button ──
    code, alerts_data = await api_get("/api/quality/alerts", {"tenant_id": TENANT})
    alerts = alerts_data.get("alerts", []) if isinstance(alerts_data, dict) else []
    if alerts:
        alert_id = alerts[0].get("id", "")
        if alert_id:
            code, data = await api_post(f"/api/quality/alerts/{alert_id}/resolve", {})
            record_test(f"POST resolve quality alert ({alert_id[:20]}...)", code == 200, f"status={code}", data)
    else:
        record_test("POST resolve quality alert", True, "No alerts to resolve (expected)")

    # ── Emergency Shutdown Button ──
    # We'll test this and immediately revoke
    code, data = await api_post("/api/emergency/shutdown", {
        "tenant_id": TENANT,
        "user_email": "admin@parwa.ai",
    })
    record_test("POST emergency shutdown", code == 200, f"status={code}", data)

    # Revoke the shutdown flag
    code, data = await api_get("/api/jarvis/flags", {"tenant_id": TENANT, "flag_type": "global_shutdown"})
    flags = data.get("flags", []) if isinstance(data, dict) else []
    if flags:
        flag_id = flags[0].get("id", "")
        if flag_id:
            code, data = await api_post(f"/api/jarvis/flags/{flag_id}/revoke", {})
            record_test("POST revoke emergency shutdown flag", code == 200, f"status={code}", data)

    # ── Pause All Refunds Button ──
    code, data = await api_post("/api/pause_all_refunds", {
        "tenant_id": TENANT,
        "user_email": "admin@parwa.ai",
    })
    record_test("POST pause all refunds", code == 200, f"status={code}", data)

    # Revoke the pause flag
    code, data = await api_get("/api/jarvis/flags", {"tenant_id": TENANT, "flag_type": "pause_action"})
    flags = data.get("flags", []) if isinstance(data, dict) else []
    for flag in flags:
        flag_id = flag.get("id", "")
        if flag_id:
            await api_post(f"/api/jarvis/flags/{flag_id}/revoke", {})


# ═══════════════════════════════════════════════════════════════
# PHASE 6: Test SSE Streaming
# ═══════════════════════════════════════════════════════════════

async def test_sse_streaming():
    print("\n" + "=" * 60)
    print("  PHASE 6: SSE STREAMING TEST")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            async with client.stream("GET", f"{API_BASE}/api/jarvis/stream") as resp:
                record_test("SSE endpoint reachable", resp.status_code == 200,
                            f"status={resp.status_code}")

                if resp.status_code == 200:
                    # Read a few events
                    events_received = []
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            events_received.append(line)
                            if len(events_received) >= 3:
                                break
                        if len(events_received) == 0 and time.monotonic() > time.monotonic() + 10:
                            break

                    record_test("SSE events received", len(events_received) >= 1,
                                f"received {len(events_received)} events")
    except Exception as e:
        record_test("SSE streaming", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 7: Verify Data Persistence & Cross-Module Integration
# ═══════════════════════════════════════════════════════════════

async def test_data_integration():
    print("\n" + "=" * 60)
    print("  PHASE 7: DATA PERSISTENCE & CROSS-MODULE INTEGRATION")
    print("=" * 60)

    # Check quality scores written by PARWA
    code, data = await api_get("/api/quality/scores", {"tenant_id": TENANT, "days": "1"})
    has_scores = isinstance(data, dict) and data.get("total_scores", 0) > 0
    record_test("Quality scores persisted from PARWA", has_scores,
                f"total_scores={data.get('total_scores', 0) if isinstance(data, dict) else 'N/A'}", data)

    # Check notifications created by pipeline
    code, data = await api_get("/api/jarvis/notifications", {"tenant_id": TENANT, "include_resolved": "true"})
    notif_count = data.get("count", 0) if isinstance(data, dict) else 0
    record_test("Notifications exist from pipeline", notif_count > 0,
                f"count={notif_count}", data)

    # Check audit trail has entries
    code, data = await api_get("/api/jarvis/audit", {"tenant_id": TENANT, "limit": "10"})
    audit_count = data.get("count", 0) if isinstance(data, dict) else 0
    record_test("Audit trail populated", audit_count > 0,
                f"count={audit_count}", data)

    # Check metrics returns data
    code, data = await api_get("/api/jarvis/metrics", {"tenant_id": TENANT, "days": "1"})
    is_valid = isinstance(data, dict) and ("total_tasks" in data or "tenant_id" in data)
    record_test("Metrics endpoint returns data", code == 200 and is_valid,
                f"status={code}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}", data)

    # Check weekly report generates
    code, data = await api_get("/api/quality/weekly-report", {"tenant_id": TENANT, "days": "7"})
    is_valid = isinstance(data, dict)
    record_test("Weekly report generates", code == 200 and is_valid,
                f"status={code}", data)

    # Check health score returns
    code, data = await api_get("/api/quality/health-score", {"tenant_id": TENANT})
    is_valid = isinstance(data, dict)
    record_test("Health score returns", code == 200 and is_valid,
                f"status={code}", data)

    # Check SLA status
    code, data = await api_get("/api/sla/status", {"tenant_id": TENANT})
    is_valid = isinstance(data, dict) and ("sla_status" in data or "actual_uptime_pct" in data)
    record_test("SLA status computes", code == 200 and is_valid,
                f"status={code}", data)

    # Check customer health
    code, data = await api_get("/api/jarvis/customer-health", {"tenant_id": TENANT})
    is_valid = isinstance(data, dict)
    record_test("Customer health returns", code == 200 and is_valid,
                f"status={code}", data)

    # Check ROI calculator
    code, data = await api_get("/api/jarvis/roi", {"tenant_id": TENANT})
    is_valid = isinstance(data, dict)
    record_test("ROI calculator returns", code == 200 and is_valid,
                f"status={code}", data)


# ═══════════════════════════════════════════════════════════════
# PHASE 8: Verify PARWA → Jarvis Bridge (Bidirectional)
# ═══════════════════════════════════════════════════════════════

async def test_parwa_jarvis_bridge():
    print("\n" + "=" * 60)
    print("  PHASE 8: PARWA↔JARVIS BRIDGE INTEGRATION")
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

    # Test bridge: load flags
    flags = await load_system_flags(TENANT)
    record_test("Bridge: load_system_flags", isinstance(flags, dict),
                f"keys={list(flags.keys())}", flags)

    # Test bridge: write quality score
    score_record = await write_quality_score_to_jarvis(
        tenant_id=TENANT,
        ticket_id="tkt_wave7_bridge_test",
        quality_score=0.92,
        resolution_path="complex_path",
        nodes_reached=["node_1", "node_2", "node_3", "node_4", "node_5", "node_6"],
        llm_calls=8,
        tokens_used=3200,
    )
    record_test("Bridge: write_quality_score", score_record is not None,
                f"record={score_record is not None}", score_record)

    # Test bridge: write to inbox
    inbox_msg = await write_to_jarvis_inbox(
        tenant_id=TENANT,
        ticket_id="tkt_wave7_stuck_test",
        stuck_reason="Quality below threshold after 2 loops",
        quality_score=0.65,
        what_was_tried="Reflexion + CRP techniques applied",
    )
    record_test("Bridge: write_to_jarvis_inbox", inbox_msg is not None,
                f"msg={inbox_msg is not None}", inbox_msg)

    # Test bridge: score confidence
    conf_result = await score_confidence(
        tenant_id=TENANT,
        ticket_id="tkt_wave7_conf_test",
        ticket_type="refund",
        query="I need a refund for my order",
        required_action="refund",
        is_vip=False,
        value_usd=89.0,
    )
    record_test("Bridge: score_confidence", conf_result is not None,
                f"routing={conf_result.get('routing') if conf_result else 'N/A'}", conf_result)

    # Test bridge: sentiment routing
    sent_result = await route_by_sentiment(
        tenant_id=TENANT,
        ticket_id="tkt_wave7_sent_test",
        query="This is absolutely unacceptable! I've been waiting for 3 weeks!",
    )
    record_test("Bridge: route_by_sentiment", sent_result is not None,
                f"route={sent_result.get('route') if sent_result else 'N/A'}", sent_result)

    # Test bridge: approval gate
    gate_result = await check_approval_gate(
        tenant_id=TENANT,
        action="refund",
        confidence=0.75,
        value_usd=500.0,
    )
    record_test("Bridge: check_approval_gate", gate_result is not None,
                f"required={gate_result.get('required') if gate_result else 'N/A'}", gate_result)

    # Test bridge: variant recommendation
    var_result = await recommend_variant(
        tenant_id=TENANT,
        ticket_id="tkt_wave7_var_test",
        query="Complex billing dispute with multiple charges",
        current_variant="mini",
        required_action="refund",
    )
    record_test("Bridge: recommend_variant", var_result is not None,
                f"upgrade={var_result.get('upgrade_needed') if var_result else 'N/A'}", var_result)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    results["start_time"] = datetime.now(timezone.utc).isoformat()
    print("\n" + "=" * 60)
    print("  WAVE 7 — FULL END-TO-END INTEGRATION TEST")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print("=" * 60)

    try:
        await test_server_health()
        await run_parwa_tickets()
        await test_jarvis_pipeline()
        await test_all_get_endpoints()
        await test_button_actions()
        await test_sse_streaming()
        await test_data_integration()
        await test_parwa_jarvis_bridge()
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        traceback.print_exc()

    results["end_time"] = datetime.now(timezone.utc).isoformat()

    # Print Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"  Total:  {results['total']}")
    print(f"  Passed: \033[92m{results['passed']}\033[0m")
    print(f"  Failed: \033[91m{results['failed']}\033[0m")
    print(f"  Rate:   {results['passed']/max(results['total'],1)*100:.1f}%")

    if results['failed'] > 0:
        print("\n  FAILED TESTS:")
        for t in results['tests']:
            if t['status'] == 'FAIL':
                print(f"    ✗ {t['name']}: {t['detail']}")

    # Save results
    results_file = "/home/z/my-project/parwa/backend/tests/results/wave7_e2e_full_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_file}")
    print(f"  Finished: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")


if __name__ == "__main__":
    asyncio.run(main())
