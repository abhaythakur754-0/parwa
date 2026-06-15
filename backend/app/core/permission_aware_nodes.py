"""
Permission-Aware Node Wrappers — Adds task permission checks to pipeline nodes.

These wrappers sit on top of the existing node implementations and add
permission checks. If a variant doesn't have permission for a task,
the wrapper handles the escalation/refusal gracefully.

Architecture:
  Original Node → Permission Wrapper → Permission Check
                                  ↓                    ↓
                              ALLOWED             NOT ALLOWED
                                  ↓                    ↓
                            Run Original         Handle Restriction
                              Node Logic         (escalate/refuse)

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from app.core.parwa_graph_state import ParwaGraphState, append_audit_entry
from app.core.variant_permissions import (
    ActionLevel,
    TaskType,
    check_task_permission,
    check_monetary_permission,
    get_permissions,
    get_escalation_message,
)
from app.logger import get_logger

logger = get_logger("permission_aware_nodes")


# ══════════════════════════════════════════════════════════════════
# INTENT → TASK TYPE MAPPING
# ══════════════════════════════════════════════════════════════════

INTENT_TASK_MAP: Dict[str, TaskType] = {
    "refund": TaskType.REFUND_REQUEST,
    "refund_request": TaskType.REFUND_REQUEST,
    "partial_refund": TaskType.PARTIAL_REFUND,
    "chargeback": TaskType.CHARGEBACK,
    "cancellation": TaskType.CANCELLATION,
    "cancel": TaskType.CANCELLATION,
    "downgrade": TaskType.DOWNGRADE,
    "billing": TaskType.BILLING_INQUIRY,
    "payment": TaskType.PAYMENT_ISSUE,
    "invoice": TaskType.INVOICE_REQUEST,
    "overcharge": TaskType.OVERCHARGE,
    "subscription": TaskType.SUBSCRIPTION_CHANGE,
    "complaint": TaskType.COMPLAINT,
    "feedback": TaskType.FEEDBACK,
    "technical": TaskType.TECHNICAL_SUPPORT,
    "bug": TaskType.BUG_REPORT,
    "shipping": TaskType.SHIPPING_INFO,
    "delivery": TaskType.SHIPPING_INFO,
    "tracking": TaskType.TRACKING,
    "order": TaskType.ORDER_STATUS,
    "how_to": TaskType.HOW_TO,
    "general_inquiry": TaskType.GENERAL_INQUIRY,
    "faq": TaskType.FAQ,
    "greeting": TaskType.GREETING,
    "escalation": TaskType.ESCALATION,
    "legal_threat": TaskType.LEGAL_THREAT,
    "safety_concern": TaskType.SAFETY_CONCERN,
}


def _get_task_type_from_state(state: ParwaGraphState) -> TaskType:
    """Extract the task type from the current state's classification."""
    try:
        classification = state.get("classification", {})
        intent = classification.get("intent", "general_inquiry").lower()
        return INTENT_TASK_MAP.get(intent, TaskType.GENERAL_INQUIRY)
    except Exception:
        return TaskType.GENERAL_INQUIRY


def _handle_restricted_task(
    state: ParwaGraphState,
    task_type: TaskType,
    action_level: ActionLevel,
    node_name: str,
) -> Dict[str, Any]:
    """Handle a task that the variant doesn't have permission for.

    Instead of skipping the node, we:
    1. Acknowledge the customer's need (same intelligence)
    2. Check what the variant IS allowed to do
    3. Either escalate or refuse with explanation

    Returns:
        Dict to merge into state with appropriate response.
    """
    try:
        variant_tier = state.get("variant_tier", "parwa")
        company_id = state.get("company_id", "")

        escalation_msg = get_escalation_message(variant_tier, task_type)

        result: Dict[str, Any] = {
            "permission_checked": True,
            "permission_action": action_level.value,
            "permission_task_type": task_type.value,
            "permission_node": node_name,
        }

        if action_level == ActionLevel.INFORM_AND_ESCALATE:
            # Variant understands the issue but can't handle it → escalate
            result["escalation_needed"] = True
            result["escalation_reason"] = f"task_restricted:{task_type.value}"
            result["escalation_message"] = escalation_msg
            result["pipeline_status"] = "escalated"

            # Still provide a helpful response to the customer
            result["response_text"] = escalation_msg

            logger.info(
                "permission_escalation: variant=%s task=%s node=%s company=%s",
                variant_tier, task_type.value, node_name, company_id,
            )

        elif action_level == ActionLevel.REFUSE_WITH_EXPLANATION:
            # Variant can't handle this at all → explain and offer alternatives
            result["response_text"] = (
                f"{escalation_msg} "
                "In the meantime, is there anything else I can help you with?"
            )
            result["escalation_needed"] = True
            result["escalation_reason"] = f"task_refused:{task_type.value}"

            logger.info(
                "permission_refuse: variant=%s task=%s node=%s company=%s",
                variant_tier, task_type.value, node_name, company_id,
            )

        elif action_level == ActionLevel.ALLOW_WITH_LIMIT:
            # Variant can handle with limits → proceed but note the limitation
            result["permission_limited"] = True
            result["permission_note"] = (
                f"Handling {task_type.value} with variant limitations"
            )

        # ALLOW → nothing extra needed, node runs normally

        return result

    except Exception:
        logger.exception("handle_restricted_task failed")
        return {
            "permission_checked": True,
            "permission_action": "error",
            "error": "permission_check_failed",
        }


# ══════════════════════════════════════════════════════════════════
# PERMISSION-AWARE WRAPPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def make_permission_aware_node(
    original_node: Callable,
    node_name: str,
    *,
    restricted_intents: Optional[list] = None,
) -> Callable:
    """Create a permission-aware wrapper around an existing node.

    The wrapper:
    1. Checks if the variant has permission for the current task
    2. If allowed → runs the original node
    3. If not allowed → handles escalation/refusal

    Args:
        original_node: The original node function.
        node_name: The node name for logging.
        restricted_intents: Optional list of intents that need permission checks.

    Returns:
        Wrapped node function.
    """
    async def wrapped_node(state: ParwaGraphState) -> Dict[str, Any]:
        try:
            variant_tier = state.get("variant_tier", "parwa")
            task_type = _get_task_type_from_state(state)

            # Check if this intent needs permission checking
            needs_check = True
            if restricted_intents is not None:
                classification = state.get("classification", {})
                intent = classification.get("intent", "").lower()
                needs_check = intent in restricted_intents

            if needs_check:
                action_level = check_task_permission(variant_tier, task_type)

                if action_level in (ActionLevel.INFORM_AND_ESCALATE, ActionLevel.REFUSE_WITH_EXPLANATION):
                    # Variant can't handle this task → handle restriction
                    restriction_result = _handle_restricted_task(
                        state, task_type, action_level, node_name
                    )

                    # Run the original node but it will see the escalation flag
                    # and adjust its behavior (still runs for analysis/intelligence)
                    original_result = await original_node(state) if asyncio.iscoroutinefunction(original_node) else original_node(state)

                    if isinstance(original_result, dict):
                        original_result.update(restriction_result)
                        return original_result
                    return restriction_result

            # Allowed or limited → run original node
            if asyncio.iscoroutinefunction(original_node):
                return await original_node(state)
            else:
                return original_node(state)

        except Exception:
            logger.exception("permission_aware_node failed: node=%s", node_name)
            # Fallback to original node without permission check
            if asyncio.iscoroutinefunction(original_node):
                return await original_node(state)
            else:
                return original_node(state)

    return wrapped_node


# ══════════════════════════════════════════════════════════════════
# SPECIFIC NODE PERMISSION WRAPPERS
# ══════════════════════════════════════════════════════════════════


async def billing_resolver_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Billing resolver with permission checks.

    Mini: Can't process refunds → escalates
    Pro: Can process refunds under $500
    High: Can process any refund
    """
    try:
        from app.core.parwa_high.nodes import billing_resolver_node

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)
        task_type = _get_task_type_from_state(state)
        action_level = check_task_permission(variant_tier, task_type)

        if action_level in (ActionLevel.INFORM_AND_ESCALATE, ActionLevel.REFUSE_WITH_EXPLANATION):
            # Variant can't handle this billing task
            restriction = _handle_restricted_task(state, task_type, action_level, "billing_resolver")

            # Still run the node for ANALYSIS (same intelligence) but flag as escalated
            result = await billing_resolver_node(state)
            if isinstance(result, dict):
                result.update(restriction)
                result["billing_action_taken"] = "none"  # No action, just analysis
                return result
            return restriction

        # Check monetary limits for refunds
        if task_type in (TaskType.REFUND_REQUEST, TaskType.PARTIAL_REFUND):
            # Extract monetary value from signals
            signals = state.get("signals", {})
            monetary_value = 0.0
            if isinstance(signals, dict):
                monetary_value = float(signals.get("monetary_value", 0) or 0)

            if monetary_value > 0:
                monetary_action = check_monetary_permission(variant_tier, "refund", monetary_value)
                if monetary_action == ActionLevel.INFORM_AND_ESCALATE:
                    result = await billing_resolver_node(state)
                    if isinstance(result, dict):
                        result["billing_action_taken"] = "escalated_over_limit"
                        result["escalation_reason"] = f"refund_amount_{monetary_value}_exceeds_{perms.max_refund_amount}"
                        return result

        # Allowed → run original node
        return await billing_resolver_node(state)

    except Exception:
        logger.exception("billing_resolver_with_permissions failed")
        from app.core.parwa_high.nodes import billing_resolver_node
        return await billing_resolver_node(state)


async def retention_negotiator_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Retention negotiator with permission checks.

    Mini: Can't handle cancellations → escalates
    Pro: Can handle cancellations but needs approval
    High: Can handle cancellations fully
    """
    try:
        from app.core.parwa_high.nodes import retention_negotiator_node

        variant_tier = state.get("variant_tier", "parwa")
        task_type = _get_task_type_from_state(state)
        action_level = check_task_permission(variant_tier, task_type)

        if action_level in (ActionLevel.INFORM_AND_ESCALATE, ActionLevel.REFUSE_WITH_EXPLANATION):
            restriction = _handle_restricted_task(state, task_type, action_level, "retention_negotiator")

            # Run for analysis but flag as escalated
            result = await retention_negotiator_node(state)
            if isinstance(result, dict):
                result.update(restriction)
                result["retention_action_taken"] = "none"
                return result
            return restriction

        # Check if variant can cancel subscriptions
        perms = get_permissions(variant_tier)
        if not perms.can_cancel_subscription:
            result = await retention_negotiator_node(state)
            if isinstance(result, dict):
                result["retention_action_taken"] = "negotiated_no_cancel"
                result["needs_approval"] = True
                return result

        return await retention_negotiator_node(state)

    except Exception:
        logger.exception("retention_negotiator_with_permissions failed")
        from app.core.parwa_high.nodes import retention_negotiator_node
        return await retention_negotiator_node(state)


async def auto_action_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Auto action with permission checks.

    Mini: Can only escalate to human
    Pro: Can apply credits, send emails
    High: Can do everything
    """
    try:
        from app.core.parwa_high.nodes import auto_action_node

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)

        # Run the original node to get proposed actions
        result = await auto_action_node(state)

        if not isinstance(result, dict):
            return result

        # Filter actions based on permissions
        proposed_actions = result.get("proposed_actions", [])
        filtered_actions = []
        blocked_actions = []

        for action in proposed_actions:
            action_type = action.get("type", "") if isinstance(action, dict) else str(action)

            if action_type == "refund" and not perms.can_issue_refund:
                blocked_actions.append(action)
                continue
            if action_type == "cancel_subscription" and not perms.can_cancel_subscription:
                blocked_actions.append(action)
                continue
            if action_type == "apply_credit" and not perms.can_apply_credit:
                blocked_actions.append(action)
                continue
            if action_type == "change_plan" and not perms.can_change_plan:
                blocked_actions.append(action)
                continue
            if action_type == "send_email" and not perms.can_send_email:
                blocked_actions.append(action)
                continue
            if action_type == "phone_call" and not perms.can_make_phone_call:
                blocked_actions.append(action)
                continue

            # Check monetary limits
            if action_type in ("refund", "apply_credit"):
                amount = float(action.get("amount", 0)) if isinstance(action, dict) else 0
                monetary_check = check_monetary_permission(
                    variant_tier,
                    action_type,
                    amount,
                )
                if monetary_check == ActionLevel.INFORM_AND_ESCALATE:
                    blocked_actions.append(action)
                    continue

            filtered_actions.append(action)

        result["proposed_actions"] = filtered_actions
        result["blocked_actions"] = blocked_actions
        result["permission_filtered"] = len(blocked_actions) > 0

        if blocked_actions:
            result["needs_human_approval"] = True
            logger.info(
                "auto_action_blocked: variant=%s blocked=%d allowed=%d company=%s",
                variant_tier, len(blocked_actions), len(filtered_actions),
                state.get("company_id", ""),
            )

        return result

    except Exception:
        logger.exception("auto_action_with_permissions failed")
        from app.core.parwa_high.nodes import auto_action_node
        return await auto_action_node(state)


async def generate_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Generate node with permission-aware model selection.

    ALL variants use the same generation logic but with different
    model tiers for cost optimization. The intelligence is the same —
    just the model size differs.
    """
    try:
        from app.core.parwa_high.nodes import generate_node
        from app.core.variant_permissions import get_permissions

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)

        # Inject permission info into state for the generate node
        enhanced_state = dict(state)
        enhanced_state["_permission_model_tier"] = perms.model_tier
        enhanced_state["_permission_clara_threshold"] = perms.clara_threshold

        # Check if this is an escalation scenario
        if state.get("escalation_needed", False):
            # Use the escalation message as the response
            escalation_msg = state.get("escalation_message", "")
            if escalation_msg:
                return {
                    "response_text": escalation_msg,
                    "generation_method": "permission_escalation",
                    "generation_tokens": 0,
                }

        return await generate_node(enhanced_state)

    except Exception:
        logger.exception("generate_with_permissions failed")
        from app.core.parwa_high.nodes import generate_node
        return await generate_node(state)


async def clara_quality_gate_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """CLARA quality gate with variant-specific thresholds.

    ALL variants now go through quality checks. The threshold differs:
      - Mini: 70 (lighter but still quality-checked)
      - Pro: 85 (standard)
      - High: 95 (strictest)
    """
    try:
        from app.core.parwa_high.nodes import clara_quality_gate_node
        from app.core.variant_permissions import get_permissions

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)

        # Inject variant-specific threshold into state
        enhanced_state = dict(state)
        enhanced_state["_clara_threshold_override"] = perms.clara_threshold

        return await clara_quality_gate_node(enhanced_state)

    except Exception:
        logger.exception("clara_quality_gate_with_permissions failed")
        from app.core.parwa_high.nodes import clara_quality_gate_node
        return await clara_quality_gate_node(state)


async def classify_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Classify node — ALL variants now use AI classification.

    Previously Mini used keyword-only classification.
    Now ALL variants use the same AI-powered classification.
    """
    try:
        from app.core.parwa_high.nodes import classify_node

        # All variants use AI classification now
        return await classify_node(state)

    except Exception:
        logger.exception("classify_with_permissions failed")
        from app.core.parwa_high.nodes import classify_node
        return await classify_node(state)


async def technique_select_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Technique selection — ALL variants now get ALL technique tiers.

    Previously Mini got no techniques, Pro got Tier 1+2, High got all.
    Now ALL variants get Tier 1+2+3 techniques (same intelligence).
    """
    try:
        from app.core.parwa_high.nodes import technique_select_node
        from app.core.variant_permissions import get_permissions

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)

        # Inject that ALL tiers are available
        enhanced_state = dict(state)
        enhanced_state["_enabled_technique_tiers"] = sorted(perms.enabled_technique_tiers)

        return await technique_select_node(enhanced_state)

    except Exception:
        logger.exception("technique_select_with_permissions failed")
        from app.core.parwa_high.nodes import technique_select_node
        return await technique_select_node(state)


async def reasoning_chain_with_permissions(state: ParwaGraphState) -> Dict[str, Any]:
    """Reasoning chain — ALL variants now execute reasoning techniques.

    ALL variants execute CoT, ReAct, ToT, UoT, GST, etc.
    Same reasoning depth and intelligence across all tiers.
    """
    try:
        from app.core.parwa_high.nodes import reasoning_chain_node

        return await reasoning_chain_node(state)

    except Exception:
        logger.exception("reasoning_chain_with_permissions failed")
        from app.core.parwa_high.nodes import reasoning_chain_node
        return await reasoning_chain_node(state)


# ══════════════════════════════════════════════════════════════════
# EXPORTS — Permission-aware node functions for the unified graph
# ══════════════════════════════════════════════════════════════════

# These can be used as drop-in replacements in the unified graph
# for nodes that need permission checks

PERMISSION_AWARE_NODES = {
    "billing_resolver": billing_resolver_with_permissions,
    "retention_negotiator": retention_negotiator_with_permissions,
    "auto_action": auto_action_with_permissions,
    "generate": generate_with_permissions,
    "clara_quality_gate": clara_quality_gate_with_permissions,
    "classify": classify_with_permissions,
    "technique_select": technique_select_with_permissions,
    "reasoning_chain": reasoning_chain_with_permissions,
}
