"""Billing Subgraph — Enhanced pipeline with self-correction and quality loop-back.

11-node pipeline focused on charge verification with self-correction:

  INTENT_CONFIRM → BILLING_VERIFY → KB_RETRIEVER → REASONING_ENGINE
      → REVERSE_THINKER → SELF_CORRECTION → ACTION_PLANNER → ACTION_EXECUTOR
      → QUALITY_SCORER → RESPONSE_FORMATTER → END
                                          ↑_______________|
                                    (if quality < 80 and attempts < 2, loop back to REASONING_ENGINE)

v3 Improvements:
  - Added REVERSE_THINKER for "what if this charge is actually correct?" validation
  - Added SELF_CORRECTION node that enriches reasoning with alternative perspective
  - Added quality loop-back: if quality < 80, re-reason with correction context
  - Up to 2 retry loops before accepting the response
  - Better quality scorer with billing-specific signals
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.billing")


async def _billing_intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm billing intent and extract billing details."""
    message = state.get("raw_message", "").lower()
    updates: dict[str, Any] = {}

    # Detect billing issue type
    issue_types = {
        "unexpected_charge": ["unexpected", "unknown charge", "didn't authorize", "random charge"],
        "overcharge": ["overcharged", "too much", "charged twice", "double charge"],
        "failed_payment": ["payment failed", "card declined", "couldn't charge"],
        "subscription_change": ["upgrade", "downgrade", "change plan", "switch plan"],
        "invoice_question": ["invoice", "receipt", "billing statement", "what was i charged"],
        "refund_billing": ["refund", "credit", "money back"],
    }

    detected_issues = []
    for issue_type, keywords in issue_types.items():
        if any(kw in message for kw in keywords):
            detected_issues.append(issue_type)

    if detected_issues:
        updates["_billing_issue_type"] = detected_issues
    else:
        updates["_billing_issue_type"] = ["general_billing"]

    # Detect amount mentions
    amount_match = re.search(r'\$?(\d+\.?\d*)', message)
    if amount_match:
        updates["_mentioned_amount"] = float(amount_match.group(1))

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["billing_subgraph"]
    updates["_reasoning_attempts"] = 0  # Initialize counter for quality loop-back
    return updates


async def _billing_verify(state: dict[str, Any]) -> dict[str, Any]:
    """Verify the billing issue against known plans and charges."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import BILLING_REASONING_PROMPT

        brain = FrameworkBrain(node="BILLING_VERIFY", state=state)
        prompt = BILLING_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            plan="standard",
            charges="recent charges to be verified",
        )

        result = await brain.think(
            prompt=prompt,
            techniques=["chain_of_thought", "self_consistency"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        output = result.output.lower() if result.output else ""
        if "incorrect" in output or "error" in output or "overcharge" in output:
            charge_status = "potentially_incorrect"
        elif "correct" in output or "matches" in output or "valid" in output:
            charge_status = "appears_correct"
        else:
            charge_status = "needs_review"

        return {
            "_charge_verification": charge_status,
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:500] if result.output else "",
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("billing_verify: brain failed: %s", exc)
        return {
            "_charge_verification": "needs_review",
            "reasoning_conclusion": "Verification inconclusive",
        }


async def _billing_kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """KB retrieval with billing-specific search boosting."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import BILLING_KB_ENHANCEMENT_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques, get_subgraph_kb_boosts

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        techniques = get_subgraph_techniques("billing", "KB_RETRIEVER")
        prompt = BILLING_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["hyde", "multi_query"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        kb_results = []
        boosts = get_subgraph_kb_boosts("billing")

        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()
            search_query = state.get("raw_message", "")
            issue_types = state.get("_billing_issue_type", [])
            if issue_types:
                search_query += " " + " ".join(issue_types)

            original_results = crm.search_kb(search_query, top_k=3)
            kb_results.extend(original_results)

            for boost_term, weight in boosts.items():
                boost_results = crm.search_kb(f"{search_query} {boost_term}", top_k=2)
                for r in boost_results:
                    r.relevance_score = min(r.relevance_score + weight, 1.0)
                kb_results.extend(boost_results)

        except ImportError:
            pass

        seen = set()
        unique_results = []
        for r in kb_results:
            if r.source not in seen:
                seen.add(r.source)
                unique_results.append(r)

        return {
            "kb_results": [{"source": r.source, "content": r.content, "relevance_score": r.relevance_score} for r in unique_results[:5]],
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("billing_kb_retriever: failed: %s", exc)
        return {"kb_results": []}


async def _billing_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """Billing-specialized reasoning with verification technique priority."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.technique_configs import get_subgraph_techniques

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        techniques = get_subgraph_techniques("billing", "REASONING_ENGINE")

        kb_context = "\n".join([
            r.get("content", "") if isinstance(r, dict) else str(r)
            for r in state.get("kb_results", [])[:3]
        ])

        prompt = f"""Analyze this billing issue step by step.

Customer message: {state.get('raw_message', '')}
Billing issue type: {state.get('_billing_issue_type', [])}
Charge verification: {state.get('_charge_verification', 'unknown')}
Amount mentioned: {state.get('_mentioned_amount', 'not specified')}

Knowledge Base Context:
{kb_context[:1000]}

Provide:
1. What specific charge or billing concern the customer has
2. Whether the charge appears correct based on our pricing
3. If incorrect, what adjustment is needed
4. What the customer should expect on their next invoice"""

        # If this is a retry, include correction context
        correction = state.get("_correction_context", "")
        if correction:
            prompt += f"\n\nSELF-CORRECTION CONTEXT (previous attempt was insufficient):\n{correction[:500]}"

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:500] if result.output else "",
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
            "_reasoning_attempts": state.get("_reasoning_attempts", 0) + 1,
        }

    except Exception as exc:
        logger.warning("billing_reasoning: brain failed: %s", exc)
        return {
            "reasoning_conclusion": "Billing reasoning inconclusive",
            "_reasoning_attempts": state.get("_reasoning_attempts", 0) + 1,  # CRITICAL: always increment to prevent infinite loop
        }


async def _billing_reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """v3 NEW: Reverse thinking — what if this charge is actually correct?

    Validates the billing reasoning by considering the opposite perspective.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REVERSE_THINKER", state=state)
        conclusion = state.get("reasoning_conclusion", "")
        charge_status = state.get("_charge_verification", "needs_review")

        prompt = f"""Consider this billing decision from the OPPOSITE perspective.

Original assessment: Charge appears {charge_status}.
Original reasoning: {conclusion[:400]}

Think about:
1. What if this charge IS correct and the customer is mistaken?
2. What if the charge is for a feature/plan they forgot about?
3. What if the timing or proration explains the amount?
4. What evidence would prove or disprove the charge is correct?

Provide your alternative analysis:"""

        result = await brain.think_single(
            "reverse_thinking",
            prompt=prompt,
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reverse_validation": {"alternative_analysis": result.output[:400] if result.output else ""},
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("billing_reverse_thinker: failed: %s", exc)
        return {"reverse_validation": {}}


async def _billing_self_correction(state: dict[str, Any]) -> dict[str, Any]:
    """v3 NEW: Self-correction — re-reason if the response seems insufficient."""
    conclusion = state.get("reasoning_conclusion", "")
    attempts = state.get("_reasoning_attempts", 0)

    # Quality pre-check
    has_amount = any(kw in conclusion.lower() for kw in ["$", "charge", "amount", "credit", "invoice"])
    has_explanation = any(kw in conclusion.lower() for kw in ["because", "due to", "reason", "caused by", "explanation"])
    has_resolution = any(kw in conclusion.lower() for kw in ["adjust", "refund", "credit", "correct", "update", "resolve"])

    # If response looks good, pass through
    if has_amount and has_explanation and has_resolution:
        return {"_self_correction_applied": False}

    # Don't loop more than twice
    if attempts >= 2:
        return {"_self_correction_applied": False}

    # Apply correction
    reverse = state.get("reverse_validation", {})
    alt_analysis = reverse.get("alternative_analysis", "")

    correction_context = ""
    if alt_analysis and len(alt_analysis) > 30:
        correction_context = f"Previous reasoning may be incomplete. Alternative perspective: {alt_analysis[:300]}"

    return {
        "_correction_context": correction_context,
        "_self_correction_applied": bool(correction_context),
        "active_frameworks": state.get("active_frameworks", []) + ["self_correction"],
    }


async def _billing_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan billing actions."""
    charge_status = state.get("_charge_verification", "needs_review")
    conclusion = state.get("reasoning_conclusion", "")
    issue_types = state.get("_billing_issue_type", [])

    actions = []

    if charge_status == "potentially_incorrect":
        actions.append({
            "action_type": "process_refund",
            "description": "Issue credit for incorrect charge",
            "parameters": {"reason": "Charge verification failed", "issue_types": issue_types},
            "evidence": conclusion[:200] if conclusion else "",
            "risk_level": "medium",
        })
    elif charge_status == "appears_correct":
        actions.append({
            "action_type": "send_reply",
            "description": "Explain the charge to the customer",
            "parameters": {"explanation": conclusion[:300] if conclusion else "Charge is correct per plan"},
            "evidence": conclusion[:200] if conclusion else "",
            "risk_level": "low",
        })
    else:
        actions.append({
            "action_type": "escalate_to_human",
            "description": "Billing review needed — charge status unclear",
            "parameters": {"reason": "Charge verification inconclusive"},
            "evidence": conclusion[:200] if conclusion else "",
            "risk_level": "medium",
        })

    return {"action_plans": actions}


async def _billing_action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute billing actions."""
    plans = state.get("action_plans", [])
    results = []

    for plan in plans:
        if isinstance(plan, dict):
            action_type = plan.get("action_type", "")
            if action_type == "process_refund":
                results.append({
                    "action": "process_refund",
                    "status": "recommended",
                    "details": plan.get("description", ""),
                })
            elif action_type == "send_reply":
                results.append({
                    "action": "send_reply",
                    "status": "sent",
                    "details": plan.get("description", ""),
                })
            else:
                results.append({
                    "action": "escalate_to_human",
                    "status": "escalated",
                    "reason": plan.get("parameters", {}).get("reason", ""),
                })

    return {
        "execution_results": results,
        "verification_passed": any(r.get("status") in ("sent", "recommended") for r in results) if results else False,
    }


async def _billing_quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """v3: Enhanced quality scorer for billing responses."""
    conclusion = state.get("reasoning_conclusion", "")
    final_response = state.get("final_response", "")
    combined = f"{conclusion} {final_response}".lower()
    has_kb = len(state.get("kb_results", [])) > 0
    verified = state.get("_charge_verification", "needs_review") != "needs_review"

    # Core signals
    has_amount = any(kw in combined for kw in ["$", "charge", "amount", "credit", "invoice", "dollars"])
    has_explanation = any(kw in combined for kw in ["because", "due to", "reason", "caused by", "explanation", "this charge is"])
    has_resolution = any(kw in combined for kw in ["adjust", "refund", "credit", "correct", "update", "resolve", "reviewed"])
    has_timeline = any(kw in combined for kw in ["business days", "hours", "processed", "next invoice", "billing cycle"])

    # Scoring
    score = 55.0
    if has_kb:
        score += 8.0
    if verified:
        score += 12.0
    if has_amount:
        score += 12.0
    if has_explanation:
        score += 8.0
    if has_resolution:
        score += 8.0
    if has_timeline:
        score += 5.0
    if len(conclusion) > 200:
        score += 5.0

    # Penalize vague
    vague = ["inconclusive", "unable to determine", "unclear"]
    if any(s in combined for s in vague):
        score -= 10.0

    quality_issues = []
    if score < 80:
        if not has_amount:
            quality_issues.append("Response lacks specific charge/amount details")
        if not has_explanation:
            quality_issues.append("No explanation for why the charge is correct/incorrect")
        if not has_resolution:
            quality_issues.append("No clear resolution path")

    return {
        "quality_score": max(min(score, 100.0), 0.0),
        "quality_issues": quality_issues,
        "_quality_check_count": state.get("_quality_check_count", 0) + 1,  # Track loop iterations
    }


def _should_retry_billing(state: dict[str, Any]) -> str:
    """Conditional edge: after quality scoring, decide to retry or proceed."""
    quality = state.get("quality_score", 0.0)
    attempts = state.get("_reasoning_attempts", 0)
    loop_key = "_quality_check_count"
    check_count = state.get(loop_key, 0) + 1

    if quality >= 80:
        return "RESPONSE_FORMATTER"
    if attempts >= 2 or check_count >= 3:
        return "RESPONSE_FORMATTER"

    logger.info("billing_quality_loop: quality=%.1f attempts=%d check=%d, retrying", quality, attempts, check_count)
    return "REASONING_ENGINE"


async def _billing_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the billing response."""
    conclusion = state.get("reasoning_conclusion", "")
    charge_status = state.get("_charge_verification", "needs_review")
    execution = state.get("execution_results", [])

    sections = []

    if charge_status == "appears_correct":
        sections.append(f"I've reviewed your billing concern. {conclusion}")
        sections.append("\nIf you have any questions about specific charges, I'm happy to walk through each line item with you.")
    elif charge_status == "potentially_incorrect":
        sections.append(f"I've reviewed your account and there appears to be a discrepancy. {conclusion}")
        sections.append("\nI've initiated a review of the charge in question. You should see the adjustment reflected within 3-5 business days.")
    else:
        sections.append(f"I've started looking into your billing concern. {conclusion}")
        sections.append("\nTo ensure we get this right, I've escalated this to our billing specialist team who will review your account in detail. You should hear back within 24 hours.")

    return {
        "final_response": "\n".join(sections),
    }


def build_billing_graph() -> StateGraph:
    """Build the 11-node billing subgraph (v3) with self-correction and quality loop-back."""
    graph = StateGraph(dict)

    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_billing_intent_confirm))
    graph.add_node("BILLING_VERIFY", safe_node("BILLING_VERIFY", fallback={})(_billing_verify))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_billing_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_billing_reasoning))
    graph.add_node("REVERSE_THINKER", safe_node("REVERSE_THINKER", fallback={})(_billing_reverse_thinker))
    graph.add_node("SELF_CORRECTION", safe_node("SELF_CORRECTION", fallback={})(_billing_self_correction))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_billing_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_billing_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_billing_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_billing_response_formatter))

    graph.set_entry_point("INTENT_CONFIRM")

    graph.add_edge("INTENT_CONFIRM", "BILLING_VERIFY")
    graph.add_edge("BILLING_VERIFY", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "REVERSE_THINKER")
    graph.add_edge("REVERSE_THINKER", "SELF_CORRECTION")
    graph.add_edge("SELF_CORRECTION", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")

    # Conditional edge: quality loop-back
    graph.add_conditional_edges(
        "QUALITY_SCORER",
        _should_retry_billing,
        {
            "RESPONSE_FORMATTER": "RESPONSE_FORMATTER",
            "REASONING_ENGINE": "REASONING_ENGINE",
        },
    )

    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class BillingGraph:
    """Convenience wrapper for the billing subgraph (v3)."""

    def __init__(self) -> None:
        self._graph = build_billing_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a billing ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 10
