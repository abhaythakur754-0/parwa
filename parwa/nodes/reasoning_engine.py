"""Node 6: REASONING_ENGINE — Thinks through the problem using Chain of Thought.

Reasoning Agent node. The main brain that reasons through the problem
using available evidence from knowledge and integration data.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, ainvoke_llm
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.reasoning_engine")


def _reason_rule_based(
    message: str,
    intent: str,
    faq_match: dict | None,
    kb_results: list[dict],
    integration_data: dict,
) -> tuple[list[str], str]:
    """Reason using rule-based chain of thought. Returns (chain, conclusion)."""
    chain = []
    conclusion = ""

    # Step 1: What does the customer want?
    chain.append(f"Customer intent: {intent}")

    # Step 2: What do we know?
    if faq_match and faq_match.get("relevance_score", 0) > 0.5:
        chain.append(f"FAQ match found: {faq_match.get('content', '')}")

    if kb_results:
        for kb in kb_results[:2]:
            chain.append(f"KB evidence: {kb.get('content', '')[:100]}")

    if integration_data:
        if "charges" in integration_data:
            charges = integration_data["charges"]
            chain.append(f"CRM shows {len(charges)} charge(s): {charges}")
        if "orders" in integration_data:
            orders = integration_data["orders"]
            chain.append(f"CRM shows {len(orders)} order(s)")

    # Step 3: What should we conclude?
    if intent == "refund_request":
        conclusion = "Customer is eligible for a refund. Evidence supports the claim."
    elif intent == "order_status":
        conclusion = "Order status can be provided from CRM data."
    elif intent == "cancellation":
        conclusion = "Cancellation request can be processed per policy."
    elif intent == "billing_issue":
        conclusion = "Billing discrepancy identified. Corrective action needed."
    else:
        conclusion = "Issue analyzed. Appropriate response can be formulated."

    chain.append(f"Conclusion: {conclusion}")
    return chain, conclusion


async def _reason_llm(
    message: str,
    intent: str,
    faq_match: dict | None,
    kb_results: list[dict],
    integration_data: dict,
    ticket_id: str = "",
    variant: str = "parwa",
) -> tuple[list[str], str]:
    """Reason using LLM chain of thought (async). Returns (chain, conclusion).

    Uses ainvoke_llm() for automatic retry + rate limiting.
    """
    evidence_parts = []
    if faq_match:
        evidence_parts.append(f"FAQ: {faq_match.get('content', '')}")
    for kb in kb_results[:2]:
        evidence_parts.append(f"KB: {kb.get('content', '')[:100]}")
    if integration_data:
        evidence_parts.append(f"CRM: {integration_data}")

    evidence = "\n".join(evidence_parts)
    prompt = (
        f"Think step-by-step about this customer issue.\n\n"
        f"Customer message: {message}\n"
        f"Intent: {intent}\n"
        f"Evidence:\n{evidence}\n\n"
        f"Provide a step-by-step reasoning chain, ending with: Conclusion: <your conclusion>"
    )
    text = await ainvoke_llm(
        prompt,
        node_name="REASONING_ENGINE",
        ticket_id=ticket_id,
        variant=variant,
    )
    chain = [line.strip() for line in text.strip().split("\n") if line.strip()]
    conclusion = ""
    for line in chain:
        if line.lower().startswith("conclusion:"):
            conclusion = line[len("conclusion:"):].strip()
            break
    if not conclusion and chain:
        conclusion = chain[-1]
    return chain, conclusion


@safe_node("REASONING_ENGINE", fallback={"reasoning_chain": [], "reasoning_conclusion": "", "active_frameworks": []})
async def reasoning_engine(state: dict[str, Any]) -> dict[str, Any]:
    """Reason through the problem using Chain of Thought (async).

    Reads: raw_message, intent, faq_match, kb_results, integration_data
    Writes: reasoning_chain, reasoning_conclusion, active_frameworks (append)
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    faq_match = state.get("faq_match")
    kb_results = state.get("kb_results", [])
    integration_data = state.get("integration_data", {})

    # Guard: ensure list types
    if not isinstance(kb_results, list):
        kb_results = []
    if not isinstance(integration_data, dict):
        integration_data = {}

    chain, conclusion = _reason_rule_based(
        raw_message, intent, faq_match, kb_results, integration_data
    )

    # Try LLM reasoning if not in mock mode (with graceful degradation)
    if not MOCK_MODE:
        try:
            llm_chain, llm_conclusion = await _reason_llm(
                raw_message, intent, faq_match, kb_results, integration_data,
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
            )
            # Use LLM result if it produced a conclusion
            if llm_conclusion:
                chain = llm_chain
                conclusion = llm_conclusion
        except Exception as exc:
            # LLM failed — keep the rule-based result (graceful degradation)
            logger.warning(
                "REASONING_ENGINE: LLM reasoning failed, "
                "falling back to rule-based chain (%d steps, conclusion='%s'): %s",
                len(chain), conclusion[:50], exc,
            )

    # Add framework tracking
    active_frameworks = list(state.get("active_frameworks", []))
    if "chain_of_thought" not in active_frameworks:
        active_frameworks.append("chain_of_thought")

    return {
        "reasoning_chain": chain,
        "reasoning_conclusion": conclusion,
        "active_frameworks": active_frameworks,
    }
