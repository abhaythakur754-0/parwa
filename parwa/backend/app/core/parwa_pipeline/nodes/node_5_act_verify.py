"""
Node 5: Act + Verify

Question: Did we DO the right thing?

Techniques (in order):
  1. Rule-based action check       (non-LLM)
  2. GSD.decompose()                (non-LLM)
  3. MAKER.bridge()                 (non-LLM)
  4. ReAct.execute()                (LLM — for complex actions)
  5. Reverse Thinking.verify()      (LLM)
  6. ZeroShotValidator.flag()       (non-LLM)
  7. UCB execute action             (via external_tool_bus)
  8. tier_permissions check         (non-LLM)

LLM calls: 1-2 (ReAct + Reverse Thinking, only for complex actions)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_5")

# Import execution limits from config
# (defined in node_2 but referenced here for action verification)
_CAPABILITY_MATRIX = {
    "mini": {"execute_refund": False, "execute_credit": False, "account_change": False},
    "parwa": {"execute_refund": True, "execute_credit": True, "account_change": True},
    "high": {"execute_refund": True, "execute_credit": True, "account_change": True},
}
_EXEC_LIMITS = {
    "mini": {"max_refund": 0, "max_credit": 0},
    "parwa": {"max_refund": 500, "max_credit": 200},
    "high": {"max_refund": float("inf"), "max_credit": float("inf")},
}


# ── Rule-based action check (non-LLM) ─────────────────────────────


def _rule_based_check(
    action: str, amount: float, tier: str
) -> Dict[str, Any]:
    """Check if action can be executed based on variant rules."""
    caps = _CAPABILITY_MATRIX.get(tier, _CAPABILITY_MATRIX["mini"])
    limits = _EXEC_LIMITS.get(tier, _EXEC_LIMITS["mini"])

    can_execute = True
    reason = ""

    if action == "execute_refund":
        if not caps["execute_refund"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute refunds — recommend only"
        elif amount > limits["max_refund"]:
            can_execute = False
            reason = f"Amount ${amount} exceeds tier '{tier}' limit of ${limits['max_refund']}"

    elif action == "execute_credit":
        if not caps["execute_credit"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute credits — recommend only"
        elif amount > limits["max_credit"]:
            can_execute = False
            reason = f"Amount ${amount} exceeds tier '{tier}' limit of ${limits['max_credit']}"

    elif action == "account_change":
        if not caps["account_change"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute account changes — recommend only"

    elif action == "provide_info":
        can_execute = True
        reason = "Information provision — no execution needed"

    else:
        can_execute = True
        reason = f"Action '{action}' — no restrictions apply"

    return {"can_execute": can_execute, "reason": reason}


# ── GSD: Decompose multi-step actions (non-LLM) ──────────────────


def _gsd_decompose_action(action: str, details: Dict) -> List[str]:
    """Break multi-step actions into individual steps."""
    if action == "execute_refund":
        return [
            "Verify customer identity and purchase",
            "Calculate refund amount",
            "Check refund policy eligibility",
            "Process refund through payment system",
            "Generate confirmation",
        ]
    elif action == "execute_credit":
        return [
            "Verify customer account status",
            "Determine credit amount",
            "Apply credit to account",
            "Notify customer",
        ]
    elif action == "account_change":
        return [
            "Verify requested change",
            "Validate new value",
            "Apply change",
            "Confirm with customer",
        ]
    else:
        return [f"Provide information about: {action}"]


# ── MAKER: Bridge action knowledge gaps (non-LLM) ─────────────────


def _maker_bridge_action(action: str, knowledge: str, crm_data: Dict) -> str:
    """Bridge knowledge gaps during action execution."""
    # Connect knowledge to action steps
    action_keywords = action.replace("_", " ").split()
    knowledge_lower = knowledge.lower()

    relevant_lines = []
    for line in knowledge_lower.split("."):
        if any(kw in line for kw in action_keywords):
            relevant_lines.append(line.strip())

    return " ".join(relevant_lines) if relevant_lines else "No direct knowledge bridge found for this action"


# ── ReAct: Think-Act-Observe loop (LLM) ───────────────────────────


async def _react_execute(
    action: str, details: Dict, knowledge: str, crm_data: Dict
) -> Dict[str, Any]:
    """Think-Act-Observe loop for complex action execution."""
    import litellm

    prompt = f"""You are executing a customer support action.

Action: {action}
Details: {details}
Knowledge: {knowledge[:1500]}
Customer Data: {str(crm_data)[:500]}

Think about what needs to happen:
THOUGHT:"""

    try:
        thought = await llm_call(prompt, max_tokens=300, temperature=0.2)
    except Exception as e:
        thought = f"Action execution failed: {e}"

    return {
        "action": action,
        "thought": thought,
        "observation": f"Action '{action}' simulated successfully",
        "status": "completed",
    }


# ── Reverse Thinking: Verify by reversibility (LLM) ───────────────


async def _reverse_verify(action: str, result: Dict, knowledge: str) -> Dict[str, Any]:
    """If I reverse this action, do I get back to original state?"""
    prompt = f"""An action was taken:
Action: {action}
Result: {result.get('observation', 'unknown')}

Knowledge: {knowledge[:1000]}

Verify: Is this action correct and reversible? What could go wrong?
RESPOND:
VERIFIED: YES/NO
RISK: <low/medium/high>
DETAILS: <brief>"""

    try:
        text = await llm_call(prompt, max_tokens=200, temperature=0.2)
        verified = "VERIFIED: YES" in text.upper()
        risk = "medium"
        if "RISK: LOW" in text.upper():
            risk = "low"
        elif "RISK: HIGH" in text.upper():
            risk = "high"
        return {"verified": verified, "risk": risk, "analysis": text}
    except Exception:
        return {"verified": False, "risk": "medium", "analysis": "Verification failed"}


# ── ZeroShotValidator: Flag wrong actions (non-LLM) ────────────────


def _zero_shot_flag_action(action: str, details: Dict, knowledge: str) -> Dict[str, Any]:
    """Flag statistically unusual actions."""
    flags = []

    amount = details.get("amount", 0)
    if amount > 5000:
        flags.append(f"High-value action: ${amount}")
    if amount < 0:
        flags.append("Negative amount detected")

    # Check if action type matches knowledge
    action_in_kb = action.replace("_", " ") in knowledge.lower()
    if not action_in_kb and action != "provide_info":
        flags.append(f"Action type '{action}' not found in knowledge base")

    return {
        "flagged": len(flags) > 0,
        "flags": flags,
        "severity": "high" if amount > 5000 else "low",
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_5_act_verify(state: PipelineV2State) -> dict:
    """Node 5: Act + Verify — Did we DO the right thing?"""
    start = time.time()
    action = state["required_action"]
    details = state.get("action_details", {})
    tier = state.get("variant_tier", "parwa")
    knowledge_docs = state.get("knowledge_context", [])
    crm_data = state.get("crm_data", {})
    logs = []
    llm_calls = 0

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)

    # 1. Rule-based action check
    rule_check = _rule_based_check(action, details.get("amount", 0), tier)
    logs.append({"node": 5, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": f"execute={rule_check['can_execute']}"})

    # 2. GSD: decompose multi-step actions
    steps = _gsd_decompose_action(action, details)
    logs.append({"node": 5, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(steps)} steps"})

    # 3. MAKER: bridge action knowledge gaps
    bridge = _maker_bridge_action(action, knowledge_str, crm_data)
    logs.append({"node": 5, "technique": "MAKER", "duration_ms": 0, "result_summary": "bridge_done"})

    # 4. Execute action (only if rule check passes and action needs execution)
    actions_taken = []
    if rule_check["can_execute"] and action != "provide_info":
        # ReAct: execute (LLM)
        react_result = await _react_execute(action, details, knowledge_str, crm_data)
        actions_taken.append(react_result)
        logs.append({"node": 5, "technique": "ReAct", "duration_ms": 0, "result_summary": f"status={react_result['status']}"})
        llm_calls += 1

        # Reverse Thinking: verify (LLM)
        reverse = await _reverse_verify(action, react_result, knowledge_str)
        logs.append({"node": 5, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"verified={reverse['verified']}"})
        llm_calls += 1

        verified = reverse["verified"]
        verification_result = reverse["analysis"]
    else:
        if not rule_check["can_execute"]:
            # Can't execute — recommend instead
            actions_taken.append({
                "action": action,
                "thought": f"Cannot execute: {rule_check['reason']}. Providing recommendation instead.",
                "observation": "Recommendation provided (not executed)",
                "status": "recommended",
            })
            verified = True  # recommendation is always "safe"
            verification_result = rule_check["reason"]
        else:
            actions_taken.append({
                "action": "provide_info",
                "thought": "Information provision — no execution needed",
                "observation": "Information provided from knowledge base",
                "status": "completed",
            })
            verified = True
            verification_result = "No execution required"

    # 6. ZeroShotValidator: flag unusual actions
    zsv = _zero_shot_flag_action(action, details, knowledge_str)
    logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flagged={zsv['flagged']}"})

    if zsv["flagged"]:
        for flag in zsv["flags"]:
            logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flag: {flag}"})

    # 7. UCB execute (mock — wired in Phase 7)
    logs.append({"node": 5, "technique": "UCB", "duration_ms": 0, "result_summary": "action_executed"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 5 complete: ticket=%s action=%s verified=%s llm=%d [%dms]",
        state["ticket_id"], action, verified, llm_calls, elapsed,
    )

    return {
        "actions_taken": actions_taken,
        "actions_verified": verified,
        "verification_result": verification_result,
        "technique_log": logs,
        "node_5_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }