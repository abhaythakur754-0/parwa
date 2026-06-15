"""
Auto-Fix Node — Detects and optionally executes automated fixes.

This node is available to ALL variant tiers (same CAPABILITY).
The difference is in EXECUTION permission:
  - Mini: Can detect fixes, but must get approval before executing
  - Pro: Can execute low/medium risk fixes, needs approval for high-risk
  - High: Can execute all fixes freely

The node:
  1. Reads from the communication bus (what other nodes found)
  2. Checks diagnostic results from tech_diagnostic
  3. Checks billing anomalies from billing_resolver
  4. Determines if an auto-fix is available
  5. Checks tier permissions before executing
  6. If blocked by tier, posts to comm bus for human escalation

BC-008: Never crash — all exceptions caught.
BC-001: company_id first parameter on public methods.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.parwa_graph_state import (
    ParwaGraphState,
    read_comm_bus,
    post_to_comm_bus,
    post_shared_insight,
    get_shared_insights,
    append_audit_entry,
)
from app.core.variant_engine.tier_permissions import (
    check_permission,
    needs_approval,
)
from app.logger import get_logger

logger = get_logger("auto_fix_node")


# ══════════════════════════════════════════════════════════════════
# AUTO-FIX TYPES
# ══════════════════════════════════════════════════════════════════

FIX_REGISTRY = {
    "config_reset": {
        "description": "Reset customer configuration to defaults",
        "risk_level": "low",
        "category": "technical",
    },
    "cache_clear": {
        "description": "Clear stale cache entries causing issues",
        "risk_level": "low",
        "category": "technical",
    },
    "credential_refresh": {
        "description": "Refresh expired API credentials or tokens",
        "risk_level": "medium",
        "category": "technical",
    },
    "subscription_sync": {
        "description": "Sync subscription status with payment provider",
        "risk_level": "medium",
        "category": "billing",
    },
    "payment_retry": {
        "description": "Retry failed payment with updated method",
        "risk_level": "high",
        "category": "monetary",
    },
    "account_unlock": {
        "description": "Unlock locked customer account",
        "risk_level": "medium",
        "category": "security",
    },
    "order_status_sync": {
        "description": "Sync order status with fulfillment system",
        "risk_level": "low",
        "category": "shipping",
    },
    "refund_auto_process": {
        "description": "Auto-process eligible refund",
        "risk_level": "high",
        "category": "monetary",
    },
}


def _detect_available_fixes(state: ParwaGraphState) -> list:
    """Detect what auto-fixes are available based on pipeline state.

    Reads from node communication bus and step outputs to find
    fixable issues. This is the INTELLIGENCE part — same for all tiers.

    Args:
        state: Current pipeline state.

    Returns:
        List of available fix descriptors.
    """
    available_fixes = []

    # Read messages from other nodes
    messages = read_comm_bus(state, "auto_fix", min_priority="medium")

    # Check tech diagnostic results
    diagnostic = state.get("diagnostic_result", {})
    if diagnostic.get("auto_fix_available"):
        fix_type = diagnostic.get("resolution_path", "config_reset")
        if fix_type in FIX_REGISTRY:
            available_fixes.append({
                "fix_type": fix_type,
                **FIX_REGISTRY[fix_type],
                "source": "tech_diagnostic",
            })

    # Check known issues
    known_issue = state.get("known_issue", {})
    if known_issue.get("known_issue_detected") and known_issue.get("severity") == "low":
        available_fixes.append({
            "fix_type": "cache_clear",
            **FIX_REGISTRY["cache_clear"],
            "source": "known_issue",
            "issue_id": known_issue.get("issue_id", ""),
        })

    # Check billing anomalies
    billing_anomaly = state.get("billing_anomaly", {})
    if billing_anomaly.get("anomaly_detected"):
        available_fixes.append({
            "fix_type": "subscription_sync",
            **FIX_REGISTRY["subscription_sync"],
            "source": "billing_anomaly",
        })

    # Check shipping issues
    shipping_issue = state.get("shipping_issue", {})
    if shipping_issue.get("issue_detected") and shipping_issue.get("severity") == "low":
        available_fixes.append({
            "fix_type": "order_status_sync",
            **FIX_REGISTRY["order_status_sync"],
            "source": "shipping_tracker",
        })

    # Check refund eligibility from billing resolver
    billing_self_service = state.get("billing_self_service", {})
    if billing_self_service.get("refund_eligible"):
        available_fixes.append({
            "fix_type": "refund_auto_process",
            **FIX_REGISTRY["refund_auto_process"],
            "source": "billing_resolver",
            "amount": billing_self_service.get("refund_amount", 0),
        })

    # Check messages from other nodes that flagged fixable issues
    for msg in messages:
        if msg.get("message_type") == "insight" and "fix_available" in msg.get("payload", {}):
            fix_info = msg["payload"]["fix_available"]
            available_fixes.append({
                "fix_type": fix_info.get("fix_type", "config_reset"),
                **FIX_REGISTRY.get(fix_info.get("fix_type", "config_reset"), {}),
                "source": msg.get("from_node", "unknown"),
            })

    return available_fixes


def _execute_fix(fix_type: str, state: ParwaGraphState) -> Dict[str, Any]:
    """Execute an auto-fix.

    In production, this would call actual APIs/services.
    For now, returns a simulated result.

    Args:
        fix_type: The type of fix to execute.
        state: Current pipeline state.

    Returns:
        Dict with execution result.
    """
    # Simulated fix execution — in production, this calls real APIs
    return {
        "success": True,
        "fix_type": fix_type,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Auto-fix '{fix_type}' executed successfully",
    }


async def auto_fix_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Auto-fix node — detects and optionally executes automated fixes.

    This node is INTELLIGENT — it can detect fixable issues from
    the entire pipeline state. The PERMISSION to execute is tier-based.

    Flow:
      1. Read from comm bus + step_outputs
      2. Detect available fixes
      3. For each fix, check tier permissions
      4. If allowed → execute
      5. If blocked → post to comm bus for escalation
      6. Update state with results

    Args:
        state: Current pipeline state.

    Returns:
        Dict with state updates.
    """
    start = time.monotonic()
    variant_tier = state.get("variant_tier", "mini_parwa")
    company_id = state.get("company_id", "")

    try:
        # 1. Detect available fixes (same intelligence for ALL tiers)
        available_fixes = _detect_available_fixes(state)

        if not available_fixes:
            return {
                "auto_fix_result": {
                    "fix_available": False,
                    "fix_type": "",
                    "fix_executed": False,
                    "fix_blocked_by_tier": False,
                    "fix_description": "No auto-fixes available for this issue",
                    "fix_risk_level": "low",
                    "approval_required": False,
                    "fix_result": None,
                },
                "steps_completed": ["auto_fix"],
                **append_audit_entry(state, "auto_fix", "no_fixes_available"),
            }

        # 2. Take the highest-priority fix
        best_fix = available_fixes[0]
        fix_type = best_fix["fix_type"]
        fix_risk = best_fix.get("risk_level", "medium")

        # 3. Check tier permissions — CAN this tier execute this fix?
        can_auto_fix = check_permission(variant_tier, "auto_fix")
        approval_needed = needs_approval(
            variant_tier, "auto_fix", risk_level=fix_risk
        )

        fix_executed = False
        fix_blocked = False
        fix_result = None

        if can_auto_fix and not approval_needed:
            # Tier allows execution without approval
            fix_result = _execute_fix(fix_type, state)
            fix_executed = True
        elif can_auto_fix and approval_needed:
            # Tier allows it but needs approval first
            fix_blocked = True
            # Post to comm bus for human/Jarvis escalation
            post_msg = post_to_comm_bus(
                state,
                from_node="auto_fix",
                to_node="auto_action",
                message_type="request",
                payload={
                    "action": "auto_fix_approval_needed",
                    "fix_type": fix_type,
                    "fix_risk": fix_risk,
                    "fix_description": best_fix.get("description", ""),
                    "approval_required": True,
                },
                priority="high",
            )
        else:
            # Tier doesn't allow this fix at all
            fix_blocked = True

        # 4. Post insight to comm bus for other nodes
        insight = post_shared_insight(
            "auto_fix",
            "auto_fix_available",
            {
                "fix_type": fix_type,
                "fix_available": True,
                "fix_executed": fix_executed,
                "fix_blocked_by_tier": fix_blocked,
            },
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "auto_fix_result": {
                "fix_available": True,
                "fix_type": fix_type,
                "fix_executed": fix_executed,
                "fix_blocked_by_tier": fix_blocked,
                "fix_description": best_fix.get("description", ""),
                "fix_risk_level": fix_risk,
                "approval_required": approval_needed,
                "fix_result": fix_result,
            },
            "steps_completed": ["auto_fix"],
            **append_audit_entry(
                state,
                "auto_fix",
                f"fix_{'executed' if fix_executed else 'detected_blocked'}",
                duration_ms=duration_ms,
                details={"fix_type": fix_type, "tier": variant_tier},
            ),
        }

        # Include comm bus updates if we posted messages
        if fix_blocked and can_auto_fix:
            result.update(post_msg if 'post_msg' in dir() else {})
        result.update(insight)

        logger.info(
            "auto_fix_node: tier=%s, fix=%s, executed=%s, blocked=%s, ms=%.1f",
            variant_tier, fix_type, fix_executed, fix_blocked, duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("auto_fix_node_error: %s", str(exc)[:200])
        return {
            "auto_fix_result": {
                "fix_available": False,
                "fix_type": "",
                "fix_executed": False,
                "fix_blocked_by_tier": False,
                "fix_description": f"Auto-fix detection error: {str(exc)[:100]}",
                "fix_risk_level": "high",
                "approval_required": True,
                "fix_result": None,
            },
            "errors": [f"auto_fix_node_error: {str(exc)[:200]}"],
            **append_audit_entry(state, "auto_fix", "error", duration_ms=duration_ms),
        }
