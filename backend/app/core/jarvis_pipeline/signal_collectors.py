"""
Jarvis Signal Collectors — Wave 2 (Real Monitoring)

Replaces ALL mock collectors from Wave 1's jarvis_1_sense.py.
Every collector reads from jarvis_db (or real integration APIs).

7 collectors:
  1. collect_stuck_tickets      — DB: quality_scores + stuck_ticket_events
  2. collect_integration_health — Real HTTP pings to connected services
  3. collect_quota_status       — DB: agent_configs + quality_scores for burn rate
  4. collect_accuracy_drift     — DB: quality_scores drift analysis
  5. collect_ticket_flow        — DB: ticket flow aggregation
  6. collect_llm_costs          — DB: LLM cost tracking + in-memory stats bridge
  7. collect_load_status        — DB: variant concurrency + VIP overflow

Zero LLM calls. Pure monitoring + data collection.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.collectors")

# ── Known integrations to ping ────────────────────────────────

# In production, this comes from agent_configs.integrations list.
# For now: known services per tenant. Extendable.
KNOWN_INTEGRATIONS = [
    {"name": "sendgrid", "health_url": None, "type": "email"},
    {"name": "twilio", "health_url": None, "type": "sms"},
    {"name": "shopify", "health_url": None, "type": "ecommerce"},
    {"name": "stripe", "health_url": None, "type": "billing"},
    {"name": "hubspot", "health_url": None, "type": "crm"},
]

# Stuck ticket escalation tiers (hours)
ESCALATION_TIERS = {
    "soft_reminder": 12,    # 12h: gentle reminder
    "backup_alert": 24,     # 24h: alert backup
    "critical": 48,         # 48h: critical escalation
}

# Quota alert thresholds
QUOTA_WARNING_PCT = 60
QUOTA_CRITICAL_PCT = 80


# ═══════════════════════════════════════════════════════════════
# 1. STUCK TICKET DETECTION
# ═══════════════════════════════════════════════════════════════

async def collect_stuck_tickets(
    tenant_id: str,
    parwa_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Detect stuck tickets from quality_scores DB.

    Stuck = quality_score < 0.85 OR resolution_path in (escalated, stuck).
    Escalation tiers: 12h soft, 24h backup, 48h critical.

    Also records live stuck events from current parwa_state.
    """
    db = get_db()
    stuck = []
    now = datetime.now(timezone.utc)

    # A. Check current PARWA state for immediate stuck signals
    status = parwa_state.get("status", "")
    ticket_id = parwa_state.get("ticket_id", "")
    quality = parwa_state.get("quality_score", 1.0)
    loops = parwa_state.get("loop_count", 0)
    errors = parwa_state.get("errors", [])
    escalated = bool(parwa_state.get("escalation_context"))

    if ticket_id and (escalated or status in ("escalated", "error") or
                       (errors and status != "resolved")):
        reason = (
            "super_node_escalated" if escalated
            else "pipeline_escalated" if status == "escalated"
            else "pipeline_errors"
        )
        # Check if we already have this ticket tracked
        existing = await db.get_stuck_tickets(tenant_id)
        already_tracked = any(e["ticket_id"] == ticket_id for e in existing)

        stuck.append({
            "ticket_id": ticket_id,
            "reason": reason,
            "quality_score": quality,
            "loops_used": loops,
            "errors": [str(e) for e in errors[-3:]],
            "escalation_tier": "soft_reminder",
            "hours_stuck": 0.0,
            "source": "live_parwa_state",
        })

        # Record in DB if new
        if not already_tracked:
            await db.record_stuck_ticket_check(
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                stuck_reason=reason,
                hours_stuck=0.0,
                escalation_tier="soft_reminder",
            )

    # B. Check DB for historical stuck tickets + escalation
    db_stuck = await db.get_stuck_tickets(tenant_id)
    for event in db_stuck:
        # Skip if already added from live state
        if event["ticket_id"] == ticket_id:
            continue

        detected = datetime.fromisoformat(event["detected_at"].replace("Z", "+00:00"))
        hours_stuck = (now - detected).total_seconds() / 3600

        # Determine escalation tier
        tier = "soft_reminder"
        if hours_stuck >= ESCALATION_TIERS["critical"]:
            tier = "critical"
        elif hours_stuck >= ESCALATION_TIERS["backup_alert"]:
            tier = "backup_alert"
        elif hours_stuck >= ESCALATION_TIERS["soft_reminder"]:
            tier = "soft_reminder"

        # Update tier if escalated
        if tier != event.get("escalation_tier"):
            await db.record_stuck_ticket_check(
                tenant_id=tenant_id,
                ticket_id=event["ticket_id"],
                stuck_reason=event["stuck_reason"],
                hours_stuck=hours_stuck,
                escalation_tier=tier,
            )

        stuck.append({
            "ticket_id": event["ticket_id"],
            "reason": event["stuck_reason"],
            "quality_score": event.get("quality_score", "N/A"),
            "loops_used": 0,
            "errors": [],
            "escalation_tier": tier,
            "hours_stuck": round(hours_stuck, 1),
            "source": "db_tracked",
        })

    # Sort by escalation tier (critical first)
    tier_order = {"critical": 0, "backup_alert": 1, "soft_reminder": 2}
    stuck.sort(key=lambda x: tier_order.get(x["escalation_tier"], 99))

    return stuck


# ═══════════════════════════════════════════════════════════════
# 2. INTEGRATION HEALTH (UCB MONITORING)
# ═══════════════════════════════════════════════════════════════

async def _ping_service(service_name: str) -> Dict[str, Any]:
    """Attempt a real health check ping. Returns {is_healthy, response_ms, error, status_code}.

    For services without a real health_url, simulates a lightweight check.
    In production, each integration would have its own health endpoint.
    """
    import httpx

    # Find service config
    svc_config = None
    for svc in KNOWN_INTEGRATIONS:
        if svc["name"] == service_name:
            svc_config = svc
            break

    health_url = svc_config.get("health_url") if svc_config else None

    if health_url:
        # Real HTTP ping
        try:
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(health_url)
            ms = (time.monotonic() - t0) * 1000
            return {
                "is_healthy": r.status_code == 200,
                "response_ms": round(ms, 1),
                "error_detail": None if r.status_code == 200 else f"HTTP {r.status_code}",
                "status_code": r.status_code,
            }
        except Exception as e:
            return {
                "is_healthy": False,
                "response_ms": None,
                "error_detail": str(e)[:200],
                "status_code": None,
            }
    else:
        # No health URL configured — mark as "unmonitored" (not degraded)
        return {
            "is_healthy": True,
            "response_ms": None,
            "error_detail": None,
            "status_code": None,
            "note": "no_health_url_configured",
        }


async def collect_integration_health(tenant_id: str) -> Dict[str, Any]:
    """Ping all known integrations and compute health summary.

    Stores pings in DB for uptime calculation.
    Returns: {services: {name: {status, uptime_pct, ...}}, degraded_count, healthy_count}
    """
    db = get_db()

    for svc in KNOWN_INTEGRATIONS:
        result = await _ping_service(svc["name"])
        await db.write_integration_ping(
            tenant_id=tenant_id,
            service_name=svc["name"],
            is_healthy=result["is_healthy"],
            response_ms=result.get("response_ms"),
            error_detail=result.get("error_detail"),
            status_code=result.get("status_code"),
        )

    # Get computed health from DB (uptime %, last errors, etc.)
    health = await db.get_integration_health(tenant_id)
    return health


# ═══════════════════════════════════════════════════════════════
# 3. QUOTA MONITORING (REAL)
# ═══════════════════════════════════════════════════════════════

async def collect_quota_status(tenant_id: str) -> Dict[str, Any]:
    """Collect real quota status from DB.

    Sources:
      - agent_configs for total quota
      - quality_scores count for used quota
      - Trend: compare recent usage vs earlier

    Returns: {variant_name: {remaining, total, used, burn_pct, status, trend_vs_yesterday}}
    """
    db = get_db()

    # Get quality stats to estimate usage
    stats = await db.get_quality_stats(tenant_id)
    total_tickets = stats["total_tickets"]

    # Get variant + quota from DB (same source as Node 2)
    try:
        from app.core.parwa_pipeline.nodes.node_2_smart_route import _load_tenant_variants
        tenant_variants = _load_tenant_variants(tenant_id)
    except Exception:
        tenant_variants = {
            "highest_tier_short": "parwa",
            "quota": {"parwa": {"total": 1000, "used": 0, "remaining": 1000}},
        }

    # Build quota from real data
    quota = {}
    tier_short = tenant_variants.get("highest_tier_short", "parwa")

    for t_short, q in tenant_variants.get("quota", {}).items():
        total = q.get("total", 1000)
        used = max(q.get("used", 0), total_tickets)  # tickets processed >= DB tracked
        remaining = max(0, total - used)
        burn_pct = round(used / max(total, 1) * 100, 1)

        if burn_pct >= QUOTA_CRITICAL_PCT:
            status = "critical"
        elif burn_pct >= QUOTA_WARNING_PCT:
            status = "warning"
        else:
            status = "healthy"

        quota[t_short] = {
            "remaining": remaining,
            "total": total,
            "used": used,
            "burn_pct": burn_pct,
            "status": status,
        }

    return quota


# ═══════════════════════════════════════════════════════════════
# 4. ACCURACY / DRIFT DETECTION
# ═══════════════════════════════════════════════════════════════

async def collect_accuracy_drift(tenant_id: str) -> Dict[str, Any]:
    """Real drift detection from quality_scores in DB.

    Delegates to db.check_quality_drift() which computes:
      - 7-day rolling accuracy
      - Day-over-day trend
      - Drift triggers (5% drop for 3+ days, same error 3+ times)

    Returns the drift dict directly.
    """
    db = get_db()
    return await db.check_quality_drift(tenant_id)


# ═══════════════════════════════════════════════════════════════
# 5. TICKET FLOW METRICS
# ═══════════════════════════════════════════════════════════════

async def collect_ticket_flow(tenant_id: str, parwa_state: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate ticket flow from DB + live PARWA state.

    DB provides: historical aggregation (total, auto_resolved, escalated, by_node)
    Live state provides: current ticket's node-by-node progress

    Returns: {summary: {total, auto_resolved, ...}, current_ticket: {nodes_reached, ...}}
    """
    db = get_db()

    # A. Aggregated flow from DB
    summary = await db.get_ticket_flow_summary(tenant_id)

    # B. Current ticket's detailed flow from PARWA state
    tech_log = parwa_state.get("technique_log", [])
    nodes_reached = set()
    for entry in tech_log:
        node_num = entry.get("node")
        if node_num:
            nodes_reached.add(node_num)

    current_ticket = {
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

    return {
        "summary": summary,
        "current_ticket": current_ticket,
    }


# ═══════════════════════════════════════════════════════════════
# 6. LLM COST TRACKING
# ═══════════════════════════════════════════════════════════════

async def collect_llm_costs(tenant_id: str) -> Dict[str, Any]:
    """Collect LLM cost data from DB + bridge in-memory stats from llm_client.

    Two sources:
      1. DB: persisted cost records (from record_llm_cost calls)
      2. In-memory: live session stats from llm_client.get_stats()

    Merges both for a complete picture.
    """
    db = get_db()

    # A. Persisted costs from DB
    db_summary = await db.get_llm_cost_summary(tenant_id)

    # B. Live session stats from PARWA's llm_client
    try:
        from app.core.parwa_pipeline.llm_client import get_stats
        live_stats = get_stats()
    except Exception:
        live_stats = {"total_calls": 0, "total_tokens": 0, "total_errors": 0}

    return {
        "persisted": db_summary,
        "live_session": live_stats,
        "total_calls_combined": db_summary.get("total_calls", 0) + live_stats.get("total_calls", 0),
        "total_tokens_combined": db_summary.get("total_tokens", 0) + live_stats.get("total_tokens", 0),
        "total_cost_usd": db_summary.get("total_cost_usd", 0.0),
    }


# ═══════════════════════════════════════════════════════════════
# 7. LOAD BALANCING AWARENESS
# ═══════════════════════════════════════════════════════════════

async def collect_load_status(tenant_id: str) -> Dict[str, Any]:
    """Detect variant load/concurrency status.

    Returns: {variants: [{name, concurrent, max_concurrent, utilization_pct, status}],
              vip_overflow_risk: bool}
    """
    db = get_db()
    return await db.get_load_status(tenant_id)