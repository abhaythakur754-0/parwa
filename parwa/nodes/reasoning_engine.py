"""Node 6: REASONING_ENGINE — Thinks through the problem using Chain of Thought.

Reasoning Agent node. The main brain that reasons through the problem
using available evidence from knowledge and integration data.

Phase 2: Now uses FrameworkBrain to select and run techniques (CoT, ReAct, UoT)
based on ticket complexity. Falls back to rule-based reasoning if FrameworkBrain
is not available.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

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
    system_instructions = (
        "Think step-by-step about this customer issue.\n\n"
        f"Intent: {intent}\n"
        f"Evidence:\n{evidence}\n\n"
        "Provide a step-by-step reasoning chain, ending with: Conclusion: <your conclusion>"
    )
    prompt = build_safe_prompt(system_instructions, message)
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


async def _reason_with_brain(state: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    """Reason using FrameworkBrain (Phase 2). Returns (chain, conclusion, frameworks).

    Uses FrameworkBrain to select and run CoT, ReAct, and UoT based
    on ticket complexity. Falls back to rule-based on any failure.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        result = await brain.think(
            prompt=state.get("raw_message", ""),
            techniques=["chain_of_thought", "react", "uncertainty_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        chain = result.chain if result.chain else []
        conclusion = result.output if result.output else ""
        frameworks = result.frameworks_used if result.frameworks_used else []

        # If FrameworkBrain produced nothing useful, fall back
        if not conclusion:
            logger.debug("reasoning_engine: FrameworkBrain produced no conclusion, falling back to rule-based")
            chain, conclusion = _reason_rule_based(
                state.get("raw_message", ""),
                state.get("intent", "general_inquiry"),
                state.get("faq_match"),
                state.get("kb_results", []),
                state.get("integration_data", {}),
            )
            frameworks = ["chain_of_thought"]

        return chain, conclusion, frameworks

    except Exception as exc:
        logger.warning(
            "reasoning_engine: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        chain, conclusion = _reason_rule_based(
            state.get("raw_message", ""),
            state.get("intent", "general_inquiry"),
            state.get("faq_match"),
            state.get("kb_results", []),
            state.get("integration_data", {}),
        )
        return chain, conclusion, ["chain_of_thought"]


@safe_node("REASONING_ENGINE", fallback={"reasoning_chain": [], "reasoning_conclusion": "", "active_frameworks": []})
async def reasoning_engine(state: dict[str, Any]) -> dict[str, Any]:
    """Reason through the problem using FrameworkBrain (Phase 2).

    Phase 2 behavior:
      - Uses FrameworkBrain to select techniques based on complexity
      - Simple: CoT only
      - Medium: CoT + ReAct
      - Complex/Critical: CoT + ReAct + UoT
      - Falls back to rule-based reasoning on any FrameworkBrain failure

    Reads: raw_message, intent, faq_match, kb_results, integration_data, complexity
    Writes: reasoning_chain, reasoning_conclusion, active_frameworks (append)
    """
    # Try FrameworkBrain first (Phase 2)
    chain, conclusion, frameworks = await _reason_with_brain(state)

    # Add framework tracking — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # Ensure at least chain_of_thought is tracked
    if not new_frameworks and "chain_of_thought" not in existing:
        new_frameworks.append("chain_of_thought")

    return {
        "reasoning_chain": chain,
        "reasoning_conclusion": conclusion,
        "active_frameworks": new_frameworks,
    }
