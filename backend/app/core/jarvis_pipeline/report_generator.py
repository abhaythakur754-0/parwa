"""
Jarvis Report Generator — Wave 6A + 6B: Weekly Wins & Performance Dashboard

Generates:
  6A: Weekly Wins Report — tickets handled, money saved, skills learned, predictions
  6B: Performance Dashboard Data — volume/accuracy, confidence trends, efficiency, learning

All data from jarvis_db via SQL aggregation. No LLM calls for data collection.
LLM only used for report narrative formatting (optional, in notify node).

Zero new dependencies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.reports")

# ── Cost Assumptions ──────────────────────────────────────────

HUMAN_COST_PER_TICKET = 8.0  # estimated $8/ticket for human handling
MANAGER_REVIEW_MINUTES = 5.0  # estimated 5 min per manual review


# ═══════════════════════════════════════════════════════════════
# 6A: WEEKLY WINS REPORT
# ═══════════════════════════════════════════════════════════════


async def generate_weekly_wins_report(
    tenant_id: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Generate the full weekly wins report.

    Data sources: quality_scores, confidence_logs, training_data, llm_costs.
    Computes money saved, new skills, predictions, top improvements, needs attention.

    Returns:
        {
            "report_type": "weekly_wins",
            "tenant_id": str,
            "period": {"days": int, "from": str, "to": str},
            "tickets_handled": int,
            "auto_resolved": int,
            "human_handled": int,
            "money_saved_usd": float,
            "avg_quality": float,
            "quality_trend": str,
            "confidence_trend": {...},
            "new_skills_learned": [...],
            "top_improvement": {...},
            "needs_attention": [...],
            "prediction": str,
            "efficiency": {...},
            "generated_at": str,
        }
    """
    db = get_db()

    now = datetime.now(timezone.utc)
    period_from = (now - timedelta(days=days)).isoformat()
    period_to = now.isoformat()

    # 1. Core performance data
    perf = await db.get_weekly_performance_data(tenant_id, days=days)

    # 2. Confidence trends
    conf_trends = await db.get_confidence_trends(tenant_id, days=days)

    # 3. Efficiency metrics
    efficiency = await db.get_efficiency_metrics(tenant_id, days=days)

    # 4. Compute money saved
    auto_resolved = perf.get("auto_resolved", 0)
    total_tickets = perf.get("total_tickets", 0)
    money_saved = auto_resolved * HUMAN_COST_PER_TICKET
    human_handled = total_tickets - auto_resolved

    # 5. Find new skills (ticket types in this period that have approved training data)
    new_skills = await _find_new_skills(tenant_id, days)

    # 6. Top improvement: ticket type with biggest quality gain
    top_improvement = await _find_top_improvement(tenant_id, days)

    # 7. Needs attention: areas with accuracy < 85% or declining
    needs_attention = await _find_needs_attention(tenant_id, days)

    # 8. Prediction based on trend
    prediction = _generate_prediction(perf, conf_trends)

    report = {
        "report_type": "weekly_wins",
        "tenant_id": tenant_id,
        "period": {
            "days": days,
            "from": period_from,
            "to": period_to,
        },
        "tickets_handled": total_tickets,
        "auto_resolved": auto_resolved,
        "human_handled": max(0, human_handled),
        "money_saved_usd": round(money_saved, 2),
        "avg_quality": perf.get("avg_quality", 0),
        "quality_trend": perf.get("quality_trend", "stable"),
        "confidence_trend": conf_trends,
        "new_skills_learned": new_skills,
        "top_improvement": top_improvement,
        "needs_attention": needs_attention,
        "prediction": prediction,
        "efficiency": efficiency,
        "generated_at": now.isoformat(),
    }

    # Save to DB
    await db.save_generated_report(tenant_id, "weekly_wins", report)

    logger.info("Weekly wins report generated: tenant=%s tickets=%d saved=$%.2f",
                tenant_id, total_tickets, money_saved)

    return report


async def _find_new_skills(tenant_id: str, days: int) -> List[Dict[str, Any]]:
    """Find ticket types that got their first approved training signals recently."""
    db = get_db()
    training = await db.get_training_data(tenant_id, signal_type="approved", limit=200)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Group approved training by ticket_type
    type_first_seen: Dict[str, str] = {}
    for t in training:
        ttype = t.get("ticket_type", "")
        created = t.get("created_at", "")
        if not ttype or not created:
            continue
        if ttype not in type_first_seen:
            type_first_seen[ttype] = created

    # Find types first seen within the window
    new_skills = []
    for ttype, created_str in type_first_seen.items():
        try:
            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created_dt >= cutoff:
                new_skills.append({
                    "ticket_type": ttype,
                    "first_approved_at": created_str,
                    "description": f"AI now handles '{ttype}' tickets",
                })
        except (ValueError, TypeError):
            pass

    return new_skills


async def _find_top_improvement(tenant_id: str, days: int) -> Dict[str, Any]:
    """Find the ticket type with the biggest accuracy improvement."""
    db = get_db()
    perf = await db.get_weekly_performance_data(tenant_id, days=days)
    by_type = perf.get("by_type", {})

    if not by_type:
        return {"ticket_type": None, "improvement": "N/A", "description": "No data yet"}

    # Find highest accuracy path
    best_path = max(by_type.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
    return {
        "ticket_type": best_path[0],
        "improvement": best_path[1],
        "description": f"Resolution path '{best_path[0]}' leads with {best_path[1]} tickets",
    }


async def _find_needs_attention(tenant_id: str, days: int) -> List[Dict[str, Any]]:
    """Find areas needing attention: low accuracy types, recurring errors."""
    db = get_db()
    mistakes = await db.get_mistake_breakdown(tenant_id, days)
    attention = []

    for error_type, count in mistakes.get("error_types", {}).items():
        if count >= 2:  # recurring issue
            attention.append({
                "area": error_type,
                "count": count,
                "severity": "high" if count >= 5 else "medium",
                "description": f"{count} tickets with '{error_type}' resolution — review needed",
            })

    return attention


def _generate_prediction(perf: Dict, conf_trends: Dict) -> str:
    """Generate a forward-looking prediction based on current trends."""
    avg_quality = perf.get("avg_quality", 0)
    trend = perf.get("quality_trend", "stable")
    avg_conf = conf_trends.get("avg_confidence", 0)

    if trend == "improving" and avg_quality > 0.85:
        next_week = min(99, int(avg_quality * 100) + 3)
        return (f"Based on the improving trend, AI accuracy will reach ~{next_week}% "
                f"by next week. Consider enabling Graduated mode for '{trend}' ticket types.")
    elif trend == "declining":
        return (f"Accuracy is declining (current: {avg_quality:.0%}). "
                f"Review recent policy changes or new ticket patterns. "
                f"Consider adding training data for underperforming types.")
    elif avg_conf < 0.80:
        return (f"Average confidence is {avg_conf:.0%}. Focus on adding more approved "
                f"training examples to boost confidence scores.")
    elif avg_quality > 0.90:
        return (f"AI is performing well at {avg_quality:.0%} accuracy. "
                f"Consider expanding to more ticket types or reducing review frequency.")
    else:
        return (f"Steady performance at {avg_quality:.0%} accuracy. "
                f"Continue approving good responses to improve training coverage.")


# ═══════════════════════════════════════════════════════════════
# 6B: PERFORMANCE DASHBOARD DATA
# ═══════════════════════════════════════════════════════════════


async def get_performance_dashboard(
    tenant_id: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Get all performance dashboard data in one call.

    Returns:
        {
            "volume_accuracy": {...},
            "confidence_trends": {...},
            "efficiency_gains": {...},
            "learning_progress": {...},
        }
    """
    db = get_db()

    # Parallel-style sequential calls (all from same DB, no network hops in InMemory)
    volume_accuracy = await db.get_weekly_performance_data(tenant_id, days=days)
    confidence = await db.get_confidence_trends(tenant_id, days=days)
    efficiency = await db.get_efficiency_metrics(tenant_id, days=days)

    # Training priority for learning progress
    from app.core.jarvis_pipeline.quality_coach import generate_training_priority_list
    training_priorities = await generate_training_priority_list(tenant_id)

    dashboard = {
        "volume_accuracy": volume_accuracy,
        "confidence_trends": confidence,
        "efficiency_gains": efficiency,
        "learning_progress": {
            "training_priorities": training_priorities[:5],  # top 5
            "total_priority_areas": len(training_priorities),
        },
        "tenant_id": tenant_id,
        "period_days": days,
    }

    logger.info("Performance dashboard: tenant=%s days=%d", tenant_id, days)
    return dashboard


# ═══════════════════════════════════════════════════════════════
# REPORT TEXT FORMATTER
# ═══════════════════════════════════════════════════════════════


def format_weekly_report_text(report: Dict[str, Any]) -> str:
    """Format a weekly wins report into human-readable text.

    No DB/LLM calls. Pure string formatting.
    """
    lines = []

    # Header
    period = report.get("period", {})
    days = period.get("days", 7)
    lines.append(f"Weekly Progress Report ({days}-Day Window)")
    lines.append("=" * 50)

    # Core metrics
    tickets = report.get("tickets_handled", 0)
    auto = report.get("auto_resolved", 0)
    human = report.get("human_handled", 0)
    saved = report.get("money_saved_usd", 0)
    quality = report.get("avg_quality", 0)
    trend = report.get("quality_trend", "stable")

    lines.append(f"\nTickets Handled: {tickets} (AI auto-resolved: {auto}, Human: {human})")
    lines.append(f"Money Saved: ${saved:.2f} (estimated at ${HUMAN_COST_PER_TICKET:.0f}/ticket human cost)")
    lines.append(f"Average Quality: {quality:.1%} (trend: {trend})")

    # Confidence
    conf = report.get("confidence_trend", {})
    avg_conf = conf.get("avg_confidence", 0)
    if avg_conf:
        lines.append(f"Average Confidence: {avg_conf:.1%}")
        dist = conf.get("distribution", {})
        if dist:
            lines.append(f"  Auto: {dist.get('auto', 0)} | Batch: {dist.get('batch', 0)} | "
                         f"Ask: {dist.get('ask', 0)} | Escalate: {dist.get('escalate', 0)}")

    # New skills
    skills = report.get("new_skills_learned", [])
    if skills:
        skill_names = [s.get("ticket_type", "?") for s in skills[:5]]
        lines.append(f"\nNew Skills Learned: {', '.join(skill_names)}")

    # Top improvement
    top = report.get("top_improvement", {})
    if top.get("ticket_type"):
        lines.append(f"\nTop Improvement: {top.get('description', '')}")

    # Needs attention
    attention = report.get("needs_attention", [])
    if attention:
        lines.append(f"\nNeeds Attention ({len(attention)} items):")
        for a in attention[:5]:
            lines.append(f"  - {a.get('description', a.get('area', ''))}")

    # Prediction
    prediction = report.get("prediction", "")
    if prediction:
        lines.append(f"\nPrediction: {prediction}")

    # Efficiency
    eff = report.get("efficiency", {})
    time_saved = eff.get("manager_time_saved_minutes", 0)
    if time_saved > 0:
        hours = int(time_saved // 60)
        mins = int(time_saved % 60)
        lines.append(f"\nManager Time Saved: {hours}h {mins}m")

    lines.append("")
    return "\n".join(lines)