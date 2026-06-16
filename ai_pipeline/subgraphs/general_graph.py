"""General Subgraph — Pipeline for general inquiries, FAQ, complaints, etc.

8-node streamlined pipeline for straightforward tickets:

  INGEST → INTENT_CONFIRM → KB_RETRIEVER → REASONING_ENGINE
      → ACTION_PLANNER → ACTION_EXECUTOR
      → QUALITY_SCORER → RESPONSE_FORMATTER

Technique priorities:
  - CoT for straightforward reasoning
  - Least-to-Most for multi-part questions
  - Minimal techniques = fast, cheap, good enough for simple tickets
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.general")


async def _general_intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm general intent and classify the sub-type."""
    message = state.get("raw_message", "").lower()
    updates: dict[str, Any] = {}

    # Detect general sub-types
    sub_types = {
        "faq": ["how do i", "what is", "where can i", "can you explain"],
        "complaint": ["complaint", "unacceptable", "terrible service", "worst"],
        "account": ["change my", "update my", "modify", "switch"],
        "order_status": ["where is my order", "tracking", "delivery", "shipping"],
        "general": [],  # fallback
    }

    detected = "general"
    for stype, keywords in sub_types.items():
        if any(kw in message for kw in keywords):
            detected = stype
            break

    updates["_general_sub_type"] = detected

    # Detect if multi-part question
    question_marks = message.count("?")
    updates["_is_multipart"] = question_marks > 1

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["general_subgraph"]
    return updates


async def _general_kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """KB retrieval for general queries."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import GENERAL_KB_ENHANCEMENT_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques, get_subgraph_kb_boosts

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        techniques = get_subgraph_techniques("general", "KB_RETRIEVER")
        prompt = GENERAL_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["hyde"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        kb_results = []

        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()
            search_query = state.get("raw_message", "")
            original_results = crm.search_kb(search_query, top_k=3)
            kb_results.extend(original_results)

            # HyDE enhanced search
            tech_meta = result.metadata.get("technique_results", {})
            hyde_entry = tech_meta.get("hyde", {})
            hyde_meta = hyde_entry.get("metadata", {}) if isinstance(hyde_entry, dict) else {}
            hyde_doc = hyde_meta.get("hypothetical_document", "")
            if hyde_doc and len(hyde_doc) > 20:
                enhanced = crm.search_kb(hyde_doc, top_k=3)
                kb_results.extend(enhanced)

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
        logger.warning("general_kb_retriever: failed: %s", exc)
        return {"kb_results": []}


async def _general_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """General reasoning — keep it simple."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.technique_configs import get_subgraph_techniques

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        techniques = get_subgraph_techniques("general", "REASONING_ENGINE")

        # For multi-part questions, use Least-to-Most
        if state.get("_is_multipart"):
            if "least_to_most" not in techniques:
                techniques = techniques + ["least_to_most"]

        kb_context = "\n".join([
            r.get("content", "") if isinstance(r, dict) else str(r)
            for r in state.get("kb_results", [])[:3]
        ])

        prompt = f"""Help resolve this customer inquiry clearly and concisely.

Customer message: {state.get('raw_message', '')}
Sub-type: {state.get('_general_sub_type', 'general')}

Knowledge Base Context:
{kb_context[:1000]}

Provide a clear, helpful answer. If you can't find the answer, say so honestly."""

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
        logger.warning("general_reasoning: brain failed: %s", exc)
        return {"reasoning_conclusion": "Reasoning inconclusive"}


async def _general_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan general support actions."""
    sub_type = state.get("_general_sub_type", "general")
    conclusion = state.get("reasoning_conclusion", "")

    action_map = {
        "complaint": "escalate_to_human",
        "order_status": "share_policy",
    }
    action_type = action_map.get(sub_type, "send_reply")

    return {
        "action_plans": [{
            "action_type": action_type,
            "description": conclusion[:300] if conclusion else "Process general inquiry",
            "parameters": {"sub_type": sub_type},
            "evidence": conclusion[:200] if conclusion else "",
            "risk_level": "low",
        }],
    }


async def _general_action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute general actions."""
    plans = state.get("action_plans", [])
    results = []

    for plan in plans:
        if isinstance(plan, dict):
            results.append({
                "action": plan.get("action_type", "send_reply"),
                "status": "completed",
                "details": plan.get("description", ""),
            })

    return {
        "execution_results": results,
        "verification_passed": True,
    }


async def _general_quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score general response quality."""
    conclusion = state.get("reasoning_conclusion", "")
    has_kb = len(state.get("kb_results", [])) > 0

    score = 70.0
    if has_kb:
        score += 15.0
    if len(conclusion) > 50:
        score += 15.0

    return {
        "quality_score": min(score, 100.0),
        "quality_issues": [],
    }


async def _general_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the general response."""
    conclusion = state.get("reasoning_conclusion", "")
    sub_type = state.get("_general_sub_type", "general")

    if sub_type == "complaint":
        response = f"I'm sorry to hear about your experience. {conclusion}\n\nI'd like to make this right — would you like me to connect you with a senior team member who can address your concern directly?"
    elif sub_type == "faq":
        response = f"{conclusion}\n\nIs there anything else I can help you with?"
    else:
        response = f"{conclusion}\n\nIf you need any further assistance, don't hesitate to ask!"

    return {
        "final_response": response,
    }


def build_general_graph() -> StateGraph:
    """Build the 8-node general subgraph."""
    graph = StateGraph(dict)

    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_general_intent_confirm))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_general_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_general_reasoning))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_general_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_general_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_general_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_general_response_formatter))

    graph.set_entry_point("INTENT_CONFIRM")

    graph.add_edge("INTENT_CONFIRM", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")
    graph.add_edge("QUALITY_SCORER", "RESPONSE_FORMATTER")
    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class GeneralGraph:
    """Convenience wrapper for the general subgraph."""

    def __init__(self) -> None:
        self._graph = build_general_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a general ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 7
