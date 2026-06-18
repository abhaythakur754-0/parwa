"""
Jarvis Node 1: SENSE (Observe)

Purpose: Monitor everything. Collect signals from PARWA pipeline,
variants, integrations, and knowledge base.

Question: What is happening RIGHT NOW?

LLM Cost: 0 calls (pure monitoring, data collection only)
Techniques: SmartRouter, DynamicContext, ZeroShotValidator, MetaLearner
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.parwa_pipeline.nodes.node_2_smart_route import MOCK_VARIANT_REGISTRY, TIER_ORDER
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
from app.core.parwa_pipeline.llm_client import get_stats as get_llm_stats

logger = logging.getLogger("jarvis.sense")


def _collect_stuck_tickets(parwa_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect stuck/unsolved tickets from PARWA pipeline state."""
    stuck = []
    status = parwa_state.get("status", "")
    ticket_id = parwa_state.get("ticket_id", "")
    errors = parwa_state.get("errors", [])
    quality = parwa_state.get("quality_score", 1.0)
    loops = parwa_state.get("loop_count", 0)
    escalated = bool(parwa_state.get("escalation_context"))

    # Ticket is stuck if:
    # 1. Escalated from Super Node (quality too low after all attempts)
    # 2. Has errors that prevented resolution
    # 3. Status is not "resolved"
    if escalated:
        stuck.append({
            "ticket_id": ticket_id,
            "reason": "super_node_escalated",
            "quality_score": quality,
            "loops_used": loops,
            "errors": [str(e) for e in errors],
        })
    elif status == "escalated":
        stuck.append({
            "ticket_id": ticket_id,
            "reason": "pipeline_escalated",
            "quality_score": quality,
            "loops_used": loops,
            "errors": [str(e) for e in errors],
        })
    elif errors and status != "resolved":
        stuck.append({
            "ticket_id": ticket_id,
            "reason": "pipeline_errors",
            "quality_score": quality,
            "loops_used": loops,
            "errors": [str(e) for e in errors[-3:]],  # last 3 errors
        })

    return stuck


def _collect_quota_status(tenant_id: str) -> Dict[str, Any]:
    """Collect quota usage from variant registry."""
    quota = {}
    reg = MOCK_VARIANT_REGISTRY.get(tenant_id, {})
    tier = reg.get("tier", "parwa")
    remaining = reg.get("quota_remaining", 0)
    total = reg.get("quota_total", 0)

    quota[tier] = {
        "remaining": remaining,
        "total": total,
        "used": total - remaining,
        "burn_pct": round((total - remaining) / max(total, 1) * 100, 1),
    }

    # Calculate burn rate (rough: if >80% used, flag it)
    if quota[tier]["burn_pct"] >= 80:
        quota[tier]["status"] = "critical"
    elif quota[tier]["burn_pct"] >= 60:
        quota[tier]["status"] = "warning"
    else:
        quota[tier]["status"] = "healthy"

    return quota


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


def _collect_ticket_flow(parwa_state: Dict[str, Any]) -> Dict[str, Any]:
    """Collect ticket flow metrics from the current PARWA state."""
    tech_log = parwa_state.get("technique_log", [])
    nodes_reached = set()
    for entry in tech_log:
        node_num = entry.get("node")
        if node_num:
            nodes_reached.add(node_num)

    return {
        "ticket_id": parwa_state.get("ticket_id", ""),
        "ticket_type": parwa_state.get("ticket_type", ""),
        "complexity": parwa_state.get("complexity", ""),
        "action": parwa_state.get("required_action", ""),
        "nodes_reached": sorted(nodes_reached),
        "node_count": len(nodes_reached),
        "llm_calls": parwa_state.get("total_token_usage", 0),
        "status": parwa_state.get("status", ""),
        "quality_score": parwa_state.get("quality_score", "N/A"),
    }


def _collect_integration_health() -> Dict[str, str]:
    """Check integration health. Mock for now — real version checks UCB."""
    return {
        "sendgrid": "healthy",
        "twilio": "healthy",
        "hubspot": "healthy",
        "stripe": "healthy",
    }


def _detect_accuracy_trend(parwa_state: Dict[str, Any]) -> str:
    """Detect accuracy trend from wiki patterns."""
    try:
        wiki = get_wiki_store()
        patterns = wiki.find_similar_patterns(
            tenant_id=parwa_state.get("tenant_id", ""),
            query=parwa_state.get("query", ""),
            ticket_type=parwa_state.get("ticket_type", ""),
            max_results=5,
        )
        if not patterns:
            return "no_historical_data"

        avg_quality = sum(p["quality_achieved"] for p in patterns) / len(patterns)
        if avg_quality >= 0.95:
            return "excellent"
        elif avg_quality >= 0.90:
            return "stable"
        elif avg_quality >= 0.80:
            return "declining"
        else:
            return "critical"
    except Exception:
        return "unknown"


# ── Main Node Function ────────────────────────────────────────


async def jarvis_sense(state: dict) -> dict:
    """Jarvis Node 1: SENSE — Observe all signals.

    LLM calls: 0 (pure data collection).
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    trigger = state.get("trigger", "poll")
    parwa_state = state.get("parwa_state", {})
    logs = []

    now = datetime.now(timezone.utc).isoformat()

    # 1. Collect stuck tickets
    stuck = _collect_stuck_tickets(parwa_state)
    logs.append({"node": "J1", "technique": "StuckDetector", "duration_ms": 0,
                 "result_summary": f"stuck={len(stuck)}"})

    # 2. Collect quota status
    quota = _collect_quota_status(tenant_id)
    logs.append({"node": "J1", "technique": "QuotaMonitor", "duration_ms": 0,
                 "result_summary": f"tiers={list(quota.keys())}"})

    # 3. Collect integration health
    integration = _collect_integration_health()
    degraded = [k for k, v in integration.items() if v != "healthy"]
    logs.append({"node": "J1", "technique": "IntegrationHealth", "duration_ms": 0,
                 "result_summary": f"degraded={len(degraded)}"})

    # 4. Check policy version
    policy = _collect_policy_version(tenant_id)
    logs.append({"node": "J1", "technique": "PolicyWatch", "duration_ms": 0,
                 "result_summary": f"c_entries={policy.get('section_c_entries', 0)}"})

    # 5. Detect accuracy trend
    trend = _detect_accuracy_trend(parwa_state)
    logs.append({"node": "J1", "technique": "AccuracyTrend", "duration_ms": 0,
                 "result_summary": f"trend={trend}"})

    # 6. Ticket flow metrics
    flow = _collect_ticket_flow(parwa_state)
    logs.append({"node": "J1", "technique": "TicketFlow", "duration_ms": 0,
                 "result_summary": f"nodes={flow['node_count']}"})

    # 7. LLM usage stats
    llm_stats = get_llm_stats()
    logs.append({"node": "J1", "technique": "LLMMonitor", "duration_ms": 0,
                 "result_summary": f"calls={llm_stats['total_calls']}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis SENSE complete: tenant=%s stuck=%d trend=%s [%dms]",
                tenant_id, len(stuck), trend, elapsed)

    signals = {
        "stuck_tickets": stuck,
        "quota_status": quota,
        "integration_health": integration,
        "policy_version": policy,
        "accuracy_trend": trend,
        "ticket_flow": flow,
        "llm_stats": llm_stats,
    }

    return {
        "timestamp": now,
        "signals": signals,
        "sense_log": logs,
        "errors": state.get("errors", []),
    }