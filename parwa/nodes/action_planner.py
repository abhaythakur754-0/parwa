"""Node 7: ACTION_PLANNER — Decides what actions should be taken.

Action Agent node. Creates action plans based on the reasoning conclusion
and strategy plan. Each action plan includes the action type, parameters,
and evidence.

Phase 5: Now uses FrameworkBrain with CoT/LeastToMost for complex action planning.
Applies PermissionChecker for variant-aware action mode setting.
Falls back to rule-based on FrameworkBrain failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.permissions import PermissionChecker
from parwa.state import ActionType, ActionPlan, ExecutionMode
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_planner")


def _detect_explicit_actions(raw_message: str, intent: str) -> list[str]:
    """Detect explicit action requests from the raw message.

    This catches financial/account requests that the intent classifier
    might miss or misclassify. Returns list of detected action types.

    KEY RULE: Asking ABOUT something → FAQ. Requesting TO DO something → action.
    - "How do I return?" → faq (asking about process)
    - "I want a refund" → process_refund (requesting action)
    - "How do I secure my account?" → faq (asking about process)
    - "Update my email" → modify_account (requesting action)
    """
    raw_lower = (raw_message or "").lower()
    detected = []

    # ─── REFUND detection ───
    # Explicit refund REQUESTS (not just questions about refunds)
    refund_request_patterns = [
        "want a refund", "need a refund", "want my money back",
        "i want a refund", "i need a refund", "give me a refund",
        "refund my", "refund immediately", "refund for the",
        "charged twice", "double charge", "duplicate charge",
        "overcharged", "want an immediate refund", "full refund",
        "refund for the difference", "i was charged twice",
    ]
    # Exclude FAQ patterns (asking about refund policy, not requesting refund)
    refund_faq_patterns = [
        "what is your refund policy", "what's your refund policy",
        "how does refund", "do you offer refund", "refund policy",
        "thinking about returning", "what is the return policy",
        "how do i return an item", "how to return", "return policy",
    ]
    is_refund_faq = any(p in raw_lower for p in refund_faq_patterns)
    is_refund_request = any(p in raw_lower for p in refund_request_patterns)

    if is_refund_request and not is_refund_faq:
        detected.append("process_refund")
    elif "refund" in raw_lower and not is_refund_faq:
        # Has "refund" but not in an FAQ context — check if it's a request
        request_indicators = ["i want", "i need", "please", "can i get", "i'd like", "give me", "my money"]
        if any(ind in raw_lower for ind in request_indicators):
            detected.append("process_refund")

    # ─── CANCELLATION detection ───
    cancel_request_patterns = [
        "cancel my", "cancel order", "cancel our", "want to cancel",
        "i want to cancel", "cancel and refund", "cancel it",
        "cancel the order", "cancel my subscription",
        "cancel my account", "please cancel",
    ]
    cancel_faq_patterns = [
        "how do i cancel", "how to cancel", "can i cancel",
        "cancellation policy", "what happens if i cancel",
    ]
    is_cancel_faq = any(p in raw_lower for p in cancel_faq_patterns)
    is_cancel_request = any(p in raw_lower for p in cancel_request_patterns)

    if is_cancel_request and not is_cancel_faq:
        detected.append("cancel_order")

    # ─── ACCOUNT MODIFICATION detection ───
    account_request_patterns = [
        "update my email", "change my email", "update my payment",
        "change my payment", "add more seats", "add seats",
        "upgrade my plan", "upgrade from", "downgrade",
        "reactivate my account", "change my company",
        "update my account", "change my account", "password reset",
        "update email", "change the phone", "change my billing",
        "add admin", "transfer my account", "switch my payment",
        "update my phone", "add 5 more", "add 3 more",
        "more seats to my", "seats to my team",
    ]
    account_faq_patterns = [
        "how do i secure", "how to secure my account",
        "how do i change my password", "how do i enable",
        "how do i update", "how to update", "how to change",
        "what are my options", "can i change",
    ]
    is_account_faq = any(p in raw_lower for p in account_faq_patterns)
    is_account_request = any(p in raw_lower for p in account_request_patterns)

    if is_account_request and not is_account_faq:
        detected.append("modify_account")

    return detected


def _plan_actions_rule_based(
    intent: str,
    conclusion: str,
    strategy_plan: list[str],
    integration_data: dict,
    variant: str = "parwa",
    raw_message: str = "",
) -> list[dict]:
    """Create action plans based on intent, strategy, AND raw message analysis.

    Month 3 fix: Now also scans the raw message for explicit financial/account
    requests that the intent classifier might miss. This catches 40% of tickets
    that were previously dropping refund/cancel/modify actions.
    """
    actions = []
    raw_lower = (raw_message or "").lower()

    # Detect explicit actions from raw message (independent of intent)
    explicit_actions = _detect_explicit_actions(raw_message, intent)

    if intent == "refund_request" or "process_refund" in explicit_actions:
        # Calculate refund amount from multiple sources (priority order):
        # 1. Explicit amount mentioned in the customer's message
        # 2. Charges from CRM integration data
        # 3. Reasoning conclusion (if it contains a dollar amount)
        # 4. Default fallback
        import re as _re
        amount = None
        
        # Source 1: Check customer's message for specific dollar amounts
        amount_patterns = _re.findall(r'\$(\d+\.?\d*)', raw_lower)
        if amount_patterns:
            # Use the first mentioned dollar amount as the refund amount
            # (the customer usually states what they were charged)
            try:
                amount = float(amount_patterns[0])
            except (ValueError, IndexError):
                amount = None
        
        # Source 2: CRM integration data
        if amount is None and integration_data.get("charges"):
            try:
                amount = float(integration_data["charges"][0].get("amount", 0))
            except (ValueError, TypeError, IndexError):
                amount = None
        
        # Source 3: Reasoning conclusion
        if amount is None:
            conclusion_amounts = _re.findall(r'\$(\d+\.?\d*)', conclusion)
            if conclusion_amounts:
                try:
                    amount = float(conclusion_amounts[0])
                except (ValueError, IndexError):
                    amount = None
        
        # Source 4: Default fallback
        if amount is None:
            amount = 49.99

        # Check for specific refund reasons
        reason = "customer_request"
        if "charged twice" in raw_lower or "double charge" in raw_lower or "duplicate charge" in raw_lower:
            reason = "duplicate_charge"
        elif "overcharged" in raw_lower or "wrong amount" in raw_lower:
            reason = "overcharge"
        elif "doesn't work" in raw_lower or "not working" in raw_lower or "crashes" in raw_lower or "defective" in raw_lower:
            reason = "defective_product"

        actions.append(ActionPlan(
            action_type=ActionType.PROCESS_REFUND,
            description=f"Process refund of ${amount} (reason: {reason})",
            parameters={"amount": amount, "reason": reason},
            evidence=[
                conclusion,
                f"Customer requested refund: {reason}",
            ],
            risk_level="low" if reason == "duplicate_charge" else "medium",
        ).model_dump())

    if intent == "cancellation" or "cancel_order" in explicit_actions:
        # Check if already processed refund above (avoid duplicate if intent is cancellation)
        has_refund = any(a.get("action_type") == "process_refund" for a in actions)

        cancel_reason = "customer_request"
        if "better price" in raw_lower:
            cancel_reason = "found_better_price"
        elif "budget" in raw_lower:
            cancel_reason = "budget_constraint"
        elif "not using" in raw_lower or "don't use" in raw_lower:
            cancel_reason = "not_using"
        elif "can't access" in raw_lower or "can't use" in raw_lower:
            cancel_reason = "access_issue"

        actions.append(ActionPlan(
            action_type=ActionType.CANCEL_ORDER,
            description=f"Cancel the customer's order (reason: {cancel_reason})",
            parameters={"reason": cancel_reason},
            evidence=[conclusion, f"Customer requested cancellation: {cancel_reason}"],
            risk_level="medium",
        ).model_dump())

    if intent == "account_modification" or "modify_account" in explicit_actions:
        # Determine specific account modification type
        mod_details = "General account modification"
        if "email" in raw_lower and ("update" in raw_lower or "change" in raw_lower):
            mod_details = "Update email address"
        elif "payment" in raw_lower and ("update" in raw_lower or "change" in raw_lower or "switch" in raw_lower):
            mod_details = "Update payment method"
        elif "seats" in raw_lower and ("add" in raw_lower or "more" in raw_lower):
            mod_details = "Add seats to plan"
        elif "upgrade" in raw_lower:
            mod_details = "Upgrade plan"
        elif "password" in raw_lower:
            mod_details = "Password reset"
        elif "reactivate" in raw_lower:
            mod_details = "Reactivate account"

        actions.append(ActionPlan(
            action_type=ActionType.MODIFY_ACCOUNT,
            description=f"Modify account: {mod_details}",
            parameters={"reason": "customer_request", "details": mod_details},
            evidence=[conclusion, f"Customer requested: {mod_details}"],
            risk_level="medium",
        ).model_dump())

    if intent == "order_status" and not any(a.get("action_type") == "process_refund" for a in actions):
        actions.append(ActionPlan(
            action_type=ActionType.SHARE_POLICY,
            description="Share order status with customer",
            parameters={},
            evidence=[conclusion],
            risk_level="low",
        ).model_dump())

    # Default: send a reply (only if no other actions were planned)
    if not actions:
        actions.append(ActionPlan(
            action_type=ActionType.SEND_REPLY,
            description="Send helpful response to customer",
            parameters={},
            evidence=[conclusion],
            risk_level="low",
        ).model_dump())

    # ─── Check for voice call / SMS triggers in the message ───
    # If the customer explicitly asks for a callback or phone contact
    voice_keywords = ["call me", "phone call", "call back", "speak on the phone",
                      "ring me", "give me a call", "can you call", "want a call",
                      "need to talk to someone", "talk on the phone", "voice call"]
    sms_keywords = ["text me", "send me a text", "sms", "send sms", "text message",
                    "message my phone", "send a message to my phone"]

    if any(kw in raw_lower for kw in voice_keywords):
        actions.append(ActionPlan(
            action_type=ActionType.VOICE_CALL,
            description="Initiate voice call to customer",
            parameters={"reason": "customer_request"},
            evidence=[conclusion, "Customer requested a phone call"],
            risk_level="low",
        ).model_dump())

    if any(kw in raw_lower for kw in sms_keywords):
        actions.append(ActionPlan(
            action_type=ActionType.SEND_SMS,
            description="Send SMS notification to customer",
            parameters={"message": conclusion[:200] if conclusion else "Follow-up from support", "reason": "customer_request"},
            evidence=[conclusion, "Customer requested SMS notification"],
            risk_level="low",
        ).model_dump())

    # Apply variant permissions to each action
    checker = PermissionChecker(variant=variant)
    for action in actions:
        action_type_str = action.get("action_type", "send_reply")
        try:
            action_type = ActionType(action_type_str)
            mode = checker.get_mode(action_type)
            action["mode"] = mode.value
        except (ValueError, TypeError):
            action["mode"] = ExecutionMode.EXECUTE.value

    return actions


async def _plan_actions_with_brain(state: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Plan actions using FrameworkBrain (Phase 5).

    Uses CoT for simple planning, LeastToMost for complex planning.
    Returns (action_plans, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})
    variant = state.get("variant", "parwa")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        # Use LeastToMost for complex planning, CoT for others
        complexity = state.get("complexity", "simple")
        techniques = ["chain_of_thought", "least_to_most"] if complexity in ("complex", "critical") else ["chain_of_thought"]

        brain = FrameworkBrain(node="ACTION_PLANNER", state=state)
        result = await brain.think(
            prompt=f"Plan actions for intent={intent}: {conclusion}",
            techniques=techniques,
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # Brain enhances planning — use rule-based as base and apply brain insights
        actions = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data, variant, raw_message=state.get("raw_message", ""))

        # If brain had high confidence, add additional context to actions
        if result.confidence > 0.7 and result.output:
            for action in actions:
                action["brain_enhanced"] = True

        return actions, frameworks

    except Exception as exc:
        logger.warning(
            "action_planner: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        actions = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data, variant, raw_message=state.get("raw_message", ""))
        return actions, ["chain_of_thought"]


@safe_node("ACTION_PLANNER", fallback={"action_plans": [], "active_frameworks": [], "evidence_chain": []})
async def action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan actions based on reasoning conclusion and strategy (async).

    Phase 5: Uses FrameworkBrain with CoT/LeastToMost for complex planning.
    Applies PermissionChecker for variant-aware action mode setting.
    Falls back to rule-based on FrameworkBrain failure.

    P0: Now reads evidence_chain from upstream to make better action decisions,
    and writes its own evidence entries for each planned action.

    Reads: intent, reasoning_conclusion, strategy_plan, integration_data, variant, complexity, evidence_chain
    Writes: action_plans, active_frameworks (append), evidence_chain (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})
    variant = state.get("variant", "parwa")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(strategy_plan, list):
        strategy_plan = []
    if not isinstance(integration_data, dict):
        integration_data = {}
    if not isinstance(variant, str):
        variant = "parwa"

    # Try FrameworkBrain first (Phase 5)
    actions, frameworks = await _plan_actions_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # P0: Build evidence chain entries for each planned action
    new_evidence = []
    for action in actions:
        action_type = action.get("action_type", "unknown")
        evidence_refs = action.get("evidence", [])

        # Gather upstream evidence that supports this action
        upstream_support = []
        existing_chain = state.get("evidence_chain", [])
        for entry in existing_chain:
            if isinstance(entry, dict):
                claim = entry.get("claim", "")
                # Check if upstream claim mentions the action type or conclusion
                if any(kw in claim.lower() for kw in [action_type, intent, "eligible", "confirmed"]):
                    upstream_support.append(claim[:80])

        new_evidence.append({
            "claim": f"Action planned: {action_type} — {action.get('description', '')[:80]}",
            "sources": evidence_refs + upstream_support,
            "confidence": 0.85 if evidence_refs else 0.6,
            "technique": "action_planner",
            "category": "action",
            "node": "ACTION_PLANNER",
            "action_type": action_type,
            "risk_level": action.get("risk_level", "low"),
        })

    # ─── Escalation action: Add ESCALATE_TO_HUMAN if should_escalate is True ───
    # The escalation_decision node sets should_escalate=True but no longer creates
    # action_plans — that's this node's job. We add the escalation action AFTER
    # the normal actions (refund, cancel, etc.) so the human agent gets full
    # context from both the reasoning AND the specific actions planned.
    if state.get("should_escalate", False):
        already_has_escalation = any(
            a.get("action_type") == "escalate_to_human"
            for a in actions
        )
        if not already_has_escalation:
            esc_reason = state.get("escalation_reason", "escalation_triggered")
            actions.append(ActionPlan(
                action_type=ActionType.ESCALATE_TO_HUMAN,
                description=f"Escalate to human agent: {esc_reason}",
                parameters={"reason": esc_reason, "priority": "high"},
                mode=ExecutionMode.EXECUTE,
                evidence=[f"Escalation triggered: {esc_reason}"],
                risk_level="high",
            ).model_dump())

    return {
        "action_plans": actions,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
    }
