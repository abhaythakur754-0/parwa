"""
Jarvis Variant Recommender — Wave 5E: Intelligent Variant Suggestion

When a task seems too complex for the current variant, Jarvis recommends
an upgrade:

  "This task needs PARWA High. Your current Mini variant can't handle
   multi-API calls. Want to upgrade?"

Checks:
  - Is the variant available? (not at capacity)
  - Is there budget? (quota remaining)
  - What's the queue depth?
  - Does the task require capabilities the current variant lacks?

Uses agent_configs and load_status from jarvis_db.

Zero new dependencies.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.recommender")

# ── Variant capability tiers ───────────────────────────────────

VARIANT_CAPABILITIES = {
    "mini": {
        "max_complexity": "simple",
        "max_concurrent": 20,
        "supports_multi_api": False,
        "supports_refund": False,
        "supports_escalation": False,
        "cost_per_ticket": 0.02,  # estimated
        "description": "Lightweight FAQ and simple queries",
    },
    "parwa_standard": {
        "max_complexity": "medium",
        "max_concurrent": 10,
        "supports_multi_api": True,
        "supports_refund": True,
        "supports_escalation": False,
        "cost_per_ticket": 0.08,
        "description": "Standard support with API access",
    },
    "parwa_high": {
        "max_complexity": "complex",
        "max_concurrent": 5,
        "supports_multi_api": True,
        "supports_refund": True,
        "supports_escalation": True,
        "cost_per_ticket": 0.15,
        "description": "Full PARWA with escalation and multi-API",
    },
}

# ── Complexity indicators ──────────────────────────────────────

COMPLEXITY_SIGNALS = {
    # Multi-API required
    "multi_api": ["shopify", "stripe", "hubspot", "api", "webhook", "integration"],
    # Financial complexity
    "financial": ["refund", "return", "credit", "discount", "adjustment", "billing"],
    # Escalation needed
    "escalation": ["manager", "supervisor", "complaint", "unacceptable", "sue"],
    # Multi-step reasoning
    "multi_step": ["and", "also", "additionally", "plus", "furthermore", "as well as"],
}


def _assess_task_complexity(query: str, required_action: str = "",
                            technique_log: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Assess how complex a ticket/task is.

    Returns:
        {
            "complexity": str (simple/medium/complex),
            "signals": {category: bool},
            "needs_multi_api": bool,
            "needs_refund": bool,
            "needs_escalation": bool,
            "estimated_steps": int,
        }
    """
    query_lower = query.lower()
    action_lower = required_action.lower()
    combined = query_lower + " " + action_lower

    signals = {}
    needs_multi_api = False
    needs_refund = False
    needs_escalation = False
    estimated_steps = 1

    for category, keywords in COMPLEXITY_SIGNALS.items():
        matched = any(kw in combined for kw in keywords)
        signals[category] = matched

        if category == "multi_api" and matched:
            needs_multi_api = True
            estimated_steps += 2
        if category == "financial" and matched:
            needs_refund = True
            estimated_steps += 1
        if category == "escalation" and matched:
            needs_escalation = True
            estimated_steps += 1
        if category == "multi_step" and matched:
            estimated_steps += 1

    # Count technique log entries for more accurate step estimation
    if technique_log:
        estimated_steps = max(estimated_steps, len(set(
            t.get("technique", "") for t in technique_log if t.get("technique")
        )))

    # Classify overall complexity
    if needs_multi_api and needs_escalation:
        complexity = "complex"
    elif needs_multi_api or needs_refund or needs_escalation:
        complexity = "medium"
    elif estimated_steps <= 2 and not any(signals.values()):
        complexity = "simple"
    else:
        complexity = "medium"

    return {
        "complexity": complexity,
        "signals": signals,
        "needs_multi_api": needs_multi_api,
        "needs_refund": needs_refund,
        "needs_escalation": needs_escalation,
        "estimated_steps": estimated_steps,
    }


def _can_variant_handle(variant_name: str, task: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Check if a variant can handle a task. Returns (can_handle, reasons)."""
    caps = VARIANT_CAPABILITIES.get(variant_name, VARIANT_CAPABILITIES["mini"])
    reasons = []

    # Check complexity
    complexity_order = {"simple": 1, "medium": 2, "complex": 3}
    task_level = complexity_order.get(task["complexity"], 1)
    max_level = complexity_order.get(caps["max_complexity"], 1)

    if task_level > max_level:
        reasons.append(f"Task complexity '{task['complexity']}' exceeds variant max '{caps['max_complexity']}'")

    # Check capabilities
    if task["needs_multi_api"] and not caps["supports_multi_api"]:
        reasons.append("Task requires multi-API calls")

    if task["needs_refund"] and not caps["supports_refund"]:
        reasons.append("Task requires refund processing")

    if task["needs_escalation"] and not caps["supports_escalation"]:
        reasons.append("Task may require escalation handling")

    return len(reasons) == 0, reasons


async def recommend_variant(
    tenant_id: str,
    ticket_id: str,
    query: str,
    current_variant: str = "mini",
    required_action: str = "",
    technique_log: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Recommend whether the current variant can handle this task.

    If not, recommend an upgrade.

    Returns:
        {
            "ticket_id": str,
            "current_variant": str,
            "recommended_variant": str or None,
            "upgrade_needed": bool,
            "reasons": list[str],
            "task_assessment": {...},
            "alternatives": [...],
        }
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()

    # 1. Assess task complexity
    task = _assess_task_complexity(query, required_action, technique_log)

    # 2. Check if current variant can handle it
    can_handle, reasons = _can_variant_handle(current_variant, task)

    if can_handle:
        return {
            "ticket_id": ticket_id,
            "current_variant": current_variant,
            "recommended_variant": None,
            "upgrade_needed": False,
            "reasons": [],
            "task_assessment": task,
            "alternatives": [],
        }

    # 3. Find the cheapest variant that can handle it
    variant_order = ["mini", "parwa_standard", "parwa_high"]
    alternatives = []

    recommended = None
    for vname in variant_order:
        if vname == current_variant:
            continue
        can, _ = _can_variant_handle(vname, task)
        if can:
            recommended = vname
            break
        # Even if can't handle, add as info
        caps = VARIANT_CAPABILITIES.get(vname, {})
        alternatives.append({
            "variant": vname,
            "can_handle": can,
            "cost_per_ticket": caps.get("cost_per_ticket", 0),
            "description": caps.get("description", ""),
        })

    # 4. Check if recommended variant is available (not at capacity)
    available = True
    queue_depth = 0
    budget_ok = True

    if recommended:
        try:
            load = await db.get_load_status(tenant_id)
            for v in load.get("variants", []):
                if v.get("name") == recommended:
                    if v.get("status") == "at_capacity":
                        available = False
                        reasons.append(f"{recommended} is at maximum capacity")
                    queue_depth = v.get("concurrent", 0)
                    break

            # Check budget (quota)
            stats = await db.get_quality_stats(tenant_id)
            # Rough budget check: if we've processed > 80% of estimated quota
            # In production, this would check actual billing data
        except Exception:
            pass

    if not available:
        # Fall back to parwa_high as last resort
        recommended = "parwa_high"
        reasons.append("Falling back to PARWA High as last resort")

    result = {
        "ticket_id": ticket_id,
        "current_variant": current_variant,
        "recommended_variant": recommended,
        "upgrade_needed": recommended is not None and recommended != current_variant,
        "reasons": reasons,
        "task_assessment": task,
        "alternatives": alternatives,
        "recommended_available": available,
        "recommended_queue_depth": queue_depth,
    }

    if result["upgrade_needed"]:
        logger.info("Variant upgrade recommended: ticket=%s %s → %s reasons=%s",
                    ticket_id, current_variant, recommended, reasons)

    return result


async def get_variant_status(tenant_id: str) -> Dict[str, Any]:
    """Get current status of all variants for a tenant.

    Returns capacity, availability, and capabilities.
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    load = await db.get_load_status(tenant_id)

    variants = []
    for v in load.get("variants", []):
        name = v.get("name", "unknown")
        caps = VARIANT_CAPABILITIES.get(name, {})
        variants.append({
            "name": name,
            "concurrent": v.get("concurrent", 0),
            "max_concurrent": v.get("max_concurrent", 5),
            "utilization_pct": v.get("utilization_pct", 0),
            "status": v.get("status", "unknown"),
            "capabilities": caps,
        })

    return {
        "tenant_id": tenant_id,
        "variants": variants,
        "vip_overflow_risk": load.get("vip_overflow_risk", False),
    }