"""
Jarvis Approval Gates — Wave 5D: Hard-Coded Safety Rules

Hard-coded safety rules that CANNOT be overridden by AI:
  - Always require approval for: Refunds (any amount), Returns, Account changes,
    Policy exceptions, VIP customer actions, Financial transactions (credits,
    adjustments, discounts >$10)
  - Even "Always Auto-Approve" has a blacklist: refunds and account changes
    ALWAYS need approval regardless
  - Approval gates live in DB (jarvis_feature_flags or dedicated config)
  - State is preserved during approval wait — ticket doesn't get lost

The approval_gates config is stored in jarvis_db and cached per tenant.

Zero new dependencies.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("jarvis.approval_gates")

# ── Default gates (always active, cannot be removed) ───────────

# Actions that ALWAYS require approval — even with auto-approve rules
HARD_REQUIRE_APPROVAL: Set[str] = {
    "refund", "refund_request", "execute_refund",
    "return", "return_request", "process_return",
    "account_change", "address_change", "plan_change",
    "policy_exception", "policy_override",
    "financial_credit", "financial_adjustment",
}

# Actions that require approval if value exceeds threshold
CONDITIONAL_APPROVAL: Dict[str, float] = {
    "discount": 10.0,      # discounts > $10 need approval
    "credit_memo": 0.0,    # any credit memo
    "price_adjustment": 10.0,
    "shipping_override": 0.0,
}

# VIP actions: always require approval for VIP customers
VIP_REQUIRE_APPROVAL: Set[str] = {
    "refund", "return", "account_change", "discount",
    "cancellation", "subscription_change",
}

# ── Cache ──────────────────────────────────────────────────────

_gate_cache: Dict[str, Dict[str, Any]] = {}  # tenant_id -> {gates, loaded_at}
_GATE_CACHE_TTL = 30.0  # 30 seconds


async def load_approval_gates(tenant_id: str) -> Dict[str, Any]:
    """Load approval gate config for a tenant.

    Combines:
      1. Hard-coded gates (always active)
      2. DB-stored gates (per-tenant customizations)
      3. Feature flags that modify gate behavior

    Returns:
        {
            "hard_gates": set of action types that ALWAYS require approval,
            "conditional_gates": {action: value_threshold},
            "vip_gates": set of actions requiring approval for VIPs,
            "auto_approve_actions": set of actions that are auto-approved,
            "auto_approve_blacklist": set that overrides auto_approve (can never auto-approve these),
            "max_auto_approve_confidence": float,
        }
    """
    now = time.time()
    cached = _gate_cache.get(tenant_id)
    if cached and (now - cached["loaded_at"]) < _GATE_CACHE_TTL:
        return cached["result"]

    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()

    # Load custom gates from feature_flags
    custom_gates = await db.get_feature_flag(tenant_id, "approval_gates")
    auto_approve_blacklist = set(HARD_REQUIRE_APPROVAL)

    # Parse custom config if it exists
    auto_approve_actions: Set[str] = set()
    max_auto_confidence = 0.95  # default: only auto-approve if > 95% confidence

    if custom_gates and isinstance(custom_gates, dict):
        # Custom actions to auto-approve (but NOT in blacklist)
        custom_auto = custom_gates.get("auto_approve_actions", [])
        for action in custom_auto:
            if action not in auto_approve_blacklist:
                auto_approve_actions.add(action)

        # Custom max confidence threshold
        custom_max = custom_gates.get("max_auto_approve_confidence")
        if custom_max is not None:
            max_auto_confidence = float(custom_max)

        # Custom hard gates (can only ADD, never remove defaults)
        custom_hard = custom_gates.get("additional_hard_gates", [])
        for action in custom_hard:
            auto_approve_blacklist.add(action)

    result = {
        "hard_gates": set(HARD_REQUIRE_APPROVAL),
        "conditional_gates": dict(CONDITIONAL_APPROVAL),
        "vip_gates": set(VIP_REQUIRE_APPROVAL),
        "auto_approve_actions": auto_approve_actions,
        "auto_approve_blacklist": auto_approve_blacklist,
        "max_auto_approve_confidence": max_auto_confidence,
    }

    _gate_cache[tenant_id] = {"result": result, "loaded_at": now}
    return result


def invalidate_gate_cache(tenant_id: Optional[str] = None):
    """Invalidate gate cache."""
    if tenant_id:
        _gate_cache.pop(tenant_id, None)
    else:
        _gate_cache.clear()


async def check_approval_required(
    tenant_id: str,
    action: str,
    confidence: float = 1.0,
    is_vip: bool = False,
    value_usd: float = 0.0,
) -> Dict[str, Any]:
    """Check if an action requires human approval.

    This is the main entry point. Called by PARWA bridge before auto-approving.

    Returns:
        {
            "required": bool,
            "reason": str,
            "gate_type": str (hard/conditional/vip/confidence/blacklist),
            "action": str,
            "confidence": float,
        }
    """
    gates = await load_approval_gates(tenant_id)

    action_lower = action.lower().strip()
    action_base = action_lower.replace("execute_", "").replace("process_", "").replace("handle_", "")

    # 1. Check hard gates (ALWAYS require approval)
    if action_lower in gates["hard_gates"] or action_base in gates["hard_gates"]:
        return {
            "required": True,
            "reason": f"Action '{action}' always requires human approval (hard gate)",
            "gate_type": "hard",
            "action": action,
            "confidence": confidence,
        }

    # 2. Check blacklist (overrides auto-approve even for non-hard actions)
    if action_lower in gates["auto_approve_blacklist"]:
        return {
            "required": True,
            "reason": f"Action '{action}' is in auto-approve blacklist",
            "gate_type": "blacklist",
            "action": action,
            "confidence": confidence,
        }

    # 3. Check conditional gates (value-based)
    for cond_action, threshold in gates["conditional_gates"].items():
        if cond_action in action_lower:
            if value_usd > threshold:
                return {
                    "required": True,
                    "reason": f"Action '{action}' requires approval (value ${value_usd:.2f} > ${threshold:.2f} threshold)",
                    "gate_type": "conditional",
                    "action": action,
                    "confidence": confidence,
                }

    # 4. Check VIP gates
    if is_vip:
        if action_lower in gates["vip_gates"] or action_base in gates["vip_gates"]:
            return {
                "required": True,
                "reason": f"Action '{action}' requires approval for VIP customers",
                "gate_type": "vip",
                "action": action,
                "confidence": confidence,
            }

    # 5. Check confidence-based approval
    if action_lower in gates["auto_approve_actions"]:
        if confidence >= gates["max_auto_approve_confidence"]:
            return {
                "required": False,
                "reason": f"Action '{action}' auto-approved (confidence {confidence:.2%} >= {gates['max_auto_approve_confidence']:.2%})",
                "gate_type": "confidence_auto",
                "action": action,
                "confidence": confidence,
            }
        else:
            return {
                "required": True,
                "reason": f"Action '{action}' needs approval (confidence {confidence:.2%} < {gates['max_auto_approve_confidence']:.2%})",
                "gate_type": "confidence",
                "action": action,
                "confidence": confidence,
            }

    # 6. Default: not required
    return {
        "required": False,
        "reason": f"No approval gate matched for '{action}'",
        "gate_type": "none",
        "action": action,
        "confidence": confidence,
    }


async def set_custom_gates(
    tenant_id: str,
    auto_approve_actions: Optional[List[str]] = None,
    max_auto_approve_confidence: Optional[float] = None,
    additional_hard_gates: Optional[List[str]] = None,
    set_by: str = "admin",
) -> Dict[str, Any]:
    """Update custom approval gate configuration.

    Writes to feature_flags table. Takes the current config,
    merges changes, and saves back.
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()

    # Load existing
    existing = await db.get_feature_flag(tenant_id, "approval_gates")
    config = dict(existing) if isinstance(existing, dict) else {}

    if auto_approve_actions is not None:
        config["auto_approve_actions"] = auto_approve_actions
    if max_auto_approve_confidence is not None:
        config["max_auto_approve_confidence"] = max_auto_approve_confidence
    if additional_hard_gates is not None:
        existing_hard = set(config.get("additional_hard_gates", []))
        existing_hard.update(additional_hard_gates)
        config["additional_hard_gates"] = list(existing_hard)

    await db.set_feature_flag(
        tenant_id=tenant_id,
        flag_name="approval_gates",
        flag_value=config,
        set_by=set_by,
    )

    # Invalidate cache
    invalidate_gate_cache(tenant_id)

    logger.info("Approval gates updated: tenant=%s by=%s actions=%s",
                tenant_id, set_by, auto_approve_actions)

    return config