"""Refund Subgraph — Enhanced pipeline with self-correction and quality loop-back.

10-node pipeline with policy verification and self-correction:

  INTENT_CONFIRM → REFUND_POLICY_CHECK → KB_RETRIEVER → REASONING_ENGINE
      → REVERSE_THINKER → SELF_CORRECTION → ACTION_PLANNER → ACTION_EXECUTOR
      → QUALITY_SCORER → RESPONSE_FORMATTER → END
                                          ↑_______________|
                                    (if quality < 80 and attempts < 2, loop back to REASONING_ENGINE)

v3 Improvements:
  - Added REVERSE_THINKER for "what if this refund is wrong?" validation
  - Added SELF_CORRECTION node that enriches reasoning with alternative perspective
  - Added quality loop-back: if quality < 80, re-reason with correction context
  - Up to 2 retry loops before accepting the response
  - Better quality scorer with more refund-specific signals
  - Improved response formatter with empathy + clarity + next steps
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.refund")


# ─── Refund-Specific Node Implementations ─────────────────────────────────────

async def _intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm the refund intent and extract refund-specific details."""
    message = state.get("raw_message", "").lower()
    updates: dict[str, Any] = {}

    # Confirm intent is refund-related
    refund_signals = ["refund", "money back", "return", "cancel", "not satisfied", "not happy"]
    refund_confidence = sum(1 for s in refund_signals if s in message) / len(refund_signals)
    updates["intent_confidence"] = min(refund_confidence * 3, 1.0)

    # Extract purchase timeframe
    time_patterns = [
        (r"(\d+)\s*day", "days"),
        (r"(\d+)\s*week", "weeks"),
        (r"(\d+)\s*month", "months"),
    ]
    for pattern, unit in time_patterns:
        match = __import__("re").search(pattern, message)
        if match:
            value = int(match.group(1))
            updates["_refund_timeframe"] = f"{value} {unit}"
            break

    # Detect subscription vs one-time
    sub_keywords = ["subscription", "monthly", "yearly", "plan", "recurring"]
    if any(kw in message for kw in sub_keywords):
        updates["_refund_type"] = "subscription"
    else:
        updates["_refund_type"] = "one_time"

    # Detect frustration level
    frustration_signals = ["angry", "unacceptable", "terrible", "worst", "furious", "disgusted"]
    if any(s in message for s in frustration_signals):
        updates["_frustration_level"] = "high"
    elif any(s in message for s in ["disappointed", "unhappy", "not working"]):
        updates["_frustration_level"] = "medium"
    else:
        updates["_frustration_level"] = "low"

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["refund_subgraph"]
    updates["_reasoning_attempts"] = 0  # Initialize counter for quality loop-back
    return updates


async def _refund_policy_check(state: dict[str, Any]) -> dict[str, Any]:
    """Check the refund against policy rules."""
    timeframe = state.get("_refund_timeframe", "unknown")
    refund_type = state.get("_refund_type", "one_time")
    frustration = state.get("_frustration_level", "low")

    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import REFUND_REASONING_PROMPT

        brain = FrameworkBrain(node="REFUND_POLICY_CHECK", state=state)
        prompt = REFUND_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            purchase_date=timeframe,
            customer_history="standard customer",
        )

        result = await brain.think(
            prompt=prompt,
            techniques=["chain_of_thought", "reverse_thinking"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        reasoning_text = result.output.lower()
        tier = "exception"
        refund_pct = 0.0

        if timeframe != "unknown":
            import re
            num_match = re.search(r"(\d+)", timeframe)
            if num_match:
                num = int(num_match.group(1))
                if "day" in timeframe and num <= 30:
                    tier = "full"
                    refund_pct = 1.0
                elif "day" in timeframe and num <= 60:
                    tier = "partial"
                    refund_pct = 0.75 if frustration == "high" else 0.5
                elif "week" in timeframe and num <= 4:
                    tier = "full"
                    refund_pct = 1.0
                elif "month" in timeframe and num <= 1:
                    tier = "full"
                    refund_pct = 1.0

        if refund_type == "subscription":
            tier = "prorated"
            refund_pct = 0.5

        return {
            "_refund_tier": tier,
            "_refund_percentage": refund_pct,
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:500] if result.output else "",
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("refund_policy_check: brain failed: %s, using rules", exc)
        return {
            "_refund_tier": "unknown",
            "_refund_percentage": 0.0,
            "reasoning_conclusion": "Policy check inconclusive — escalate to human",
        }


async def _refund_kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """KB retrieval with refund-specific search boosting."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import REFUND_KB_ENHANCEMENT_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques, get_subgraph_kb_boosts

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        techniques = get_subgraph_techniques("refund", "KB_RETRIEVER")
        prompt = REFUND_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["hyde", "multi_query"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        kb_results = []
        boosts = get_subgraph_kb_boosts("refund")

        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()
            original_results = crm.search_kb(state.get("raw_message", ""), top_k=3)
            kb_results.extend(original_results)

            tech_meta = result.metadata.get("technique_results", {})
            hyde_entry = tech_meta.get("hyde", {})
            hyde_meta = hyde_entry.get("metadata", {}) if isinstance(hyde_entry, dict) else {}
            hyde_doc = hyde_meta.get("hypothetical_document", "")
            if hyde_doc and len(hyde_doc) > 20:
                enhanced_results = crm.search_kb(hyde_doc, top_k=3)
                kb_results.extend(enhanced_results)

            for boost_term, weight in boosts.items():
                boost_results = crm.search_kb(f"{state.get('raw_message', '')} {boost_term}", top_k=2)
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
        logger.warning("refund_kb_retriever: failed: %s", exc)
        return {"kb_results": []}


async def _refund_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """Refund-specialized reasoning with policy-first technique priority."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import REFUND_REASONING_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        techniques = get_subgraph_techniques("refund", "REASONING_ENGINE")
        kb_context = "\n".join([
            r.get("content", "") if isinstance(r, dict) else str(r)
            for r in state.get("kb_results", [])[:3]
        ])

        prompt = REFUND_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            purchase_date=state.get("_refund_timeframe", "unknown"),
            customer_history="standard",
        )

        if kb_context:
            prompt += f"\n\nKnowledge Base Context:\n{kb_context[:1000]}"

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
        logger.warning("refund_reasoning: brain failed: %s", exc)
        return {
            "reasoning_conclusion": "Reasoning inconclusive",
            "_reasoning_attempts": state.get("_reasoning_attempts", 0) + 1,  # CRITICAL: always increment to prevent infinite loop
        }


async def _refund_reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """v3 NEW: Reverse thinking — what if this refund decision is wrong?

    Validates the refund reasoning by considering the opposite perspective:
    - What if the customer doesn't actually qualify?
    - What if there's fraud risk?
    - What if the refund amount should be different?
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REVERSE_THINKER", state=state)
        conclusion = state.get("reasoning_conclusion", "")
        tier = state.get("_refund_tier", "unknown")

        prompt = f"""Consider this refund decision from the OPPOSITE perspective.

Original decision: {tier} refund for the customer's request.
Original reasoning: {conclusion[:400]}

Think about:
1. What if this refund should be DENIED? What policy reasons could block it?
2. What if the refund amount is WRONG? (too high or too low)
3. What if this is a fraudulent refund request? What red flags exist?
4. What if the customer actually needs something different (not a refund)?

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
        logger.warning("refund_reverse_thinker: failed: %s", exc)
        return {"reverse_validation": {}}


async def _refund_self_correction(state: dict[str, Any]) -> dict[str, Any]:
    """v3 NEW: Self-correction — re-reason if the response seems insufficient.

    Checks if the current reasoning would score below quality threshold.
    If so, enriches with the reverse thinker's analysis and flags for retry.
    """
    conclusion = state.get("reasoning_conclusion", "")
    attempts = state.get("_reasoning_attempts", 0)

    # Quality pre-check — does the conclusion have substance?
    has_refund_amount = any(
        kw in conclusion.lower()
        for kw in ["full refund", "partial refund", "prorated", "100%", "50%", "75%", "$"]
    )
    has_policy_ref = any(
        kw in conclusion.lower()
        for kw in ["30-day", "policy", "eligible", "qualifies", "within", "days"]
    )
    has_next_steps = any(
        kw in conclusion.lower()
        for kw in ["processed", "business days", "confirm", "email", "review"]
    )

    # If response looks good, pass through
    if has_refund_amount and has_policy_ref and has_next_steps:
        return {"_self_correction_applied": False}

    # Don't loop more than twice
    if attempts >= 2:
        return {"_self_correction_applied": False}

    # Apply correction: incorporate reverse analysis
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


async def _refund_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan the refund action based on policy check results."""
    tier = state.get("_refund_tier", "unknown")
    pct = state.get("_refund_percentage", 0.0)
    conclusion = state.get("reasoning_conclusion", "")

    action_type = "process_refund" if tier in ("full", "partial", "prorated") else "escalate_to_human"

    if tier == "full":
        amount_desc = "Full refund (100%)"
    elif tier == "partial":
        amount_desc = f"Partial refund ({int(pct*100)}%)"
    elif tier == "prorated":
        amount_desc = "Prorated refund from cancellation date"
    else:
        amount_desc = "Refund amount to be determined by human agent"

    action_plan = {
        "action_type": action_type,
        "description": amount_desc,
        "parameters": {
            "refund_tier": tier,
            "refund_percentage": pct,
            "refund_type": state.get("_refund_type", "one_time"),
        },
        "evidence": conclusion[:300] if conclusion else "No reasoning available",
        "risk_level": "low" if tier == "full" else "medium" if tier == "partial" else "high",
    }

    return {
        "action_plans": [action_plan],
    }


async def _refund_action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the refund action."""
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
                    "parameters": plan.get("parameters", {}),
                })
            else:
                results.append({
                    "action": "escalate_to_human",
                    "status": "escalated",
                    "reason": f"Refund tier '{plan.get('parameters', {}).get('refund_tier', 'unknown')}' requires human review",
                })

    return {
        "execution_results": results,
        "verification_passed": any(r.get("status") == "recommended" for r in results) if results else False,
    }


async def _refund_quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """v3: Enhanced quality scorer for refund responses.

    Checks for:
    - Specific refund amount or tier mentioned
    - Policy reference (30-day, etc.)
    - Timeline for processing
    - Empathy (for frustrated customers)
    - Next steps
    """
    conclusion = state.get("reasoning_conclusion", "")
    final_response = state.get("final_response", "")
    combined = f"{conclusion} {final_response}".lower()
    has_kb = len(state.get("kb_results", [])) > 0
    frustration = state.get("_frustration_level", "low")

    # Core quality signals
    has_amount = any(kw in combined for kw in ["full refund", "partial refund", "prorated", "100%", "50%", "75%", "$"])
    has_policy = any(kw in combined for kw in ["30-day", "policy", "eligible", "qualifies", "within", "days"])
    has_timeline = any(kw in combined for kw in ["business days", "hours", "processed", "confirmation"])
    has_empathy = any(kw in combined for kw in ["sorry", "apologize", "understand", "frustration", "inconvenience"])
    has_next = any(kw in combined for kw in ["email", "confirm", "review", "contact", "reach out", "specialist"])

    # Scoring
    score = 55.0
    if has_kb:
        score += 8.0
    if has_amount:
        score += 15.0
    if has_policy:
        score += 10.0
    if has_timeline:
        score += 8.0
    if frustration != "low" and has_empathy:
        score += 10.0
    elif has_empathy:
        score += 5.0
    if has_next:
        score += 7.0
    if len(conclusion) > 200:
        score += 5.0
    elif len(conclusion) > 100:
        score += 2.0

    # Penalize vague responses
    vague = ["inconclusive", "unable to determine", "unclear", "not sure"]
    if any(s in combined for s in vague):
        score -= 10.0

    quality_issues = []
    if score < 80:
        if not has_amount:
            quality_issues.append("Response lacks specific refund amount or tier")
        if not has_policy:
            quality_issues.append("No policy reference provided")
        if not has_timeline:
            quality_issues.append("No processing timeline given")

    return {
        "quality_score": max(min(score, 100.0), 0.0),
        "quality_issues": quality_issues,
        "_quality_check_count": state.get("_quality_check_count", 0) + 1,  # Track loop iterations
    }


def _should_retry_refund(state: dict[str, Any]) -> str:
    """Conditional edge: after quality scoring, decide to retry or proceed to formatting."""
    quality = state.get("quality_score", 0.0)
    attempts = state.get("_reasoning_attempts", 0)

    # ALWAYS increment attempts to prevent infinite loops
    # If attempts was never set or is stuck at 0, count how many times we've been here
    loop_key = "_quality_check_count"
    check_count = state.get(loop_key, 0) + 1

    # If quality is good enough, proceed to response formatting
    if quality >= 80:
        return "RESPONSE_FORMATTER"

    # If we've already retried OR checked quality too many times, accept what we have
    if attempts >= 2 or check_count >= 3:
        return "RESPONSE_FORMATTER"

    # Otherwise, loop back to reasoning with correction context
    logger.info("refund_quality_loop: quality=%.1f attempts=%d check=%d, retrying", quality, attempts, check_count)
    return "REASONING_ENGINE"


async def _refund_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the refund response with empathy and clarity."""
    tier = state.get("_refund_tier", "unknown")
    pct = state.get("_refund_percentage", 0.0)
    execution = state.get("execution_results", [])
    frustration = state.get("_frustration_level", "low")
    conclusion = state.get("reasoning_conclusion", "")

    # Build empathetic response
    empathy_prefix = ""
    if frustration == "high":
        empathy_prefix = "I sincerely apologize for the inconvenience you've experienced. "
    elif frustration == "medium":
        empathy_prefix = "I understand your frustration. "

    sections = []

    if tier == "full":
        sections.append(
            f"{empathy_prefix}I've reviewed your refund request, and I'm happy to confirm "
            f"that you qualify for a full refund under our 30-day policy."
        )
        sections.append(f"\n**Refund Details:**\n{conclusion}")
        sections.append(
            "\nThe refund will be processed to your original payment method within 5-7 business days. "
            "You'll receive a confirmation email shortly."
        )
    elif tier == "partial":
        sections.append(
            f"{empathy_prefix}Based on our review, your request falls within our partial "
            f"refund policy. We can process a {int(pct*100)}% refund to your original payment method."
        )
        sections.append(f"\n**Refund Details:**\n{conclusion}")
        sections.append(
            "\nThe refund will be processed within 5-7 business days. "
            "If you'd like to discuss this further, I'm happy to connect you with a specialist."
        )
    elif tier == "prorated":
        sections.append(
            f"{empathy_prefix}Since this is a subscription cancellation, we'll process "
            f"a prorated refund for the unused portion of your billing period."
        )
        sections.append(f"\n**Refund Details:**\n{conclusion}")
        sections.append("\nThe refund will be processed within 5-7 business days.")
    else:
        sections.append(
            f"{empathy_prefix}I've reviewed your request, and I'd like to connect you "
            f"with a specialist who can provide the best resolution for your situation."
        )
        if conclusion:
            sections.append(f"\n**Initial Assessment:**\n{conclusion}")
        sections.append("\nA team member will reach out within 24 hours.")

    return {
        "final_response": "\n".join(sections),
    }


# ─── Build the Refund Subgraph ────────────────────────────────────────────────

def build_refund_graph() -> StateGraph:
    """Build the 10-node refund subgraph (v3) with self-correction and quality loop-back.

    Flow:
      INTENT_CONFIRM → REFUND_POLICY_CHECK → KB_RETRIEVER → REASONING_ENGINE
          → REVERSE_THINKER → SELF_CORRECTION → ACTION_PLANNER → ACTION_EXECUTOR
          → QUALITY_SCORER → RESPONSE_FORMATTER → END
                                        ↑__________________|
                                  (if quality < 80 and attempts < 2)
    """
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_intent_confirm))
    graph.add_node("REFUND_POLICY_CHECK", safe_node("REFUND_POLICY_CHECK", fallback={})(_refund_policy_check))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_refund_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_refund_reasoning))
    graph.add_node("REVERSE_THINKER", safe_node("REVERSE_THINKER", fallback={})(_refund_reverse_thinker))
    graph.add_node("SELF_CORRECTION", safe_node("SELF_CORRECTION", fallback={})(_refund_self_correction))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_refund_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_refund_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_refund_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_refund_response_formatter))

    # Set entry point
    graph.set_entry_point("INTENT_CONFIRM")

    # Add edges
    graph.add_edge("INTENT_CONFIRM", "REFUND_POLICY_CHECK")
    graph.add_edge("REFUND_POLICY_CHECK", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "REVERSE_THINKER")
    graph.add_edge("REVERSE_THINKER", "SELF_CORRECTION")
    graph.add_edge("SELF_CORRECTION", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")

    # Conditional edge: quality loop-back
    graph.add_conditional_edges(
        "QUALITY_SCORER",
        _should_retry_refund,
        {
            "RESPONSE_FORMATTER": "RESPONSE_FORMATTER",
            "REASONING_ENGINE": "REASONING_ENGINE",
        },
    )

    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class RefundGraph:
    """Convenience wrapper for the refund subgraph (v3)."""

    def __init__(self) -> None:
        self._graph = build_refund_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a refund ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 10
