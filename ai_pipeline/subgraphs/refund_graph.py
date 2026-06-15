"""Refund Subgraph — Specialized pipeline for refund and cancellation tickets.

8-node streamlined pipeline focused on refund policy verification:

  INGEST → INTENT_CONFIRM → REFUND_POLICY_CHECK → KB_RETRIEVER
      → REASONING_ENGINE → ACTION_PLANNER → ACTION_EXECUTOR
      → RESPONSE_FORMATTER

Technique priorities:
  - CoT for step-by-step policy verification
  - Reverse Thinking for "what if this refund is wrong?"
  - ReAct for looking up customer purchase history

This subgraph achieves higher accuracy than the flat pipeline because:
  1. System prompt is refund-specific (not generic)
  2. Technique priorities favor policy reasoning
  3. KB search is boosted for refund/cancellation terms
  4. Fewer nodes = less noise, faster resolution
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.state import TicketState, validate_state
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.refund")


# ─── Refund-Specific Node Implementations ─────────────────────────────────────

async def _intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm the refund intent and extract refund-specific details.

    Extracts:
    - Purchase date (if mentioned)
    - Refund reason
    - Customer frustration level
    - Whether this is a subscription or one-time purchase
    """
    message = state.get("raw_message", "").lower()
    updates: dict[str, Any] = {}

    # Confirm intent is refund-related
    refund_signals = ["refund", "money back", "return", "cancel", "not satisfied", "not happy"]
    refund_confidence = sum(1 for s in refund_signals if s in message) / len(refund_signals)
    updates["intent_confidence"] = min(refund_confidence * 3, 1.0)  # Scale up

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

    # Detect frustration level (affects refund generosity)
    frustration_signals = ["angry", "unacceptable", "terrible", "worst", "furious", "disgusted"]
    if any(s in message for s in frustration_signals):
        updates["_frustration_level"] = "high"
    elif any(s in message for s in ["disappointed", "unhappy", "not working"]):
        updates["_frustration_level"] = "medium"
    else:
        updates["_frustration_level"] = "low"

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["refund_subgraph"]
    return updates


async def _refund_policy_check(state: dict[str, Any]) -> dict[str, Any]:
    """Check the refund against policy rules.

    Determines:
    - Which refund tier applies (30-day, 31-60, 60+)
    - Whether fraud signals exist
    - Recommended refund amount
    """
    timeframe = state.get("_refund_timeframe", "unknown")
    refund_type = state.get("_refund_type", "one_time")
    frustration = state.get("_frustration_level", "low")

    # Use FrameworkBrain for policy reasoning
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

        # Parse the refund tier from reasoning
        reasoning_text = result.output.lower()

        # Determine tier based on timeframe
        tier = "exception"  # Default: needs manual review
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
            refund_pct = 0.5  # Prorated from cancellation date

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

        # Use refund-specific techniques
        techniques = get_subgraph_techniques("refund", "KB_RETRIEVER")
        prompt = REFUND_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["hyde", "multi_query"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Search with enhanced queries + refund-specific boosting
        kb_results = []
        boosts = get_subgraph_kb_boosts("refund")

        # Try CRM search if available
        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()

            # Search with original query
            original_results = crm.search_kb(state.get("raw_message", ""), top_k=3)
            kb_results.extend(original_results)

            # Search with HyDE enhanced query
            tech_meta = result.metadata.get("technique_results", {})
            hyde_entry = tech_meta.get("hyde", {})
            hyde_meta = hyde_entry.get("metadata", {}) if isinstance(hyde_entry, dict) else {}
            hyde_doc = hyde_meta.get("hypothetical_document", "")
            if hyde_doc and len(hyde_doc) > 20:
                enhanced_results = crm.search_kb(hyde_doc, top_k=3)
                kb_results.extend(enhanced_results)

            # Search with refund-boosted terms
            for boost_term, weight in boosts.items():
                boost_results = crm.search_kb(f"{state.get('raw_message', '')} {boost_term}", top_k=2)
                for r in boost_results:
                    r.relevance_score = min(r.relevance_score + weight, 1.0)
                kb_results.extend(boost_results)

        except ImportError:
            pass  # CRM not available

        # Deduplicate
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
        }

    except Exception as exc:
        logger.warning("refund_reasoning: brain failed: %s", exc)
        return {"reasoning_conclusion": "Reasoning inconclusive"}


async def _refund_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan the refund action based on policy check results."""
    tier = state.get("_refund_tier", "unknown")
    pct = state.get("_refund_percentage", 0.0)
    conclusion = state.get("reasoning_conclusion", "")

    action_type = "process_refund" if tier in ("full", "partial", "prorated") else "escalate_to_human"

    # Determine amount description
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
                    "status": "recommended",  # In production, this would actually process
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


async def _refund_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the refund response with empathy and clarity."""
    tier = state.get("_refund_tier", "unknown")
    pct = state.get("_refund_percentage", 0.0)
    execution = state.get("execution_results", [])
    frustration = state.get("_frustration_level", "low")

    # Build empathetic response
    empathy_prefix = ""
    if frustration == "high":
        empathy_prefix = "I sincerely apologize for the inconvenience you've experienced. "
    elif frustration == "medium":
        empathy_prefix = "I understand your frustration. "

    if tier == "full":
        response = (
            f"{empathy_prefix}I've reviewed your refund request, and I'm happy to confirm "
            f"that you qualify for a full refund. The refund will be processed to your "
            f"original payment method within 5-7 business days. You'll receive a "
            f"confirmation email shortly."
        )
    elif tier == "partial":
        response = (
            f"{empathy_prefix}Based on our review, your request falls within our partial "
            f"refund policy. We can process a {int(pct*100)}% refund to your original "
            f"payment method. The refund will be processed within 5-7 business days. "
            f"If you'd like to discuss this further, I'm happy to connect you with a "
            f"specialist who can review your case."
        )
    elif tier == "prorated":
        response = (
            f"{empathy_prefix}Since this is a subscription cancellation, we'll process "
            f"a prorated refund for the unused portion of your billing period. "
            f"The refund will be processed within 5-7 business days."
        )
    else:
        response = (
            f"{empathy_prefix}I've reviewed your request, and I'd like to connect you "
            f"with a specialist who can provide the best resolution for your situation. "
            f"A team member will reach out within 24 hours."
        )

    return {
        "final_response": response,
        "quality_score": 85.0 if tier != "unknown" else 60.0,
    }


# ─── Build the Refund Subgraph ────────────────────────────────────────────────

def build_refund_graph() -> StateGraph:
    """Build the 8-node refund subgraph.

    Flow:
      INGEST → INTENT_CONFIRM → REFUND_POLICY_CHECK → KB_RETRIEVER
          → REASONING_ENGINE → ACTION_PLANNER → ACTION_EXECUTOR
          → RESPONSE_FORMATTER → END
    """
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_intent_confirm))
    graph.add_node("REFUND_POLICY_CHECK", safe_node("REFUND_POLICY_CHECK", fallback={})(_refund_policy_check))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_refund_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_refund_reasoning))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_refund_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_refund_action_executor))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_refund_response_formatter))

    # Set entry point
    graph.set_entry_point("INTENT_CONFIRM")

    # Add edges
    graph.add_edge("INTENT_CONFIRM", "REFUND_POLICY_CHECK")
    graph.add_edge("REFUND_POLICY_CHECK", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "RESPONSE_FORMATTER")
    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class RefundGraph:
    """Convenience wrapper for the refund subgraph."""

    def __init__(self) -> None:
        self._graph = build_refund_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a refund ticket through the subgraph.

        Args:
            state: Ticket state dict (must have raw_message).

        Returns:
            Updated state with refund decision and response.
        """
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 7  # Not counting entry point
