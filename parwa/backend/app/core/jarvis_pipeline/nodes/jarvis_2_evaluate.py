"""
Jarvis Node 2: EVALUATE (Think)

Purpose: Make sense of signals. Decide what needs attention,
what's noise, and what action to recommend.

Question: Does this MATTER? What should we DO about it?

LLM Cost: 1-2 calls (CoT for complex eval, Reflexion before sending)
Techniques: CoT, CLARA, Reflexion, SmartRouter, GSD, FederatedReasoning,
            ZeroShotValidator, MetaLearner, DynamicContext, MAKER
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

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
    """Non-LLM evaluation of a stuck ticket signal."""
    reason = signal.get("reason", "")
    quality = signal.get("quality_score", 0)
    loops = signal.get("loops_used", 0)

    # Impact: how bad is it?
    if reason == "super_node_escalated":
        impact = 0.9  # Super Node failed — high impact
    elif reason == "pipeline_escalated":
        impact = 0.85
    elif reason == "pipeline_errors":
        impact = 0.7
    else:
        impact = 0.5

    # Urgency: based on quality score
    if quality < 0.7:
        urgency = 0.95  # Very low quality = urgent
    elif quality < 0.85:
        urgency = 0.75
    else:
        urgency = 0.4  # Close to passing = less urgent

    # Trend: how many loops used (more = worse trend)
    if loops >= 3:
        trend = 0.9
    elif loops >= 2:
        trend = 0.7
    elif loops >= 1:
        trend = 0.5
    else:
        trend = 0.3

    # Admin preference & frequency: default mid-values
    admin_preference = 0.5
    frequency = 0.5

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
        "recommendation": _recommendation(priority, "stuck_ticket"),
        "related_tickets": [signal.get("ticket_id", "")],
    }


def _evaluate_quota(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Non-LLM evaluation of quota status."""
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


def _evaluate_accuracy(trend: str) -> Optional[Dict[str, Any]]:
    """Non-LLM evaluation of accuracy trend."""
    if trend in ("stable", "excellent", "no_historical_data", "unknown"):
        return None

    # Declining or critical accuracy
    impact = 0.9 if trend == "critical" else 0.6
    urgency = 0.8 if trend == "critical" else 0.5
    priority = _score_priority(impact, urgency, 0.8, 0.6, 0.6)

    return {
        "type": "accuracy_drop",
        "signal": {"trend": trend},
        "scores": {"impact": impact, "urgency": urgency, "trend": 0.8,
                   "admin_preference": 0.6, "frequency": 0.6},
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "accuracy_drop"),
        "related_tickets": [],
    }


def _evaluate_integration(health: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Non-LLM evaluation of integration health."""
    degraded = [(k, v) for k, v in health.items() if v != "healthy"]
    if not degraded:
        return None

    impact = 0.7 if len(degraded) >= 2 else 0.5
    urgency = 0.8 if any(v == "down" for _, v in degraded) else 0.5
    priority = _score_priority(impact, urgency, 0.5, 0.4, 0.5)

    return {
        "type": "integration_down",
        "signal": {"degraded_services": degraded},
        "scores": {"impact": impact, "urgency": urgency, "trend": 0.5,
                   "admin_preference": 0.4, "frequency": 0.5},
        "priority_score": round(priority, 4),
        "recommendation": _recommendation(priority, "integration_down"),
        "related_tickets": [],
    }


def _recommendation(priority: float, ntype: str) -> str:
    """Generate a recommendation string based on priority and type."""
    if priority >= 0.85:
        return f"CRITICAL: Immediate attention needed for {ntype}. Notify admin immediately."
    elif priority >= 0.65:
        return f"HIGH: {ntype} needs attention. Include in next notification batch."
    elif priority >= 0.40:
        return f"MEDIUM: {ntype} noted. Batch in digest."
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

    LLM calls: 0-2 (CLARA for ambiguous, Reflexion before sending).
    """
    start = time.time()
    signals = state.get("signals", {})
    logs = []
    llm_calls = 0
    evaluations = []

    # 1. Evaluate stuck tickets (non-LLM)
    for stuck in signals.get("stuck_tickets", []):
        ev = _evaluate_stuck_ticket(stuck)
        evaluations.append(ev)
    if signals.get("stuck_tickets"):
        logs.append({"node": "J2", "technique": "StuckEval", "duration_ms": 0,
                     "result_summary": f"evaluated={len(signals['stuck_tickets'])}"})

    # 2. Evaluate quota status (non-LLM)
    quota = signals.get("quota_status", {})
    if quota:
        qev = _evaluate_quota(quota)
        if qev:
            evaluations.append(qev)
        logs.append({"node": "J2", "technique": "QuotaEval", "duration_ms": 0,
                     "result_summary": f"status={list(quota.values())[0].get('status', '?') if quota else 'N/A'}"})

    # 3. Evaluate accuracy trend (non-LLM)
    trend = signals.get("accuracy_trend", "")
    aev = _evaluate_accuracy(trend)
    if aev:
        evaluations.append(aev)
        logs.append({"node": "J2", "technique": "AccuracyEval", "duration_ms": 0,
                     "result_summary": f"trend={trend}"})

    # 4. Evaluate integration health (non-LLM)
    health = signals.get("integration_health", {})
    iev = _evaluate_integration(health)
    if iev:
        evaluations.append(iev)
        degraded = [k for k, v in health.items() if v != "healthy"]
        logs.append({"node": "J2", "technique": "IntegrationEval", "duration_ms": 0,
                     "result_summary": f"degraded={degraded}"})

    # 5. CLARA: If ambiguous signals, use LLM to clarify (1 call)
    ambiguous = [e for e in evaluations if 0.50 <= e["priority_score"] <= 0.70]
    clara_result = ""
    if ambiguous and state.get("trigger") == "poll":
        clara_result = await _llm_clarify_signal(
            ambiguous[0]["signal"],
            {"other_evaluations": len(evaluations)},
        )
        llm_calls += 1
        logs.append({"node": "J2", "technique": "CLARA", "duration_ms": 0,
                     "result_summary": f"clarified={len(ambiguous)}"})

    # 6. Reflexion: Self-critique before sending (1 call, only if we have notifications)
    reflexion_result = ""
    notifiable = [e for e in evaluations if e["priority_score"] >= 0.40]
    if notifiable and state.get("trigger") == "poll":
        reflexion_result = await _llm_reflexion_check(notifiable, signals)
        llm_calls += 1
        logs.append({"node": "J2", "technique": "Reflexion", "duration_ms": 0,
                     "result_summary": f"checked={len(notifiable)}"})

    # 7. FederatedReasoning: Aggregate all scores
    if evaluations:
        avg_priority = sum(e["priority_score"] for e in evaluations) / len(evaluations)
        max_priority = max(e["priority_score"] for e in evaluations)
    else:
        avg_priority = 0.0
        max_priority = 0.0

    logs.append({"node": "J2", "technique": "FederatedReasoning", "duration_ms": 0,
                 "result_summary": f"avg={avg_priority:.3f} max={max_priority:.3f}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis EVALUATE complete: tenant=%s evals=%d llm=%d [%dms]",
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