"""
Jarvis Node 2: EVALUATE (Think) — Wave 2: Real Data Evaluation

Purpose: Make sense of signals. Decide what needs attention,
what's noise, and what action to recommend.

Wave 2 additions:
  - Drift severity scoring (warning/critical from DB drift analysis)
  - Escalation tier awareness (12h/24h/48h for stuck tickets)
  - LLM cost awareness in priority scoring
  - Load bottleneck detection
  - Integration degradation with uptime context

Question: Does this MATTER? What should we DO about it?

LLM Cost: 1-2 calls (CoT for complex eval, Reflexion before sending)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.parwa_pipeline.llm_client import llm_call

logger = logging.getLogger("jarvis.evaluate")

# ── Priority Scoring Formula (Roadmap Section 5) ─────────────

def _score_priority(
    impact: float,
    urgency: float,
    trend: float,
    admin_preference: float,
    frequency: float,
) -> float:
    """Weighted average priority score.
    CRITICAL > 0.85, HIGH 0.65-0.85, MEDIUM 0.40-0.65, LOW < 0.40"""
    return (
        impact * 0.30
        + urgency * 0.25
        + trend * 0.20
        + admin_preference * 0.15
        + frequency * 0.10
    )


def _evaluate_stuck_ticket(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a stuck ticket with escalation tier awareness."""
    reason = signal.get("reason", "")
    quality = signal.get("quality_score", 0)
    loops = signal.get("loops_used", 0)
    escalation_tier = signal.get("escalation_tier", "soft_reminder")
    hours_stuck = signal.get("hours_stuck", 0)

    # Impact: based on escalation tier
    if escalation_tier == "critical":
        impact = 0.95
    elif escalation_tier == "backup_alert":
        impact = 0.85
    else:  # soft_reminder
        impact = 0.7 if reason == "super_node_escalated" else 0.6

    # Urgency: based on quality score
    if isinstance(quality, (int, float)):
        if quality < 0.7:
            urgency = 0.95
        elif quality < 0.85:
            urgency = 0.75
        else:
            urgency = 0.4
    else:
        urgency = 0.7  # unknown quality → moderate urgency

    # Trend: based on hours stuck + loops
    if hours_stuck >= 48 or loops >= 3:
        trend = 0.95
    elif hours_stuck >= 24 or loops >= 2:
        trend = 0.7
    elif hours_stuck >= 12 or loops >= 1:
        trend = 0.5
    else:
        trend = 0.3

    # Frequency: more stuck tickets = higher priority
    frequency = 0.5  # default, could aggregate from DB

    admin_preference = 0.5
    priority = _score_priority(impact, urgency, trend, admin_preference, frequency)

    return {
        "type": "stuck_ticket",
        "signal": signal,
        "scores": {
            "impact": impact,
            "urgency": urgency,
            "trend": trend,
            "admin_preference": admin_preference,
            "frequency": frequency,
        },
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "stuck_ticket", escalation_tier),
        "related_tickets": [signal.get("ticket_id", "")],
        "escalation_tier": escalation_tier,
    }


def _evaluate_quota(signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate quota with trend context."""
    for tier, data in signal.items():
        if not isinstance(data, dict):
            continue
        burn_pct = data.get("burn_pct", 0)
        status = data.get("status", "healthy")

        if status == "critical":
            impact = 0.8
            urgency = 0.9
        elif status == "warning":
            impact = 0.5
            urgency = 0.6
        else:
            return None  # Healthy — skip

        priority = _score_priority(impact, urgency, 0.5, 0.5, 0.5)
        return {
            "type": "quota_low",
            "signal": {tier: data},
            "scores": {"impact": impact, "urgency": urgency, "trend": 0.5,
                       "admin_preference": 0.5, "frequency": 0.5},
            "priority_score": round(priority, 4),
            "recommendation": _recommendation(priority, "quota_low"),
            "related_tickets": [],
        }
    return None


def _evaluate_drift(drift_status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Wave 2: Evaluate drift from DB drift analysis.

    Uses real drift_severity (warning/critical) and trigger_reason.
    """
    if not drift_status.get("drift_detected"):
        return None

    severity = drift_status.get("drift_severity", "none")
    trigger = drift_status.get("trigger_reason", "unknown")

    if severity == "critical":
        impact = 0.9
        urgency = 0.85
    elif severity == "warning":
        impact = 0.7
        urgency = 0.7
    else:
        return None

    # Trend is already determined by drift analysis
    trend = 0.8 if severity == "critical" else 0.6

    priority = _score_priority(impact, urgency, trend, 0.6, 0.6)

    return {
        "type": "accuracy_drop",
        "signal": {
            "trend": drift_status.get("trend_direction", "unknown"),
            "severity": severity,
            "trigger": trigger,
            "accuracy_7d": drift_status.get("accuracy_7d"),
            "accuracy_today": drift_status.get("accuracy_today"),
        },
        "scores": {"impact": impact, "urgency": urgency, "trend": trend,
                   "admin_preference": 0.6, "frequency": 0.6},
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "accuracy_drop"),
        "related_tickets": [],
        "drift_severity": severity,
    }


def _evaluate_integration(health: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Wave 2: Evaluate integration health with uptime context."""
    services = health.get("services", {})
    degraded = [(name, info) for name, info in services.items()
                if info.get("status") != "healthy"]

    if not degraded:
        return None

    # Deeper evaluation with uptime data
    worst_uptime = 100.0
    any_down = False
    degraded_details = []
    for name, info in degraded:
        uptime = info.get("uptime_pct", 0)
        worst_uptime = min(worst_uptime, uptime)
        if info.get("status") == "down":
            any_down = True
        degraded_details.append({
            "name": name,
            "status": info.get("status"),
            "uptime_pct": uptime,
            "avg_response_ms": info.get("avg_response_ms"),
            "last_error": info.get("last_error"),
        })

    impact = 0.85 if any_down else (0.7 if len(degraded) >= 2 else 0.5)
    urgency = 0.9 if any_down else 0.6
    # Trend: lower uptime → higher trend score
    trend = 0.9 if worst_uptime < 50 else (0.7 if worst_uptime < 80 else 0.5)

    priority = _score_priority(impact, urgency, trend, 0.4, 0.5)

    return {
        "type": "integration_down",
        "signal": {
            "degraded_services": degraded_details,
            "worst_uptime_pct": worst_uptime,
            "total_degraded": len(degraded),
        },
        "scores": {"impact": impact, "urgency": urgency, "trend": trend,
                   "admin_preference": 0.4, "frequency": 0.5},
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "integration_down"),
        "related_tickets": [],
    }


def _evaluate_load_status(load: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Wave 2: Evaluate load/bottleneck status."""
    variants = load.get("variants", [])
    vip_risk = load.get("vip_overflow_risk", False)

    at_capacity = [v for v in variants if v.get("status") == "at_capacity"]
    high_load = [v for v in variants if v.get("status") == "high"]

    if not at_capacity and not high_load and not vip_risk:
        return None

    impact = 0.8 if vip_risk else (0.6 if at_capacity else 0.4)
    urgency = 0.9 if vip_risk else (0.7 if at_capacity else 0.5)
    priority = _score_priority(impact, urgency, 0.5, 0.5, 0.5)

    bottleneck_names = [v["name"] for v in at_capacity + high_load]
    return {
        "type": "load_bottleneck",
        "signal": {
            "at_capacity": at_capacity,
            "high_load": high_load,
            "vip_overflow_risk": vip_risk,
        },
        "scores": {"impact": impact, "urgency": urgency, "trend": 0.5,
                   "admin_preference": 0.5, "frequency": 0.5},
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "load_bottleneck"),
        "related_tickets": [],
        "bottleneck_variants": bottleneck_names,
    }


def _recommendation(priority: float, ntype: str, extra: str = "") -> str:
    """Generate a recommendation string based on priority and type."""
    tier_info = f" [Escalation: {extra}]" if extra else ""
    if priority >= 0.85:
        return f"CRITICAL: Immediate attention needed for {ntype}.{tier_info} Notify admin immediately."
    elif priority >= 0.65:
        return f"HIGH: {ntype} needs attention.{tier_info} Include in next notification batch."
    elif priority >= 0.40:
        return f"MEDIUM: {ntype} noted.{tier_info} Batch in digest."
    return f"LOW: {ntype} logged. No notification needed."


# ── LLM-based evaluation for complex situations ──────────────


async def _llm_clarify_signal(signal: Dict, context: Dict) -> str:
    """CLARA: Clarify ambiguous signals before deciding."""
    prompt = f"""A monitoring system detected this signal:
Signal: {signal.get('type', 'unknown')}
Details: {signal}
Context: {context}

Is this a real problem requiring admin attention, or normal fluctuation?
Answer in one sentence: REAL_PROBLEM or NORMAL_FLUCTUATION, then explain why."""

    try:
        result = await llm_call(prompt, max_tokens=80, temperature=0.0)
        return result.strip()
    except Exception as e:
        logger.warning("CLARA call failed: %s", e)
        return "REAL_PROBLEM (CLARA unavailable, erring on side of caution)"


async def _llm_reflexion_check(evaluations: List[Dict], signals: Dict) -> str:
    """Reflexion: Self-critique on evaluation decisions before sending."""
    eval_summary = "\n".join(
        f"- {e['type']}: priority={e['priority_score']} ({e['recommendation']})"
        for e in evaluations
    )
    prompt = f"""Before sending these notifications to an admin, critique each:
{eval_summary}

Context: {signals}

For each, answer: Is this worth notifying? Could it be noise?
One line per evaluation: KEEP or DISMISS, then reason."""

    try:
        result = await llm_call(prompt, max_tokens=150, temperature=0.0)
        return result.strip()
    except Exception as e:
        logger.warning("Reflexion call failed: %s", e)
        return "All KEEP (Reflexion unavailable)"


# ── Main Node Function ────────────────────────────────────────


async def jarvis_evaluate(state: dict) -> dict:
    """Jarvis Node 2: EVALUATE — Think about signals.

    Wave 2: Now evaluates drift_status, load_status, and enhanced
    integration health with uptime context.

    LLM calls: 0-2 (CLARA for ambiguous, Reflexion before sending).
    """
    start = time.time()
    signals = state.get("signals", {})
    logs = []
    llm_calls = 0
    evaluations = []

    # 1. Evaluate stuck tickets (with escalation tiers)
    for stuck in signals.get("stuck_tickets", []):
        ev = _evaluate_stuck_ticket(stuck)
        evaluations.append(ev)
    if signals.get("stuck_tickets"):
        tiers = [s.get("escalation_tier", "?") for s in signals["stuck_tickets"]]
        logs.append({"node": "J2", "technique": "StuckEval",
                     "duration_ms": 0,
                     "result_summary": f"evaluated={len(signals['stuck_tickets'])} "
                     f"tiers={tiers}"})

    # 2. Evaluate quota status
    quota = signals.get("quota_status", {})
    if quota:
        qev = _evaluate_quota(quota)
        if qev:
            evaluations.append(qev)
        logs.append({"node": "J2", "technique": "QuotaEval",
                     "duration_ms": 0,
                     "result_summary": f"status={list(quota.values())[0].get('status', '?') if quota else 'N/A'}"})

    # 3. Evaluate accuracy/drift (Wave 2: from DB drift analysis)
    drift_status = signals.get("drift_status", {})
    dev = _evaluate_drift(drift_status)
    if dev:
        evaluations.append(dev)
        logs.append({"node": "J2", "technique": "DriftEval",
                     "duration_ms": 0,
                     "result_summary": f"drift={drift_status.get('drift_detected')} "
                     f"severity={drift_status.get('drift_severity', 'none')}"})

    # 4. Evaluate integration health (Wave 2: with uptime context)
    health = signals.get("integration_health", {})
    iev = _evaluate_integration(health)
    if iev:
        evaluations.append(iev)
        degraded = [name for name, info in health.get("services", {}).items()
                    if info.get("status") != "healthy"]
        logs.append({"node": "J2", "technique": "IntegrationEval",
                     "duration_ms": 0,
                     "result_summary": f"degraded={degraded}"})

    # 5. Evaluate load status (Wave 2: new)
    load = signals.get("load_status", {})
    lev = _evaluate_load_status(load)
    if lev:
        evaluations.append(lev)
        logs.append({"node": "J2", "technique": "LoadEval",
                     "duration_ms": 0,
                     "result_summary": f"vip_risk={load.get('vip_overflow_risk')} "
                     f"variants={len(load.get('variants', []))}"})

    # 6. CLARA: If ambiguous signals, use LLM to clarify (1 call)
    ambiguous = [e for e in evaluations if 0.50 <= e["priority_score"] <= 0.70]
    clara_result = ""
    if ambiguous and state.get("trigger") == "poll":
        clara_result = await _llm_clarify_signal(
            ambiguous[0]["signal"],
            {"other_evaluations": len(evaluations)},
        )
        llm_calls += 1
        logs.append({"node": "J2", "technique": "CLARA",
                     "duration_ms": 0,
                     "result_summary": f"clarified={len(ambiguous)}"})

    # 7. Reflexion: Self-critique before sending (1 call)
    reflexion_result = ""
    notifiable = [e for e in evaluations if e["priority_score"] >= 0.40]
    if notifiable and state.get("trigger") == "poll":
        reflexion_result = await _llm_reflexion_check(notifiable, signals)
        llm_calls += 1
        logs.append({"node": "J2", "technique": "Reflexion",
                     "duration_ms": 0,
                     "result_summary": f"checked={len(notifiable)}"})

    # 8. FederatedReasoning: Aggregate all scores
    if evaluations:
        avg_priority = sum(e["priority_score"] for e in evaluations) / len(evaluations)
        max_priority = max(e["priority_score"] for e in evaluations)
    else:
        avg_priority = 0.0
        max_priority = 0.0

    logs.append({"node": "J2", "technique": "FederatedReasoning",
                 "duration_ms": 0,
                 "result_summary": f"avg={avg_priority:.3f} max={max_priority:.3f}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis EVALUATE (Wave 2) complete: tenant=%s evals=%d llm=%d [%dms]",
                state.get("tenant_id", ""), len(evaluations), llm_calls, elapsed)

    return {
        "evaluations": evaluations,
        "clara_result": clara_result,
        "reflexion_result": reflexion_result,
        "priority_scores": {
            "average": round(avg_priority, 4),
            "max": round(max_priority, 4),
            "notifiable_count": len(notifiable),
        },
        "evaluation_log": logs,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }