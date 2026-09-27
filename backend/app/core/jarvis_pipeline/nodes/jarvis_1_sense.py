"""
Jarvis Node 1: SENSE (Observe) — Wave 2: Real Monitoring

Purpose: Monitor everything. Collect signals from PARWA pipeline,
variants, integrations, and knowledge base.

Question: What is happening RIGHT NOW?

LLM Cost: 0 calls (pure monitoring, data collection only)
Techniques: All 7 collectors now read from jarvis_db (real data).

Wave 2 changes:
  - _collect_stuck_tickets → signal_collectors.collect_stuck_tickets (DB-backed, 12h/24h/48h escalation)
  - _collect_integration_health → signal_collectors.collect_integration_health (real pings + DB history)
  - _collect_quota_status → signal_collectors.collect_quota_status (DB burn rate + trend)
  - _detect_accuracy_trend → signal_collectors.collect_accuracy_drift (DB drift analysis)
  - _collect_ticket_flow → signal_collectors.collect_ticket_flow (DB aggregation + live PARWA state)
  - NEW: collect_llm_costs (DB cost tracking + live session bridge)
  - NEW: collect_load_status (DB variant concurrency + VIP overflow)
  - REMOVED: _collect_policy_version (absorbed into drift detection)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
from app.core.jarvis_pipeline.signal_collectors import (
    collect_stuck_tickets,
    collect_integration_health,
    collect_quota_status,
    collect_accuracy_drift,
    collect_ticket_flow,
    collect_llm_costs,
    collect_load_status,
)

logger = logging.getLogger("jarvis.sense")


# ── Policy version check (still uses wiki, not mock) ───────────

def _collect_policy_version(tenant_id: str) -> Dict[str, Any]:
    """Check AI Wiki Section C for policy changes."""
    try:
        wiki = get_wiki_store()
        stats = wiki.get_stats(tenant_id)
        return {
            "section_c_entries": stats.get("section_c_entries", 0),
            "total_entries": stats.get("total_entries", 0),
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        return {"section_c_entries": 0, "total_entries": 0, "error": "wiki_unavailable"}


# ── Main Node Function ────────────────────────────────────────


async def jarvis_sense(state: dict) -> dict:
    """Jarvis Node 1: SENSE — Observe all signals (REAL DATA).

    Wave 2: All 7 collectors read from jarvis_db.
    Zero mocks. Every signal is backed by persistent storage.

    LLM calls: 0 (pure data collection).
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    trigger = state.get("trigger", "poll")
    parwa_state = state.get("parwa_state", {})
    logs = []

    now = datetime.now(timezone.utc).isoformat()

    # 1. Stuck tickets — DB-backed with escalation tiers
    stuck = await collect_stuck_tickets(tenant_id, parwa_state)
    logs.append({"node": "J1", "technique": "StuckDetector",
                 "duration_ms": 0,
                 "result_summary": f"stuck={len(stuck)} "
                 f"tiers={[(s['escalation_tier'], s['ticket_id']) for s in stuck[:3]]}"})

    # 2. Quota status — DB burn rate
    quota = await collect_quota_status(tenant_id)
    quota_status = list(quota.values())[0].get("status", "healthy") if quota else "unknown"
    logs.append({"node": "J1", "technique": "QuotaMonitor",
                 "duration_ms": 0,
                 "result_summary": f"tiers={list(quota.keys())} status={quota_status}"})

    # 3. Integration health — Real pings + DB history
    integration = await collect_integration_health(tenant_id)
    degraded_count = integration.get("degraded_count", 0)
    logs.append({"node": "J1", "technique": "IntegrationHealth",
                 "duration_ms": 0,
                 "result_summary": f"services={len(integration.get('services', {}))} "
                 f"degraded={degraded_count}"})

    # 4. Policy version (wiki-based, not mock)
    policy = _collect_policy_version(tenant_id)
    logs.append({"node": "J1", "technique": "PolicyWatch",
                 "duration_ms": 0,
                 "result_summary": f"c_entries={policy.get('section_c_entries', 0)}"})

    # 5. Accuracy / Drift detection — DB drift analysis
    drift = await collect_accuracy_drift(tenant_id)
    trend = drift.get("trend_direction", "no_data")
    logs.append({"node": "J1", "technique": "AccuracyDrift",
                 "duration_ms": 0,
                 "result_summary": f"trend={trend} drift={drift.get('drift_detected', False)} "
                 f"severity={drift.get('drift_severity', 'none')}"})

    # 6. Ticket flow metrics — DB aggregation + live PARWA state
    flow = await collect_ticket_flow(tenant_id, parwa_state)
    summary = flow.get("summary", {})
    logs.append({"node": "J1", "technique": "TicketFlow",
                 "duration_ms": 0,
                 "result_summary": f"total={summary.get('total', 0)} "
                 f"auto={summary.get('auto_resolved', 0)} "
                 f"escalated={summary.get('escalated', 0)}"})

    # 7. LLM costs — DB tracking + live session
    llm_costs = await collect_llm_costs(tenant_id)
    live = llm_costs.get("live_session", {})
    logs.append({"node": "J1", "technique": "LLMCostTracker",
                 "duration_ms": 0,
                 "result_summary": f"calls={llm_costs.get('total_calls_combined', 0)} "
                 f"cost=${llm_costs.get('total_cost_usd', 0):.4f}"})

    # 8. Load balancing — DB variant concurrency
    load = await collect_load_status(tenant_id)
    vip_risk = load.get("vip_overflow_risk", False)
    logs.append({"node": "J1", "technique": "LoadBalancer",
                 "duration_ms": 0,
                 "result_summary": f"variants={len(load.get('variants', []))} "
                 f"vip_risk={vip_risk}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis SENSE (Wave 2) complete: tenant=%s stuck=%d drift=%s cost=$%.4f [%dms]",
                tenant_id, len(stuck), trend,
                llm_costs.get("total_cost_usd", 0), elapsed)

    signals = {
        # Original signals (enhanced)
        "stuck_tickets": stuck,
        "quota_status": quota,
        "integration_health": integration,
        "policy_version": policy,
        "accuracy_trend": trend,
        "ticket_flow": flow,
        # Wave 2 new signals
        "drift_status": drift,
        "llm_costs": llm_costs,
        "load_status": load,
    }

    return {
        "timestamp": now,
        "signals": signals,
        "sense_log": logs,
        "errors": state.get("errors", []),
    }