"""
Jarvis SLA Calculator — Wave 6E: Uptime Tracking & Credit Computation

Tracks actual uptime vs SLA target. Computes SLA credits.
Per-client SLA config from jarvis_db.

Features:
  - Uptime event recording (downtime_start, downtime_end)
  - SLA status computation (meeting / at_risk / breached)
  - Monthly SLA report generation
  - Credit calculation (10% monthly fee per 1% below target)

Zero new dependencies. Zero LLM calls.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.sla")

# ── SLA Constants ──────────────────────────────────────────────

DEFAULT_TARGET_UPTIME = 99.5  # percent
CREDIT_RATE = 0.10  # 10% of monthly fee per 1% downtime below target


# ═══════════════════════════════════════════════════════════════
# CORE SLA FUNCTIONS
# ═══════════════════════════════════════════════════════════════


async def compute_sla_status(
    tenant_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """Compute full SLA status for a tenant.

    Returns:
        {
            "tenant_id": str,
            "period_days": int,
            "target_uptime_pct": float,
            "actual_uptime_pct": float,
            "uptime_gap_pct": float,
            "total_downtime_seconds": float,
            "incident_count": int,
            "credit_owed_usd": float,
            "sla_status": str (meeting/at_risk/breached),
            "recommendation": str,
            "config": {...},
        }
    """
    db = get_db()

    # 1. Get SLA summary from DB (uptime computation + alerts)
    sla = await db.get_sla_summary(tenant_id, days=days)

    target = sla.get("target_uptime_pct", DEFAULT_TARGET_UPTIME)
    actual = sla.get("actual_uptime_pct", 100.0)
    gap = target - actual
    incidents = sla.get("incident_count", 0)
    downtime = sla.get("total_downtime_seconds", 0)
    credit = sla.get("credit_owed", 0.0)
    monthly_fee = sla.get("monthly_fee", 0.0)
    config = await db.get_client_legal_config(tenant_id)

    # 2. Determine SLA status
    if actual >= target:
        status = "meeting"
    elif gap <= 0.5:
        status = "at_risk"
    else:
        status = "breached"

    # 3. Build recommendation
    recommendation = _sla_recommendation(status, actual, target, gap, incidents, credit)

    result = {
        "tenant_id": tenant_id,
        "period_days": days,
        "target_uptime_pct": target,
        "actual_uptime_pct": round(actual, 2),
        "uptime_gap_pct": round(max(0, gap), 2),
        "total_downtime_seconds": round(downtime, 1),
        "incident_count": incidents,
        "credit_owed_usd": round(credit, 2),
        "sla_status": status,
        "recommendation": recommendation,
        "config": config,
    }

    logger.info("SLA status: tenant=%s actual=%.2f%% target=%.2f%% status=%s",
                tenant_id, actual, target, status)

    return result


async def generate_monthly_sla_report(tenant_id: str) -> Dict[str, Any]:
    """Generate a comprehensive monthly SLA report.

    Combines SLA data with integration health for a full picture.

    Returns:
        {
            "report_type": "monthly_sla",
            "tenant_id": str,
            "sla_status": {...},
            "integration_health": {...},
            "incidents_summary": str,
            "credit_summary": str,
            "recommendations": [...],
            "generated_at": str,
        }
    """
    db = get_db()

    # 1. SLA status
    sla = await compute_sla_status(tenant_id, days=30)

    # 2. Integration health
    health = await db.get_integration_health(tenant_id)

    # 3. Build incident summary
    incidents = sla.get("incident_count", 0)
    downtime = sla.get("total_downtime_seconds", 0)
    hours_down = round(downtime / 3600, 2)

    if incidents == 0:
        incidents_summary = "No downtime incidents in this period. All services operational."
    else:
        incidents_summary = (
            f"{incidents} downtime incident(s) totaling {hours_down} hours. "
            f"Degraded services: {sla.get('degraded_services', 'none')}."
        )

    # 4. Credit summary
    credit = sla.get("credit_owed_usd", 0)
    if credit > 0:
        credit_summary = (
            f"SLA credit owed: ${credit:.2f} "
            f"(actual uptime {sla['actual_uptime_pct']:.2f}% vs target {sla['target_uptime_pct']:.2f}%). "
            f"Credit will be applied to next billing cycle."
        )
    else:
        credit_summary = "No SLA credits owed. Uptime target is being met."

    # 5. Recommendations
    recommendations = _sla_report_recommendations(sla, health)

    report = {
        "report_type": "monthly_sla",
        "tenant_id": tenant_id,
        "sla_status": sla,
        "integration_health": health,
        "incidents_summary": incidents_summary,
        "credit_summary": credit_summary,
        "recommendations": recommendations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save
    await db.save_generated_report(tenant_id, "monthly_sla", report)

    logger.info("Monthly SLA report: tenant=%s status=%s credit=$%.2f",
                tenant_id, sla.get("sla_status"), credit)

    return report


async def record_uptime_event(
    tenant_id: str,
    event_type: str,
    duration_seconds: float = 0,
    details: str = "",
) -> Dict[str, Any]:
    """Record an uptime/downtime event.

    event_type: "uptime_start", "uptime_end", "downtime_start", "downtime_end"

    Returns the recorded event.
    """
    db = get_db()
    event = await db.record_sla_event(
        tenant_id=tenant_id,
        event_type=event_type,
        duration_seconds=duration_seconds,
        details=details,
    )
    return event


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _sla_recommendation(
    status: str, actual: float, target: float,
    gap: float, incidents: int, credit: float,
) -> str:
    """Generate an SLA recommendation string."""
    if status == "meeting":
        return (f"Uptime is meeting the {target}% SLA target (actual: {actual:.2f}%). "
                f"No action needed. Continue monitoring.")
    elif status == "at_risk":
        return (f"Uptime is {gap:.2f}% below the {target}% SLA target. "
                f"Review recent incidents and ensure monitoring is active. "
                f"If trend continues, SLA breach may occur.")
    else:
        return (f"SLA BREACHED: Uptime is {actual:.2f}% vs {target}% target. "
                f"Credit owed: ${credit:.2f}. "
                f"Immediate action required to restore service stability.")


def _sla_report_recommendations(
    sla: Dict[str, Any],
    health: Dict[str, Any],
) -> list:
    """Build monthly SLA report recommendations."""
    recs = []
    status = sla.get("sla_status", "meeting")

    if status == "breached":
        recs.append({
            "priority": "critical",
            "text": ("SLA breached. Conduct a post-mortem on all downtime incidents. "
                     "Identify root causes and implement preventive measures."),
        })

    if status in ("at_risk", "breached"):
        recs.append({
            "priority": "high",
            "text": ("Set up redundant health checks and consider adding a secondary "
                     "monitoring service to catch issues faster."),
        })

    # Check for degraded integrations
    degraded = health.get("degraded_count", 0)
    if degraded > 0:
        recs.append({
            "priority": "high" if degraded >= 2 else "medium",
            "text": (f"{degraded} integration(s) degraded. "
                     f"Review service health and consider failover configurations."),
        })

    # General recommendation
    actual = sla.get("actual_uptime_pct", 100)
    if actual >= 99.9:
        recs.append({
            "priority": "low",
            "text": ("Excellent uptime. Consider documenting your reliability practices "
                     "for client reporting and marketing."),
        })

    if not recs:
        recs.append({
            "priority": "low",
            "text": "All systems operational. No action needed.",
        })

    return recs