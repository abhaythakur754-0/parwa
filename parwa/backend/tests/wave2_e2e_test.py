"""
Wave 2 — End-to-End Test

Proves the FULL chain is wired with REAL DATA (no mocks in SENSE):
  1. DB layer: integration pings, LLM costs, stuck tickets, drift detection, flow, load
  2. Signal collectors: all 7 collectors read from DB
  3. SENSE node: all signals from real collectors
  4. EVALUATE node: drift scoring, escalation tiers, load evaluation
  5. NOTIFY node: 5 new query handlers (health, cost, flow, load, stuck)
  6. Command parser: 5 new regex patterns
  7. Full pipeline: chat → parse → auth → execute → DB → response

Run: python tests/wave2_e2e_test.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/home/z/my-project/parwa/backend")

from app.core.jarvis_pipeline.jarvis_db import (
    use_in_memory, reset_db, get_db,
    PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
)
from app.core.jarvis_pipeline.command_parser import (
    classify_command_sync, is_query_intent,
)
from app.core.jarvis_pipeline.jarvis_auth import (
    authorize_command_sync, make_user_context,
)
from app.core.jarvis_pipeline.graph import run_jarvis_chat, run_jarvis
from app.core.jarvis_pipeline.signal_collectors import (
    collect_stuck_tickets,
    collect_integration_health,
    collect_quota_status,
    collect_accuracy_drift,
    collect_ticket_flow,
    collect_llm_costs,
    collect_load_status,
)

TENANT_ID = "test_tenant_002"
ADMIN_EMAIL = "admin@parwa.ai"

PASS = 0
FAIL = 0
RESULTS = []


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append(("PASS" if condition else "FAIL", name, detail))


async def run_all():
    global PASS, FAIL, RESULTS
    # Reset
    reset_db()
    use_in_memory()
    db = get_db()

    print("=" * 70)
    print("WAVE 2 — END-TO-END TEST")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────
    # SECTION 1: DB LAYER — Wave 2 Methods
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 1: DB Layer (Wave 2 Methods) ---")

    # 1a. Integration pings
    await db.write_integration_ping(TENANT_ID, "sendgrid", True, 45.2)
    await db.write_integration_ping(TENANT_ID, "sendgrid", True, 52.1)
    await db.write_integration_ping(TENANT_ID, "sendgrid", False, None, "Connection timeout", 504)
    await db.write_integration_ping(TENANT_ID, "stripe", True, 120.5)
    await db.write_integration_ping(TENANT_ID, "stripe", True, 110.2)

    health = await db.get_integration_health(TENANT_ID)
    test("DB: write_integration_ping stores pings", len(health["services"]) == 2,
         f"services={list(health['services'].keys())}")
    test("DB: sendgrid uptime 66.7% (2/3 healthy)",
         health["services"]["sendgrid"]["uptime_pct"] == 66.7,
         f"uptime={health['services']['sendgrid']['uptime_pct']}")
    test("DB: sendgrid has error",
         health["services"]["sendgrid"]["last_error"] == "Connection timeout",
         f"error={health['services']['sendgrid']['last_error']}")
    test("DB: stripe 100% healthy",
         health["services"]["stripe"]["status"] == "healthy",
         f"status={health['services']['stripe']['status']}")
    test("DB: degraded_count=1", health["degraded_count"] == 1,
         f"degraded={health['degraded_count']}")

    # 1b. LLM cost tracking
    await db.record_llm_cost(TENANT_ID, "llama-3.1-8b", 150, 80, 0.00045, "parwa_pipeline")
    await db.record_llm_cost(TENANT_ID, "llama-3.1-8b", 200, 100, 0.00060, "parwa_pipeline")
    await db.record_llm_cost(TENANT_ID, "gpt-4o-mini", 300, 150, 0.00120, "jarvis_chat")

    cost = await db.get_llm_cost_summary(TENANT_ID)
    test("DB: LLM cost total_calls=3", cost["total_calls"] == 3, f"calls={cost['total_calls']}")
    test("DB: LLM cost by_model has 2 models", len(cost["by_model"]) == 2,
         f"models={list(cost['by_model'].keys())}")
    test("DB: LLM cost by_type has jarvis_chat",
         "jarvis_chat" in cost["by_type"],
         f"types={list(cost['by_type'].keys())}")
    test("DB: LLM cost total_tokens correct",
         cost["total_tokens"] == 150 + 80 + 200 + 100 + 300 + 150,
         f"tokens={cost['total_tokens']}")

    # 1c. Stuck ticket tracking
    await db.record_stuck_ticket_check(TENANT_ID, "TKT-001", "super_node_escalated", 14.0, "backup_alert")
    await db.record_stuck_ticket_check(TENANT_ID, "TKT-002", "pipeline_errors", 2.0, "soft_reminder")

    stuck = await db.get_stuck_tickets(TENANT_ID)
    test("DB: stuck tickets count=2", len(stuck) == 2, f"stuck={len(stuck)}")
    test("DB: TKT-001 escalation=backup_alert", stuck[0]["escalation_tier"] == "backup_alert",
         f"tier={stuck[0]['escalation_tier']}")

    # 1d. Drift detection
    now = datetime.now(timezone.utc)
    # Create scores across 4 days: declining pattern
    for day_offset in range(4):
        day = now - timedelta(days=3 - day_offset)
        date_str = day.isoformat()
        # Declining: 0.95, 0.90, 0.85, 0.78
        score_val = [0.95, 0.90, 0.85, 0.78][day_offset]
        await db.write_quality_score(
            tenant_id=TENANT_ID, ticket_id=f"TKT-D{day_offset}",
            overall_score=score_val, confidence_score=0.9,
            resolution_path="complex" if day_offset < 3 else "stuck",
            nodes_reached=["N1", "N2", "N3"], llm_calls=3, tokens_used=500,
            model_used="llama-3.1-8b",
        )
        # Fix the created_at to simulate different days
        scores = db._quality_scores
        scores[-1]["created_at"] = date_str

    drift = await db.check_quality_drift(TENANT_ID)
    test("DB: drift detected=True", drift["drift_detected"] == True,
         f"detected={drift['drift_detected']}")
    test("DB: drift trend_direction=declining",
         drift["trend_direction"] in ("declining", "slight_decline"),
         f"trend={drift['trend_direction']}")
    test("DB: drift severity=warning or critical",
         drift["drift_severity"] in ("warning", "critical"),
         f"severity={drift['drift_severity']}")

    # 1e. Ticket flow aggregation
    flow = await db.get_ticket_flow_summary(TENANT_ID)
    test("DB: flow total=4", flow["total"] == 4, f"total={flow['total']}")
    test("DB: flow auto_resolved=3 (score>=0.85)",
         flow["auto_resolved"] == 3,
         f"auto={flow['auto_resolved']}")
    test("DB: flow stuck=1", flow["stuck"] == 1, f"stuck={flow['stuck']}")
    test("DB: flow by_node has N1", "N1" in flow["by_node"],
         f"by_node={flow['by_node']}")

    # 1f. Load status
    db.set_load(TENANT_ID, "parwa", 4, 5)
    db.set_load(TENANT_ID, "mini", 2, 5)
    load = await db.get_load_status(TENANT_ID)
    test("DB: load variants=2", len(load["variants"]) == 2,
         f"variants={len(load['variants'])}")
    test("DB: parwa 80% utilized (high)",
         load["variants"][0]["utilization_pct"] == 80.0,
         f"util={load['variants'][0]['utilization_pct']}")
    test("DB: parwa status=high",
         load["variants"][0]["status"] == "high",
         f"status={load['variants'][0]['status']}")

    # ─────────────────────────────────────────────────────────
    # SECTION 2: SIGNAL COLLECTORS
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 2: Signal Collectors ---")

    # 2a. Stuck tickets collector
    parwa_state_escalated = {
        "ticket_id": "TKT-NEW",
        "status": "escalated",
        "quality_score": 0.6,
        "loop_count": 2,
        "errors": ["Quality too low"],
        "escalation_context": {"reason": "super_node_failed"},
    }
    stuck_collected = await collect_stuck_tickets(TENANT_ID, parwa_state_escalated)
    test("Collector: stuck_tickets finds live + DB",
         len(stuck_collected) >= 2,
         f"count={len(stuck_collected)}")
    test("Collector: live ticket has escalation_tier",
         any(s["escalation_tier"] for s in stuck_collected if s["ticket_id"] == "TKT-NEW"),
         "live ticket should have escalation_tier")

    # 2b. Integration health collector
    health_collected = await collect_integration_health(TENANT_ID)
    test("Collector: integration_health returns services",
         len(health_collected["services"]) > 0,
         f"services={list(health_collected['services'].keys())}")
    test("Collector: integration_health has degraded_count",
         "degraded_count" in health_collected,
         f"keys={list(health_collected.keys())}")

    # 2c. Quota collector
    quota_collected = await collect_quota_status(TENANT_ID)
    test("Collector: quota_status returns dict", isinstance(quota_collected, dict),
         f"type={type(quota_collected)}")

    # 2d. Drift collector
    drift_collected = await collect_accuracy_drift(TENANT_ID)
    test("Collector: drift returns trend_direction",
         "trend_direction" in drift_collected,
         f"keys={list(drift_collected.keys())}")
    test("Collector: drift detected from our declining scores",
         drift_collected["drift_detected"] == True,
         f"detected={drift_collected['drift_detected']}")

    # 2e. Ticket flow collector
    flow_collected = await collect_ticket_flow(TENANT_ID, {"ticket_id": "", "technique_log": []})
    test("Collector: ticket_flow has summary",
         "summary" in flow_collected,
         f"keys={list(flow_collected.keys())}")
    test("Collector: ticket_flow summary has total",
         flow_collected["summary"]["total"] == 4,
         f"total={flow_collected['summary']['total']}")

    # 2f. LLM costs collector
    cost_collected = await collect_llm_costs(TENANT_ID)
    test("Collector: llm_costs has persisted",
         "persisted" in cost_collected,
         f"keys={list(cost_collected.keys())}")
    test("Collector: llm_costs total_calls_combined >= 3",
         cost_collected["total_calls_combined"] >= 3,
         f"combined={cost_collected['total_calls_combined']}")

    # 2g. Load status collector
    load_collected = await collect_load_status(TENANT_ID)
    test("Collector: load_status has variants",
         len(load_collected["variants"]) == 2,
         f"variants={len(load_collected['variants'])}")

    # ─────────────────────────────────────────────────────────
    # SECTION 3: COMMAND PARSER (Wave 2 Intents)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 3: Command Parser (Wave 2 Intents) ---")

    w2_commands = [
        ("show integration health", "query_health"),
        ("check service status", "query_health"),
        ("show llm costs", "query_cost"),
        ("how much have we spent on tokens", "query_cost"),
        ("show ticket flow metrics", "query_flow"),
        ("how many resolved this week", "query_flow"),
        ("show load status", "query_load"),
        ("check bottleneck", "query_load"),
        ("show stuck tickets", "query_stuck"),
        ("show pending approvals", "query_stuck"),
    ]

    for cmd, expected_intent in w2_commands:
        result = classify_command_sync(cmd)
        matched = result["intent"] == expected_intent
        test(f"Parser: '{cmd}' → {expected_intent}",
             matched, f"got={result['intent']} method={result['classification_method']}")
        test(f"Parser: '{cmd}' is_query_intent",
             is_query_intent(result["intent"]),
             f"intent={result['intent']}")

    # ─────────────────────────────────────────────────────────
    # SECTION 4: FULL PIPELINE — SENSE (Real Collectors)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 4: Full Pipeline — SENSE Node ---")

    result = await run_jarvis(
        tenant_id=TENANT_ID,
        trigger="poll",
        parwa_state=parwa_state_escalated,
    )

    signals = result.get("signals", {})
    test("Pipeline: SENSE returns signals", bool(signals), f"signals={list(signals.keys())}")

    # Verify NO MOCKS — all 8 signal keys present
    expected_signal_keys = [
        "stuck_tickets", "quota_status", "integration_health", "policy_version",
        "accuracy_trend", "ticket_flow", "drift_status", "llm_costs", "load_status",
    ]
    for key in expected_signal_keys:
        test(f"Pipeline: SENSE has signal '{key}'",
             key in signals,
             f"missing={key}")

    # Verify integration_health is REAL (has services dict, not just {"sendgrid": "healthy"})
    ih = signals.get("integration_health", {})
    test("Pipeline: integration_health has 'services' key (real data, not mock)",
         "services" in ih and isinstance(ih["services"], dict),
         f"keys={list(ih.keys())}")

    # Verify drift_status is REAL (has drift_detected key)
    ds = signals.get("drift_status", {})
    test("Pipeline: drift_status has 'drift_detected' (real data, not mock string)",
         isinstance(ds, dict) and "drift_detected" in ds,
         f"drift_status type={type(ds)}")

    # Verify llm_costs is REAL (has persisted key)
    lc = signals.get("llm_costs", {})
    test("Pipeline: llm_costs has 'persisted' key (real data, not just call count)",
         isinstance(lc, dict) and "persisted" in lc,
         f"llm_costs type={type(lc)}")

    # Verify load_status is REAL (has variants list)
    ls = signals.get("load_status", {})
    test("Pipeline: load_status has 'variants' (real data, not empty dict)",
         isinstance(ls, dict) and "variants" in ls,
         f"load_status type={type(ls)}")

    # Verify ticket_flow has summary (real aggregation)
    tf = signals.get("ticket_flow", {})
    test("Pipeline: ticket_flow has 'summary' key (real aggregation, not single ticket)",
         isinstance(tf, dict) and "summary" in tf,
         f"ticket_flow keys={list(tf.keys())}")

    # ─────────────────────────────────────────────────────────
    # SECTION 5: FULL PIPELINE — EVALUATE (Wave 2 Scoring)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 5: Full Pipeline — EVALUATE Node ---")

    evaluations = result.get("evaluations", [])
    test("Pipeline: EVALUATE produced evaluations", len(evaluations) > 0,
         f"count={len(evaluations)}")

    # Check that drift evaluation exists (since we have drift data)
    drift_evals = [e for e in evaluations if e.get("type") == "accuracy_drop"]
    if drift_evals:
        de = drift_evals[0]
        test("Pipeline: drift eval has severity",
             "drift_severity" in de,
             f"keys={list(de.keys())}")
        test("Pipeline: drift eval has signal with trigger",
             de.get("signal", {}).get("trigger") is not None,
             f"trigger={de.get('signal', {}).get('trigger')}")

    # Check that stuck ticket eval has escalation_tier
    stuck_evals = [e for e in evaluations if e.get("type") == "stuck_ticket"]
    if stuck_evals:
        se = stuck_evals[0]
        test("Pipeline: stuck eval has escalation_tier",
             "escalation_tier" in se,
             f"keys={list(se.keys())}")

    # Check load evaluation (if any variant at high capacity)
    load_evals = [e for e in evaluations if e.get("type") == "load_bottleneck"]
    test("Pipeline: load_bottleneck eval exists (parwa at 80%)",
         len(load_evals) > 0,
         f"load_evals={len(load_evals)}")

    # ─────────────────────────────────────────────────────────
    # SECTION 6: FULL PIPELINE — NOTIFY (Wave 2 Query Handlers)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 6: Full Pipeline — NOTIFY (Wave 2 Queries) ---")

    # Need to use admin_chat trigger for query handlers
    w2_queries = [
        ("show integration health", "Integration Health"),
        ("show llm costs", "LLM Cost Summary"),
        ("show ticket flow metrics", "Ticket Flow Metrics"),
        ("show load status", "Load Status"),
        ("show stuck tickets", "Stuck Tickets"),
    ]

    for question, expected_in_response in w2_queries:
        q_result = await run_jarvis_chat(
            tenant_id=TENANT_ID,
            question=question,
            user_email=ADMIN_EMAIL,
            user_role="admin",
            parwa_state=parwa_state_escalated,
        )
        response = q_result.get("chat_response", "")
        test(f"Query: '{question}' → contains '{expected_in_response}'",
             expected_in_response in response,
             f"response[:100]={response[:100]}")

    # ─────────────────────────────────────────────────────────
    # SECTION 7: WAVE 1 COMPATIBILITY (existing queries still work)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 7: Wave 1 Backward Compatibility ---")

    # First set a flag so query_flags has something to show
    await db.set_flag(TENANT_ID, "pause_action", "refund", ADMIN_EMAIL,
                     reason="Test flag for Wave 2")

    w1_queries = [
        ("show status", "System Status"),
        ("show quality", "Quality Metrics"),
        ("show flags", "Active Flags"),
        ("show audit", "Recent Activity"),
        ("pause refunds", "[OK]"),
    ]

    for question, expected_in_response in w1_queries:
        q_result = await run_jarvis_chat(
            tenant_id=TENANT_ID,
            question=question,
            user_email=ADMIN_EMAIL,
            user_role="admin",
            parwa_state={},
        )
        response = q_result.get("chat_response", "")
        test(f"W1 Compat: '{question}' → contains '{expected_in_response}'",
             expected_in_response in response,
             f"response[:100]={response[:100]}")

    # ─────────────────────────────────────────────────────────
    # SECTION 8: NOTIFICATION FORMAT (Wave 2 Enhanced)
    # ─────────────────────────────────────────────────────────
    print("\n--- Section 8: Notification Format (Wave 2) ---")

    # Run a poll that generates notifications from our test data
    poll_result = await run_jarvis(
        tenant_id=TENANT_ID,
        trigger="poll",
        parwa_state=parwa_state_escalated,
    )
    notifications = poll_result.get("notifications", [])
    test("Pipeline: poll created notifications", len(notifications) > 0,
         f"count={len(notifications)}")

    # Check stuck ticket notification has escalation info in title
    stuck_nf = [n for n in notifications if "Stuck Ticket" in n.get("title", "")]
    if stuck_nf:
        test("Notification: stuck ticket title has escalation tier",
             "SOFT_REMINDER" in stuck_nf[0]["title"] or "BACKUP_ALERT" in stuck_nf[0]["title"],
             f"title={stuck_nf[0]['title']}")

    # Check drift notification has severity
    drift_nf = [n for n in notifications if "Drift" in n.get("title", "")]
    if drift_nf:
        test("Notification: drift title has severity",
             "WARNING" in drift_nf[0]["title"] or "CRITICAL" in drift_nf[0]["title"],
             f"title={drift_nf[0]['title']}")

    # ─────────────────────────────────────────────────────────
    # RESULTS
    # ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS + FAIL})")
    print("=" * 70)

    if FAIL > 0:
        print("\nFAILED TESTS:")
        for status, name, detail in RESULTS:
            if status == "FAIL":
                print(f"  FAIL: {name} — {detail}")
    else:
        print("\nALL TESTS PASSED!")

    # Verify no mocks remain in SENSE
    print("\n--- MOCK VERIFICATION ---")
    with open("/home/z/my-project/parwa/backend/app/core/jarvis_pipeline/nodes/jarvis_1_sense.py") as f:
        sense_code = f.read()
    mock_indicators = [
        'return {"sendgrid": "healthy"',  # old hardcoded mock
        '_collect_integration_health()',
        '_collect_stuck_tickets(parwa_state)',
        '_detect_accuracy_trend(parwa_state)',
        '_collect_quota_status(tenant_id)',
        '_collect_ticket_flow(parwa_state)',
    ]
    has_old_mocks = any(indicator in sense_code for indicator in mock_indicators)
    test("No old mock functions called in SENSE",
         not has_old_mocks,
         "old mock functions should not be called")

    real_collectors = [
        'collect_stuck_tickets',
        'collect_integration_health',
        'collect_quota_status',
        'collect_accuracy_drift',
        'collect_ticket_flow',
        'collect_llm_costs',
        'collect_load_status',
    ]
    for collector in real_collectors:
        test(f"SENSE uses '{collector}'",
             collector in sense_code,
             f"missing={collector}")

    print(f"\nFINAL: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)