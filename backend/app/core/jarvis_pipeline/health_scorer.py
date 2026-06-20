"""
Jarvis Health Scorer — Wave 6F + 6G: Customer Health Score & ROI Calculator

Provides:
  6F: Customer health score for onboarding clients, milestone-based guidance
  6G: ROI calculator — cost comparison, savings analysis

Zero new dependencies.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.health")

# ── Onboarding Milestones ─────────────────────────────────────

ONBOARDING_MILESTONES = [
    {
        "name": "knowledge_base_setup",
        "description": "Upload knowledge base documents (policies, FAQs, product info)",
        "threshold": 0.20,  # 20% = at least some KB content
        "weight": 0.25,
    },
    {
        "name": "initial_training",
        "description": "AI has at least 10 approved training examples",
        "threshold": 10,  # count of approved training records
        "weight": 0.20,
    },
    {
        "name": "accuracy_target",
        "description": "AI accuracy reaches 85% on handled tickets",
        "threshold": 0.85,
        "weight": 0.25,
    },
    {
        "name": "integration_connect",
        "description": "At least 1 external integration connected and healthy",
        "threshold": 1,
        "weight": 0.15,
    },
    {
        "name": "policy_coverage",
        "description": "Cover at least 5 distinct ticket types with training data",
        "threshold": 5,
        "weight": 0.15,
    },
]

# ── Cost Assumptions ──────────────────────────────────────────

HUMAN_COST_PER_TICKET = 8.0
HUMAN_AVG_TIME_MINUTES = 12.0
AI_COST_MULTIPLIER = 1.0  # 1.0 = actual cost from DB


# ═══════════════════════════════════════════════════════════════
# 6F: CUSTOMER HEALTH SCORE
# ═══════════════════════════════════════════════════════════════


async def get_customer_health(tenant_id: str) -> Dict[str, Any]:
    """Get comprehensive customer health score for onboarding.

    Combines KB coverage, accuracy, policy count, integration health
    into a composite score with milestone tracking.

    Returns:
        {
            "tenant_id": str,
            "health_score": float (0-1),
            "readiness_pct": int (0-100),
            "grade": str (onboarding/ready/optimized/excellent),
            "components": {
                "kb_coverage": float,
                "accuracy_score": float,
                "policy_count": float,
                "integration_health": float,
            },
            "milestones": [
                {"name": str, "achieved": bool, "description": str, "current_value": ...},
            ],
            "success_coach_message": str,
        }
    """
    db = get_db()

    # 1. Get base health from DB
    base_health = await db.get_customer_health_score(tenant_id)

    components = base_health.get("components", {})
    kb_coverage = components.get("kb_coverage", 0)
    accuracy_score = components.get("accuracy_score", 0)
    policy_coverage = components.get("policy_coverage", 0)
    integration_health = components.get("integration_health", 0)

    # 2. Check milestones
    training_data = await db.get_training_data(tenant_id, signal_type="approved", limit=500)
    approved_count = len(training_data)

    # Count distinct ticket types
    ticket_types = set(t.get("ticket_type", "") for t in training_data if t.get("ticket_type"))
    type_count = len(ticket_types)

    # Integration health
    int_health = await db.get_integration_health(tenant_id)
    healthy_integrations = int_health.get("healthy_count", 0)

    milestones = []
    for m in ONBOARDING_MILESTONES:
        name = m["name"]
        achieved = False
        current_value = None

        if name == "knowledge_base_setup":
            current_value = kb_coverage
            achieved = kb_coverage >= m["threshold"]
        elif name == "initial_training":
            current_value = approved_count
            achieved = approved_count >= m["threshold"]
        elif name == "accuracy_target":
            current_value = accuracy_score
            achieved = accuracy_score >= m["threshold"]
        elif name == "integration_connect":
            current_value = healthy_integrations
            achieved = healthy_integrations >= m["threshold"]
        elif name == "policy_coverage":
            current_value = type_count
            achieved = type_count >= m["threshold"]

        milestones.append({
            "name": name,
            "achieved": achieved,
            "description": m["description"],
            "threshold": m["threshold"],
            "current_value": current_value,
            "weight": m["weight"],
        })

    achieved_count = sum(1 for m in milestones if m["achieved"])
    total_milestones = len(milestones)

    # 3. Composite score (weighted)
    composite = 0
    total_weight = 0
    for m in milestones:
        w = m["weight"]
        cv = m["current_value"] or 0
        threshold = m["threshold"]
        # Normalize: how far toward the threshold (capped at 1.0)
        progress = min(1.0, cv / max(threshold, 0.001)) if threshold > 0 else 0
        composite += progress * w
        total_weight += w

    health_score = composite / max(total_weight, 0.001)
    health_score = round(health_score, 4)
    readiness_pct = int(health_score * 100)

    # 4. Grade
    if readiness_pct >= 90:
        grade = "excellent"
    elif readiness_pct >= 75:
        grade = "ready"
    elif readiness_pct >= 50:
        grade = "onboarding"
    else:
        grade = "early"

    # 5. Success coach message
    coach_msg = get_success_coach_message(
        health_score, readiness_pct, milestones, grade
    )

    result = {
        "tenant_id": tenant_id,
        "health_score": health_score,
        "readiness_pct": readiness_pct,
        "grade": grade,
        "components": components,
        "milestones": milestones,
        "achieved_milestones": achieved_count,
        "total_milestones": total_milestones,
        "success_coach_message": coach_msg,
    }

    logger.info("Customer health: tenant=%s score=%.2f grade=%s milestones=%d/%d",
                tenant_id, health_score, grade, achieved_count, total_milestones)

    return result


def get_success_coach_message(
    health_score: float,
    readiness_pct: int,
    milestones: List[Dict[str, Any]],
    grade: str,
) -> str:
    """Generate a success coach message based on health and milestones.

    Pure string builder. No DB/LLM calls.
    """
    # Find unachieved milestones
    unachieved = [m for m in milestones if not m["achieved"]]

    if grade == "excellent":
        return (
            f"You're {readiness_pct}% ready — excellent! Your AI is well-trained and "
            f"connected. Focus on monitoring drift and expanding to new ticket types."
        )

    if grade == "ready":
        if unachieved:
            next_m = unachieved[0]
            return (
                f"You're {readiness_pct}% ready to go live. "
                f"Complete '{next_m['description']}' and you'll be in excellent shape. "
                f"Consider starting a supervised trial with real tickets."
            )
        return f"You're {readiness_pct}% ready. All milestones achieved!"

    # Build specific guidance for onboarding/early
    guidance_parts = []
    for m in unachieved[:3]:  # Top 3 unachieved
        name = m["name"]
        cv = m.get("current_value", 0)
        threshold = m.get("threshold", "?")
        if name == "knowledge_base_setup":
            guidance_parts.append("upload your knowledge base documents (policies, FAQs)")
        elif name == "initial_training":
            remaining = max(0, int(threshold) - int(cv))
            guidance_parts.append(f"add {remaining} more approved training examples")
        elif name == "accuracy_target":
            guidance_parts.append("improve AI accuracy to 85%+ (approve more good responses)")
        elif name == "integration_connect":
            guidance_parts.append("connect and verify at least 1 external integration")
        elif name == "policy_coverage":
            remaining = max(0, int(threshold) - int(cv))
            guidance_parts.append(f"add training data for {remaining} more ticket types")

    if guidance_parts:
        actions = ". Then ".join(guidance_parts)
        return (f"You're {readiness_pct}% ready. Next steps: {actions}. "
                f"This will significantly improve your AI's performance.")
    else:
        return f"You're {readiness_pct}% ready. Keep adding training data to improve."


# ═══════════════════════════════════════════════════════════════
# 6G: ROI CALCULATOR
# ═══════════════════════════════════════════════════════════════


async def calculate_roi(
    tenant_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """Calculate ROI for the AI system.

    Compares:
    - Human cost: tickets manually handled * $8/ticket * avg time
    - AI cost: total LLM cost from DB

    Returns:
        {
            "tenant_id": str,
            "period_days": int,
            "total_tickets": int,
            "auto_resolved": int,
            "human_handled": int,
            "human_cost_usd": float,
            "ai_cost_usd": float,
            "net_savings_usd": float,
            "roi_pct": float,
            "auto_resolve_pct": float,
            "recommendation": str,
        }
    """
    db = get_db()

    # 1. Performance data
    perf = await db.get_weekly_performance_data(tenant_id, days=days)
    total = perf.get("total_tickets", 0)
    auto = perf.get("auto_resolved", 0)
    human = max(0, total - auto)

    # 2. Efficiency
    efficiency = await db.get_efficiency_metrics(tenant_id, days=days)

    # 3. LLM costs
    cost_summary = await db.get_llm_cost_summary(tenant_id, days=days)
    ai_cost = cost_summary.get("total_cost_usd", 0.0)

    # 4. Compute human cost
    human_cost = human * HUMAN_COST_PER_TICKET

    # 5. Net savings and ROI
    net_savings = human_cost - ai_cost
    roi_pct = (net_savings / ai_cost * 100) if ai_cost > 0 else (100.0 if net_savings > 0 else 0.0)

    auto_pct = (auto / max(total, 1)) * 100

    # 6. Recommendation
    recommendation = _roi_recommendation(
        total, auto, human, human_cost, ai_cost, net_savings, roi_pct, auto_pct
    )

    result = {
        "tenant_id": tenant_id,
        "period_days": days,
        "total_tickets": total,
        "auto_resolved": auto,
        "human_handled": human,
        "human_cost_usd": round(human_cost, 2),
        "ai_cost_usd": round(ai_cost, 2),
        "net_savings_usd": round(net_savings, 2),
        "roi_pct": round(roi_pct, 1),
        "auto_resolve_pct": round(auto_pct, 1),
        "recommendation": recommendation,
        "efficiency": efficiency,
    }

    logger.info("ROI: tenant=%s savings=$%.2f roi=%.1f%% auto=%.1f%%",
                tenant_id, net_savings, roi_pct, auto_pct)

    return result


def _roi_recommendation(
    total: int, auto: int, human: int,
    human_cost: float, ai_cost: float,
    net_savings: float, roi_pct: float, auto_pct: float,
) -> str:
    """Generate ROI recommendation."""
    if total == 0:
        return "No tickets processed yet. Start handling tickets to see ROI data."

    if auto_pct >= 90:
        return (
            f"Excellent ROI: {roi_pct:.0f}% return. AI handles {auto_pct:.0f}% of tickets "
            f"automatically, saving ${net_savings:.2f} vs human cost. "
            f"Your AI is highly efficient."
        )
    elif auto_pct >= 70:
        return (
            f"Good ROI: {roi_pct:.0f}% return. AI handles {auto_pct:.0f}% of tickets, "
            f"saving ${net_savings:.2f}. Consider optimizing approval gates "
            f"to increase auto-resolve rate."
        )
    elif auto_pct >= 50:
        return (
            f"Moderate ROI: {roi_pct:.0f}% return. AI handles {auto_pct:.0f}% of tickets, "
            f"saving ${net_savings:.2f}. Focus on adding training data to boost "
            f"confidence and auto-resolve rate."
        )
    else:
        return (
            f"Low ROI so far: {roi_pct:.0f}% return. Only {auto_pct:.0f}% of tickets "
            f"are auto-resolved. This is normal during early onboarding. "
            f"Add training data and connect integrations to improve."
        )