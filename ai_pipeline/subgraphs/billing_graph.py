"""Billing Subgraph — Specialized pipeline for billing and payment tickets.

9-node pipeline focused on charge verification:

  INGEST → INTENT_CONFIRM → BILLING_VERIFY → KB_RETRIEVER
      → REASONING_ENGINE → ACTION_PLANNER → ACTION_EXECUTOR
      → QUALITY_SCORER → RESPONSE_FORMATTER

Technique priorities:
  - CoT for step-by-step charge verification
  - Self-Consistency for "does this charge match the plan?"
  - Reverse Thinking for "what if this charge is incorrect?"
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
    return updates


async def _billing_verify(state: dict[str, Any]) -> dict[str, Any]:
    """Verify the billing issue against known plans and charges."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import BILLING_REASONING_PROMPT

        brain = FrameworkBrain(node="BILLING_VERIFY", state=state)
        prompt = BILLING_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            plan="standard",  # Would come from CRM in production
            charges="recent charges to be verified",
        )

        # Use Self-Consistency to verify charge correctness
        result = await brain.think(
            prompt=prompt,
            techniques=["chain_of_thought", "self_consistency"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Determine if charge appears correct
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
            # Add issue type keywords to search
            issue_types = state.get("_billing_issue_type", [])
            if issue_types:
                search_query += " " + " ".join(issue_types)

            original_results = crm.search_kb(search_query, top_k=3)
            kb_results.extend(original_results)

            # Search with billing-boosted terms
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
        logger.warning("billing_reasoning: brain failed: %s", exc)
        return {"reasoning_conclusion": "Billing reasoning inconclusive"}


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
    """Score billing response quality."""
    conclusion = state.get("reasoning_conclusion", "")
    has_kb = len(state.get("kb_results", [])) > 0
    has_amount = "amount" in conclusion.lower() or "$" in conclusion or "charge" in conclusion.lower()
    verified = state.get("_charge_verification", "needs_review") != "needs_review"

    score = 60.0
    if has_kb:
        score += 10.0
    if has_amount:
        score += 15.0
    if verified:
        score += 15.0

    return {
        "quality_score": min(score, 100.0),
        "quality_issues": [] if score >= 80 else ["Billing response may lack specific charge details"],
    }


async def _billing_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the billing response."""
    conclusion = state.get("reasoning_conclusion", "")
    charge_status = state.get("_charge_verification", "needs_review")
    execution = state.get("execution_results", [])

    if charge_status == "appears_correct":
        response = f"I've reviewed your billing concern. {conclusion}\n\nIf you have any questions about specific charges, I'm happy to walk through each line item with you."
    elif charge_status == "potentially_incorrect":
        response = f"I've reviewed your account and there appears to be a discrepancy. {conclusion}\n\nI've initiated a review of the charge in question. You should see the adjustment reflected within 3-5 business days."
    else:
        response = f"I've started looking into your billing concern. {conclusion}\n\nTo ensure we get this right, I've escalated this to our billing specialist team who will review your account in detail. You should hear back within 24 hours."

    return {
        "final_response": response,
    }


def build_billing_graph() -> StateGraph:
    """Build the 9-node billing subgraph."""
    graph = StateGraph(dict)

    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_billing_intent_confirm))
    graph.add_node("BILLING_VERIFY", safe_node("BILLING_VERIFY", fallback={})(_billing_verify))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_billing_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_billing_reasoning))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_billing_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_billing_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_billing_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_billing_response_formatter))

    graph.set_entry_point("INTENT_CONFIRM")

    graph.add_edge("INTENT_CONFIRM", "BILLING_VERIFY")
    graph.add_edge("BILLING_VERIFY", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")
    graph.add_edge("QUALITY_SCORER", "RESPONSE_FORMATTER")
    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class BillingGraph:
    """Convenience wrapper for the billing subgraph."""

    def __init__(self) -> None:
        self._graph = build_billing_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a billing ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 8
