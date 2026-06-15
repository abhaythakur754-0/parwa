"""Tech Support Subgraph — Specialized pipeline for technical support tickets.

10-node pipeline focused on diagnostic reasoning:

  INGEST → INTENT_CONFIRM → TECH_DIAGNOSIS → KB_RETRIEVER
      → REASONING_ENGINE → REVERSE_THINKER → ACTION_PLANNER
      → ACTION_EXECUTOR → QUALITY_SCORER → RESPONSE_FORMATTER

Technique priorities:
  - ReAct for step-by-step troubleshooting (primary)
  - ToT for complex multi-path diagnostics
  - CoT as baseline for simple issues
  - UoT for critical system-wide issues

This subgraph is the most technique-heavy because tech issues benefit
most from structured diagnostic reasoning.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.tech")


async def _tech_intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm tech support intent and extract technical details."""
    message = state.get("raw_message", "").lower()
    updates: dict[str, Any] = {}

    # Extract error codes
    error_codes = re.findall(r'\b\d{3}\b', message)  # HTTP status codes
    if error_codes:
        updates["_error_codes"] = error_codes

    # Detect product area
    product_areas = {
        "api": ["api", "endpoint", "webhook", "sdk", "integration"],
        "dashboard": ["dashboard", "ui", "interface", "page", "screen"],
        "auth": ["login", "password", "authentication", "sso", "2fa", "mfa"],
        "billing_tech": ["payment failed", "charge error", "invoice not loading"],
        "performance": ["slow", "timeout", "lag", "loading", "latency"],
    }
    detected_areas = []
    for area, keywords in product_areas.items():
        if any(kw in message for kw in keywords):
            detected_areas.append(area)
    if detected_areas:
        updates["_product_areas"] = detected_areas

    # Detect severity
    critical_signals = ["down", "outage", "all users", "production", "urgent", "emergency"]
    if any(s in message for s in critical_signals):
        updates["_tech_severity"] = "critical"
        updates["complexity"] = "critical"
    elif error_codes or detected_areas:
        updates["_tech_severity"] = "medium"
    else:
        updates["_tech_severity"] = "low"

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["tech_subgraph"]
    return updates


async def _tech_diagnosis(state: dict[str, Any]) -> dict[str, Any]:
    """Run initial diagnostic assessment."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import TECH_REASONING_PROMPT

        brain = FrameworkBrain(node="TECH_DIAGNOSIS", state=state)
        prompt = TECH_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            product=state.get("_product_areas", ["general"]),
            error_details=state.get("_error_codes", []),
        )

        # Tech diagnosis uses ReAct for structured troubleshooting
        result = await brain.think(
            prompt=prompt,
            techniques=["react", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:500] if result.output else "",
            "_diagnostic_steps": result.chain if result.chain else [],
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_diagnosis: brain failed: %s", exc)
        return {"reasoning_conclusion": "Initial diagnosis inconclusive"}


async def _tech_kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """KB retrieval with tech-specific search boosting."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import TECH_KB_ENHANCEMENT_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques, get_subgraph_kb_boosts

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        techniques = get_subgraph_techniques("tech", "KB_RETRIEVER")
        prompt = TECH_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["multi_query", "step_back"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        kb_results = []
        boosts = get_subgraph_kb_boosts("tech")

        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()

            # Search with original + error codes
            search_query = state.get("raw_message", "")
            error_codes = state.get("_error_codes", [])
            if error_codes:
                search_query += " " + " ".join(error_codes)

            original_results = crm.search_kb(search_query, top_k=3)
            kb_results.extend(original_results)

            # Search with MultiQuery enhanced queries
            tech_meta = result.metadata.get("technique_results", {})
            mq_entry = tech_meta.get("multi_query", {})
            mq_meta = mq_entry.get("metadata", {}) if isinstance(mq_entry, dict) else {}
            mq_queries = mq_meta.get("queries", [])
            for q in mq_queries[:3]:
                if len(q) > 10:
                    enhanced = crm.search_kb(q, top_k=2)
                    kb_results.extend(enhanced)

            # Search with tech-boosted terms
            for boost_term, weight in boosts.items():
                boost_results = crm.search_kb(f"{search_query} {boost_term}", top_k=2)
                for r in boost_results:
                    r.relevance_score = min(r.relevance_score + weight, 1.0)
                kb_results.extend(boost_results)

        except ImportError:
            pass

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
        logger.warning("tech_kb_retriever: failed: %s", exc)
        return {"kb_results": []}


async def _tech_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """Tech-specialized reasoning with diagnostic technique priority."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.technique_configs import get_subgraph_techniques

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        techniques = get_subgraph_techniques("tech", "REASONING_ENGINE")

        kb_context = "\n".join([
            r.get("content", "") if isinstance(r, dict) else str(r)
            for r in state.get("kb_results", [])[:3]
        ])

        prompt = f"""Analyze this technical support issue with step-by-step diagnostic reasoning.

Customer message: {state.get('raw_message', '')}
Product area: {state.get('_product_areas', ['unknown'])}
Error codes: {state.get('_error_codes', [])}
Severity: {state.get('_tech_severity', 'unknown')}

Knowledge Base Context:
{kb_context[:1000]}

Provide:
1. Most likely root cause
2. Step-by-step fix to try
3. If fix fails, what to try next
4. When to escalate to engineering"""

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["react", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:500] if result.output else "",
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_reasoning: brain failed: %s", exc)
        return {"reasoning_conclusion": "Technical reasoning inconclusive"}


async def _tech_reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """Reverse thinking for tech issues — what if our diagnosis is wrong?"""
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REVERSE_THINKER", state=state)
        conclusion = state.get("reasoning_conclusion", "")

        result = await brain.think_single(
            technique_name="reverse_thinking",
            prompt=f"Our diagnosis: {conclusion}\n\nChallenge this diagnosis. What if we're wrong? What else could cause these symptoms?",
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reverse_validation": {"alternative_diagnosis": result.output[:300] if result.output else ""},
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_reverse_thinker: failed: %s", exc)
        return {"reverse_validation": {}}


async def _tech_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan technical support actions."""
    severity = state.get("_tech_severity", "low")
    conclusion = state.get("reasoning_conclusion", "")
    reverse = state.get("reverse_validation", {})
    alt_diagnosis = reverse.get("alternative_diagnosis", "")

    actions = []

    # Primary fix action
    actions.append({
        "action_type": "send_reply",
        "description": "Send diagnostic steps to customer",
        "parameters": {
            "steps": conclusion[:500] if conclusion else "No diagnostic steps available",
            "product_area": state.get("_product_areas", ["general"]),
        },
        "evidence": conclusion[:200] if conclusion else "",
        "risk_level": "low",
    })

    # If severe, also escalate
    if severity == "critical":
        actions.append({
            "action_type": "escalate_to_human",
            "description": "Critical issue — escalate to engineering",
            "parameters": {"reason": "Production-impacting issue detected", "severity": "critical"},
            "evidence": alt_diagnosis[:200] if alt_diagnosis else conclusion[:200],
            "risk_level": "high",
        })

    return {"action_plans": actions}


async def _tech_action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute tech support actions."""
    plans = state.get("action_plans", [])
    results = []

    for plan in plans:
        if isinstance(plan, dict):
            action_type = plan.get("action_type", "")
            if action_type == "send_reply":
                results.append({
                    "action": "send_reply",
                    "status": "sent",
                    "details": plan.get("description", ""),
                })
            elif action_type == "escalate_to_human":
                results.append({
                    "action": "escalate_to_human",
                    "status": "escalated",
                    "reason": plan.get("parameters", {}).get("reason", ""),
                })

    return {
        "execution_results": results,
        "verification_passed": any(r.get("status") == "sent" for r in results) if results else False,
    }


async def _tech_quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score the quality of the tech support response."""
    conclusion = state.get("reasoning_conclusion", "")
    has_kb = len(state.get("kb_results", [])) > 0
    has_steps = "step" in conclusion.lower() or "try" in conclusion.lower() or "fix" in conclusion.lower()
    has_escalation_path = "escalat" in conclusion.lower() or "engineering" in conclusion.lower()

    score = 60.0  # Base
    if has_kb:
        score += 10.0
    if has_steps:
        score += 15.0
    if has_escalation_path:
        score += 5.0
    if len(conclusion) > 100:
        score += 10.0

    return {
        "quality_score": min(score, 100.0),
        "quality_issues": [] if score >= 80 else ["Response may lack specific diagnostic steps"],
    }


async def _tech_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the tech support response."""
    conclusion = state.get("reasoning_conclusion", "")
    severity = state.get("_tech_severity", "low")
    execution = state.get("execution_results", [])

    # Build structured diagnostic response
    sections = []

    # Acknowledge the issue
    sections.append("Thank you for reaching out about this issue. I've analyzed the problem and here's what I recommend:")

    # Diagnostic steps
    if conclusion:
        sections.append(f"\n**Diagnostic Steps:**\n{conclusion}")

    # Next steps if first fix fails
    reverse = state.get("reverse_validation", {})
    alt = reverse.get("alternative_diagnosis", "")
    if alt:
        sections.append(f"\n**If the above doesn't resolve it:**\n{alt[:300]}")

    # Escalation notice for critical issues
    if severity == "critical":
        sections.append("\nSince this appears to be a critical issue, I've also escalated this to our engineering team who will investigate further. You should hear back within 2 hours.")

    sections.append("\nPlease let me know if the steps above help resolve the issue, or if you need further assistance.")

    return {
        "final_response": "\n".join(sections),
    }


def build_tech_graph() -> StateGraph:
    """Build the 10-node tech support subgraph.

    Flow:
      INTENT_CONFIRM → TECH_DIAGNOSIS → KB_RETRIEVER → REASONING_ENGINE
          → REVERSE_THINKER → ACTION_PLANNER → ACTION_EXECUTOR
          → QUALITY_SCORER → RESPONSE_FORMATTER → END
    """
    graph = StateGraph(dict)

    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_tech_intent_confirm))
    graph.add_node("TECH_DIAGNOSIS", safe_node("TECH_DIAGNOSIS", fallback={})(_tech_diagnosis))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_tech_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_tech_reasoning))
    graph.add_node("REVERSE_THINKER", safe_node("REVERSE_THINKER", fallback={})(_tech_reverse_thinker))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_tech_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_tech_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_tech_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_tech_response_formatter))

    graph.set_entry_point("INTENT_CONFIRM")

    graph.add_edge("INTENT_CONFIRM", "TECH_DIAGNOSIS")
    graph.add_edge("TECH_DIAGNOSIS", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "REVERSE_THINKER")
    graph.add_edge("REVERSE_THINKER", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")
    graph.add_edge("QUALITY_SCORER", "RESPONSE_FORMATTER")
    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class TechGraph:
    """Convenience wrapper for the tech support subgraph."""

    def __init__(self) -> None:
        self._graph = build_tech_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a tech support ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 9
