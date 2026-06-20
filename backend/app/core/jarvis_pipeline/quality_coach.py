"""
Jarvis Quality Coach — Wave 6C + 6D: Drift Alerts & Quality Reports

Provides:
  6C: Automated drift detection with alert creation
  6D: Weekly quality report, mistake analysis, training priority, agent health score

All data from jarvis_db. Zero LLM calls.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.quality_coach")


# ═══════════════════════════════════════════════════════════════
# 6D: QUALITY COACH REPORTS
# ═══════════════════════════════════════════════════════════════


async def generate_weekly_quality_report(
    tenant_id: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Generate a comprehensive weekly quality report.

    Combines health score, performance, mistakes, and trends into
    one actionable report.

    Returns:
        {
            "report_type": "weekly_quality",
            "tenant_id": str,
            "health_score": {...},
            "performance": {...},
            "mistakes": {...},
            "confidence_trend": {...},
            "recommendations": [...],
            "period_days": int,
        }
    """
    db = get_db()

    # 1. Agent health score
    health = await db.compute_agent_health_score(tenant_id)

    # 2. Weekly performance
    perf = await db.get_weekly_performance_data(tenant_id, days=days)

    # 3. Mistake analysis
    mistakes = await db.get_mistake_breakdown(tenant_id, days)

    # 4. Confidence trends
    conf = await db.get_confidence_trends(tenant_id, days)

    # 5. Build recommendations from the data
    recommendations = _build_recommendations(health, perf, mistakes, conf)

    report = {
        "report_type": "weekly_quality",
        "tenant_id": tenant_id,
        "health_score": health,
        "performance": perf,
        "mistakes": mistakes,
        "confidence_trend": conf,
        "recommendations": recommendations,
        "period_days": days,
    }

    # Save
    await db.save_generated_report(tenant_id, "weekly_quality", report)

    logger.info("Weekly quality report: tenant=%s health=%.2f grade=%s",
                tenant_id, health.get("health_score", 0), health.get("grade", "?"))

    return report


async def generate_mistake_analysis(
    tenant_id: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Generate a detailed mistake analysis.

    Enriches the DB breakdown with:
    - Most common mistake type
    - Improvement suggestions per type

    Returns:
        {
            "total_mistakes": int,
            "mistake_rate": float,
            "error_types": {type: count},
            "examples": [...],
            "most_common_mistake": str or None,
            "improvement_suggestions": [...],
        }
    """
    db = get_db()
    breakdown = await db.get_mistake_breakdown(tenant_id, days)

    error_types = breakdown.get("error_types", {})
    examples = breakdown.get("examples", [])

    # Most common mistake
    most_common = None
    most_count = 0
    for etype, count in error_types.items():
        if count > most_count:
            most_count = count
            most_common = etype

    # Generate suggestions
    suggestions = []
    for etype, count in sorted(error_types.items(), key=lambda x: -x[1]):
        if count >= 3:
            suggestions.append({
                "area": etype,
                "count": count,
                "suggestion": (
                    f"Add approved training examples for '{etype}' tickets. "
                    f"Current rejection rate is high ({count} in {days} days). "
                    f"Review the examples below and approve correct responses to improve."
                ),
                "priority": "high" if count >= 5 else "medium",
            })
        elif count >= 1:
            suggestions.append({
                "area": etype,
                "count": count,
                "suggestion": (
                    f"Monitor '{etype}' tickets. {count} low-quality resolution "
                    f"in {days} days. May need policy clarification."
                ),
                "priority": "low",
            })

    result = {
        **breakdown,
        "most_common_mistake": most_common,
        "improvement_suggestions": suggestions,
    }

    logger.info("Mistake analysis: tenant=%s total=%d most_common=%s",
                tenant_id, breakdown.get("total_mistakes", 0), most_common)

    return result


async def generate_training_priority_list(
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Generate a ranked training priority list.

    Enriches DB data with suggested_action per item.

    Returns:
        [{ticket_type, rejection_count, accuracy_pct, priority_rank, suggested_action}]
    """
    db = get_db()
    priorities = await db.get_training_priority_list(tenant_id)

    for i, item in enumerate(priorities):
        rank = i + 1
        item["priority_rank"] = rank

        acc = item.get("accuracy_pct", 0)
        rejections = item.get("rejection_count", 0)

        if acc < 0.50:
            item["suggested_action"] = (
                f"CRITICAL: '{item['ticket_type']}' has {acc:.0%} accuracy. "
                f"Add at least 10 approved examples immediately. "
                f"Consider pausing auto-resolve for this type."
            )
        elif acc < 0.75:
            item["suggested_action"] = (
                f"Add 5-10 approved training examples for '{item['ticket_type']}'. "
                f"Current accuracy {acc:.0%} is below target. "
                f"Review rejected examples for patterns."
            )
        elif acc < 0.90:
            item["suggested_action"] = (
                f"Good progress on '{item['ticket_type']}' ({acc:.0%}). "
                f"Add 3-5 more approved examples to push above 90%."
            )
        else:
            item["suggested_action"] = (
                f"'{item['ticket_type']}' is performing well ({acc:.0%}). "
                f"Monitor for drift. No immediate action needed."
            )

    return priorities


def _build_recommendations(
    health: Dict,
    perf: Dict,
    mistakes: Dict,
    conf: Dict,
) -> List[Dict[str, Any]]:
    """Build actionable recommendations from report data.

    Pure computation, no DB/LLM calls.
    """
    recs = []

    # 1. Health score based
    health_score = health.get("health_score", 0)
    grade = health.get("grade", "F")
    if health_score < 0.60:
        recs.append({
            "category": "health",
            "priority": "critical",
            "text": (f"Agent health score is {health_score:.0%} (grade {grade}). "
                     f"Focus on the weakest component first."),
            "weakest_component": health.get("weakest_component", "unknown"),
        })

    # 2. Quality trend based
    trend = perf.get("quality_trend", "stable")
    if trend == "declining":
        recs.append({
            "category": "quality",
            "priority": "high",
            "text": ("Quality is declining. Check for new ticket patterns or "
                     "policy changes that may be causing confusion."),
        })

    # 3. Mistake-based
    total_mistakes = mistakes.get("total_mistakes", 0)
    if total_mistakes > 0:
        most_common = mistakes.get("most_common_mistake", "unknown")
        recs.append({
            "category": "mistakes",
            "priority": "high" if total_mistakes >= 5 else "medium",
            "text": (f"{total_mistakes} mistakes in this period. "
                     f"Most common: '{most_common}'. Add training data."),
        })

    # 4. Confidence-based
    avg_conf = conf.get("avg_confidence", 0)
    if avg_conf < 0.80:
        recs.append({
            "category": "confidence",
            "priority": "medium",
            "text": (f"Average confidence is {avg_conf:.0%}. "
                     f"Low confidence increases manager review burden. "
                     f"Add approved examples to boost confidence."),
        })

    # 5. Auto-resolve rate
    total = perf.get("total_tickets", 0)
    auto = perf.get("auto_resolved", 0)
    if total > 0 and auto / total < 0.60:
        recs.append({
            "category": "efficiency",
            "priority": "medium",
            "text": (f"Only {auto / total:.0%} of tickets are auto-resolved. "
                     f"Review escalation rules and approval gates for optimization."),
        })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recs


# ═══════════════════════════════════════════════════════════════
# 6C: DRIFT DETECTION & ALERTS
# ═══════════════════════════════════════════════════════════════


async def run_drift_check_and_alert(tenant_id: str) -> Dict[str, Any]:
    """Run drift detection and create alerts if needed.

    Combines:
    - Quality drift (from check_quality_drift)
    - Confidence drift (from confidence trends)
    - Error patterns (recurring errors)

    Returns:
        {
            "alerts_created": [...],
            "total_new": int,
            "existing_active": int,
        }
    """
    db = get_db()

    # Delegate to DB which combines all checks
    new_alerts = await db.check_and_create_drift_alerts(tenant_id)

    # Count existing active alerts
    existing = await db.get_quality_alerts(tenant_id, include_resolved=False)
    existing_count = len(existing)

    result = {
        "alerts_created": new_alerts,
        "total_new": len(new_alerts),
        "existing_active": existing_count,
    }

    if new_alerts:
        logger.warning("Drift check created %d alerts for tenant=%s: %s",
                       len(new_alerts), tenant_id,
                       [a.get("alert_type") for a in new_alerts])

    return result


async def get_agent_health_summary(tenant_id: str) -> Dict[str, Any]:
    """Get a comprehensive agent health summary with coaching.

    Returns:
        {
            "health_score": float,
            "grade": str,
            "grade_description": str,
            "components": {...},
            "weakest_component": str,
            "recommendation": str,
        }
    """
    db = get_db()
    health = await db.compute_agent_health_score(tenant_id)

    score = health.get("health_score", 0)
    grade = health.get("grade", "F")
    components = health.get("components", {})

    # Grade descriptions
    grade_desc = {
        "A": "Excellent — AI is performing at a high level across all metrics.",
        "B": "Good — Solid performance with minor areas for improvement.",
        "C": "Fair — Meeting basic expectations but needs attention in key areas.",
        "D": "Poor — Significant gaps detected. Immediate action recommended.",
        "F": "Critical — AI is underperforming. Pause auto-resolve and review.",
    }

    # Find weakest component
    weakest = "unknown"
    weakest_val = 1.0
    for comp_name, comp_val in components.items():
        if isinstance(comp_val, (int, float)) and comp_val < weakest_val:
            weakest_val = comp_val
            weakest = comp_name

    # Build recommendation based on weakest
    rec = _health_recommendation(weakest, weakest_val, score)

    result = {
        **health,
        "grade_description": grade_desc.get(grade, "Unknown grade."),
        "weakest_component": weakest,
        "recommendation": rec,
    }

    logger.info("Agent health: tenant=%s score=%.2f grade=%s weakest=%s",
                tenant_id, score, grade, weakest)

    return result


def _health_recommendation(weakest: str, weakest_val: float, overall: float) -> str:
    """Generate a health improvement recommendation."""
    recs = {
        "accuracy": (
            f"Accuracy is the weakest component ({weakest_val:.0%}). "
            f"Focus on adding approved training examples and reviewing rejected responses. "
            f"Target: improve to at least 85%."
        ),
        "efficiency": (
            f"Auto-resolve rate is low ({weakest_val:.0%}). "
            f"Review approval gates and confidence thresholds. "
            f"Consider auto-approving high-confidence ticket types."
        ),
        "confidence": (
            f"Average confidence is low ({weakest_val:.0%}). "
            f"This means more tickets need human review. "
            f"Add training data to boost pattern matching and policy alignment."
        ),
        "integrations": (
            f"Integration health is the weakest area ({weakest_val:.0%}). "
            f"Check connected services (Shopify, Stripe, etc.) for outages. "
            f"Degraded integrations affect AI's ability to fetch real data."
        ),
    }
    return recs.get(weakest, f"Focus on improving the weakest component ({weakest}: {weakest_val:.0%}).")