"""
Control System Node — Group 7: Approval & Interrupt Logic

Implements the human-in-the-loop control system with interrupt logic
for approval workflows. Determines whether a proposed action can be
auto-approved or requires human review based on variant tier,
action type, red flags, VIP status, and DND rules.

Tier Behavior:
  Mini:  Auto-approve everything (no interrupts)
  Pro:   Human approval for monetary + destructive + VIP + red flag
  High:  Human approval for all risky actions + VIP + money rules

State Contract:
  Reads:  red_flag, action_type, variant_tier, agent_confidence,
          pii_redacted_message, tenant_id, customer_tier,
          dnd_applies, selected_solution
  Writes: approval_decision, confidence_breakdown, system_mode,
          dnd_applies, money_rule_triggered, vip_rule_triggered,
          approval_timeout_seconds

BC-008: Never crash — defaults to needs_human_approval on error (conservative).
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict

from app.core.langgraph.config import (
    CONTROL_CONFIG,
    ApprovalDecision,
    SystemMode,
    needs_human_approval,
)
from app.logger import get_logger

logger = get_logger("node_control_system")


# ──────────────────────────────────────────────────────────────
# Default fallback values for Control System output
# ──────────────────────────────────────────────────────────────

_DEFAULT_CONTROL_STATE: Dict[str, Any] = {
    "approval_decision": ApprovalDecision.NEEDS_HUMAN_APPROVAL.value,
    "confidence_breakdown": {},
    "system_mode": SystemMode.SUPERVISED.value,
    "dnd_applies": False,
    "money_rule_triggered": False,
    "vip_rule_triggered": False,
    "approval_timeout_seconds": 300,
}


# ═══════════════════════════════════════════════════════════════
# Internal: DND (Do Not Disturb) check
# ═══════════════════════════════════════════════════════════════


def _check_dnd_applies(
    state: Dict[str, Any],
    tenant_id: str,
) -> bool:
    """
    Check if Do Not Disturb rules apply for this customer.

    Uses the production DND module if available, otherwise
    uses the state's dnd_applies field.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if DND rules apply.
    """
    # Check state first (set by upstream nodes)
    if state.get("dnd_applies", False):
        return True

    try:
        from app.core.dnd_engine import check_dnd  # type: ignore[import-untyped]

        customer_id = state.get("customer_id", "")
        result = check_dnd(
            customer_id=customer_id,
            tenant_id=tenant_id,
        )
        return bool(result.get("dnd_active", False))

    except ImportError:
        pass
    except Exception as dnd_exc:
        logger.warning(
            "dnd_check_error",
            tenant_id=tenant_id,
            error=str(dnd_exc),
        )

    return False


# ═══════════════════════════════════════════════════════════════
# Internal: VIP check
# ═══════════════════════════════════════════════════════════════


def _is_vip_customer(
    state: Dict[str, Any],
    tenant_id: str,
) -> bool:
    """
    Check if the customer is a VIP requiring special handling.

    Uses the state's customer_tier field and optionally the
    production VIP module.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if the customer is VIP.
    """
    customer_tier = state.get("customer_tier", "free")
    if customer_tier in ("vip", "enterprise"):
        return True

    try:
        from app.core.customer_tier import is_vip  # type: ignore[import-untyped]

        customer_id = state.get("customer_id", "")
        return bool(is_vip(customer_id=customer_id, tenant_id=tenant_id))

    except ImportError:
        pass
    except Exception:
        pass

    return False


# ═══════════════════════════════════════════════════════════════
# Internal: Confidence breakdown builder
# ═══════════════════════════════════════════════════════════════


def _build_confidence_breakdown(
    agent_confidence: float,
    maker_confidence: float,
    red_flag: bool,
    action_type: str,
    variant_tier: str,
) -> Dict[str, float]:
    """
    Build the confidence breakdown dict for the state.

    Aggregates agent confidence, maker confidence, and computes
    an overall score weighted by tier-specific factors.

    Args:
        agent_confidence: Domain agent confidence (0.0-1.0).
        maker_confidence: MAKER best solution confidence (0.0-1.0).
        red_flag: Whether MAKER raised a red flag.
        action_type: Classified action type.
        variant_tier: Variant tier string.

    Returns:
        Dict with confidence breakdown scores.
    """
    # Weight the overall score
    agent_weight = 0.4
    maker_weight = 0.6  # MAKER carries more weight

    overall = (agent_confidence * agent_weight) + (maker_confidence * maker_weight)

    # Red flag penalty
    if red_flag:
        overall *= 0.7  # 30% penalty for red flags

    # Risky action penalty (for non-informational)
    if action_type in ("monetary", "destructive"):
        overall *= 0.9  # 10% penalty

    overall = round(max(0.0, min(1.0, overall)), 2)

    return {
        "agent_confidence": round(agent_confidence, 2),
        "maker_confidence": round(maker_confidence, 2),
        "action_type_risk": 0.1 if action_type in ("monetary", "destructive") else 0.0,
        "red_flag_penalty": 0.3 if red_flag else 0.0,
        "overall": overall,
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def control_system_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Control System Node — Approval and interrupt logic for human-in-the-loop.

    Determines whether proposed actions require human approval based on:
      - Variant tier (mini=auto, pro/high=selective)
      - Action type (informational/monetary/destructive/escalation)
      - Red flags from MAKER validator
      - VIP customer status
      - Monetary action rules
      - DND (Do Not Disturb) rules

    Approval Decision Logic:
      1. Mini tier → auto-approve everything
      2. Action type needs approval → needs_human_approval
      3. Red flag + pro/high → needs_human_approval
      4. VIP customer + monetary action → needs_human_approval (pro/high)
      5. DND applies → defer (auto-approve but mark for later review)

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with Control System output fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "control_system_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        action_type=state.get("action_type", "informational"),
        red_flag=state.get("red_flag", False),
    )

    try:
        # ── Extract state fields ────────────────────────────────
        red_flag = bool(state.get("red_flag", False))
        action_type = state.get("action_type", "informational")
        agent_confidence = float(state.get("agent_confidence", 0.0))

        # Get MAKER confidence from k_solutions if available
        maker_confidence = agent_confidence  # Default to agent confidence
        k_solutions = state.get("k_solutions", [])
        selected_solution = state.get("selected_solution", "")
        if k_solutions:
            # Find the best scored confidence
            for sol in k_solutions:
                scored = float(sol.get("scored_confidence", 0.0))
                if scored > maker_confidence:
                    maker_confidence = scored

        # ── Get control config for this tier ────────────────────
        control_config = CONTROL_CONFIG.get(
            variant_tier,
            CONTROL_CONFIG["mini"],
        )
        approval_timeout = int(
            control_config.get("human_approval_timeout_seconds", 300)
        )
        auto_approve_threshold = float(
            control_config.get("auto_approve_threshold", 0.50)
        )

        # ── Initialize flags ────────────────────────────────────
        money_rule_triggered = False
        vip_rule_triggered = False
        dnd_applies = _check_dnd_applies(state, tenant_id)
        is_vip = _is_vip_customer(state, tenant_id)

        # ── Determine approval decision ─────────────────────────
        approval_decision = ApprovalDecision.APPROVED.value
        system_mode = SystemMode.AUTO.value

        # ── Rule 1: Mini tier → auto-approve everything ────────
        if variant_tier == "mini":
            approval_decision = ApprovalDecision.AUTO_APPROVED.value
            system_mode = SystemMode.AUTO.value

            logger.info(
                "control_mini_auto_approved",
                tenant_id=tenant_id,
                action_type=action_type,
            )

        # ── Rule 2: Action type needs human approval ────────────
        elif needs_human_approval(action_type, variant_tier):
            approval_decision = ApprovalDecision.NEEDS_HUMAN_APPROVAL.value
            system_mode = SystemMode.SUPERVISED.value

            logger.info(
                "control_action_needs_approval",
                tenant_id=tenant_id,
                action_type=action_type,
                variant_tier=variant_tier,
            )

        # ── Rule 3: Red flag + pro/high → needs human approval ──
        elif red_flag and variant_tier in ("pro", "high"):
            approval_decision = ApprovalDecision.NEEDS_HUMAN_APPROVAL.value
            system_mode = SystemMode.SUPERVISED.value

            logger.warning(
                "control_red_flag_needs_approval",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                red_flag=red_flag,
            )

        # ── Rule 4: VIP customer + monetary action → approval ───
        if (
            is_vip
            and action_type == "monetary"
            and variant_tier in ("pro", "high")
        ):
            vip_rule_triggered = True
            approval_decision = ApprovalDecision.NEEDS_HUMAN_APPROVAL.value
            system_mode = SystemMode.SUPERVISED.value

            logger.info(
                "control_vip_monetary_rule_triggered",
                tenant_id=tenant_id,
                customer_tier=state.get("customer_tier", "free"),
                action_type=action_type,
            )

        # ── Rule 5: Money rule (high tier: all monetary need review)
        if (
            action_type == "monetary"
            and variant_tier == "high"
            and control_config.get("money_rules", False)
        ):
            money_rule_triggered = True
            approval_decision = ApprovalDecision.NEEDS_HUMAN_APPROVAL.value
            system_mode = SystemMode.SUPERVISED.value

            logger.info(
                "control_money_rule_triggered",
                tenant_id=tenant_id,
                action_type=action_type,
                variant_tier=variant_tier,
            )

        # ── Rule 6: DND applies → defer (auto-approve but mark) ─
        if dnd_applies and approval_decision == ApprovalDecision.APPROVED.value:
            # DND doesn't block, but it defers delivery
            logger.info(
                "control_dnd_deferred",
                tenant_id=tenant_id,
                note="Action approved but delivery deferred due to DND",
            )

        # ── High confidence auto-approve override ────────────────
        # If confidence is very high and no special rules triggered,
        # auto-approve even for pro/high
        if (
            approval_decision == ApprovalDecision.APPROVED.value
            and not vip_rule_triggered
            and not money_rule_triggered
            and not red_flag
            and maker_confidence >= auto_approve_threshold
        ):
            approval_decision = ApprovalDecision.AUTO_APPROVED.value

        # ── Build confidence breakdown ──────────────────────────
        confidence_breakdown = _build_confidence_breakdown(
            agent_confidence=agent_confidence,
            maker_confidence=maker_confidence,
            red_flag=red_flag,
            action_type=action_type,
            variant_tier=variant_tier,
        )

        # ── Build state update ──────────────────────────────────
        result = {
            "approval_decision": approval_decision,
            "confidence_breakdown": confidence_breakdown,
            "system_mode": system_mode,
            "dnd_applies": dnd_applies,
            "money_rule_triggered": money_rule_triggered,
            "vip_rule_triggered": vip_rule_triggered,
            "approval_timeout_seconds": approval_timeout,
        }

        logger.info(
            "control_system_node_success",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            approval_decision=approval_decision,
            system_mode=system_mode,
            money_rule_triggered=money_rule_triggered,
            vip_rule_triggered=vip_rule_triggered,
            dnd_applies=dnd_applies,
            overall_confidence=confidence_breakdown.get("overall", 0.0),
        )

        return result

    except Exception as exc:
        logger.error(
            "control_system_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, default to needs_human_approval
        # (conservative — safer to require human review than auto-approve)
        return {
            **_DEFAULT_CONTROL_STATE,
            "approval_decision": ApprovalDecision.NEEDS_HUMAN_APPROVAL.value,
            "system_mode": SystemMode.SUPERVISED.value,
            "errors": [f"Control system fatal error: {exc}"],
        }
