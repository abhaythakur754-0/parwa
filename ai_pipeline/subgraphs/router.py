"""Subgraph Router — Routes tickets to the correct specialized subgraph.

The router replaces the generic flow with domain-specific routing:
  refund_request / cancellation → Refund Subgraph
  technical_support → Tech Subgraph
  billing_issue → Billing Subgraph
  everything else → General Subgraph

This is the entry point for the subgraph architecture. It runs BEFORE
the main pipeline, classifies the intent, and dispatches to the
appropriate subgraph. Each subgraph is a self-contained mini-pipeline
with its own nodes, technique priorities, and system prompts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from parwa.state import IntentType

logger = logging.getLogger("parwa.subgraphs.router")


# ─── Intent → Subgraph Mapping ────────────────────────────────────────────────

INTENT_SUBGRAPH_MAP: dict[str, str] = {
    "refund_request": "refund",
    "cancellation": "refund",       # Cancellations often involve refunds
    "technical_support": "tech",
    "billing_issue": "billing",
    "order_status": "general",
    "faq_question": "general",
    "complaint": "general",
    "account_modification": "general",
    "escalation": "general",
    "general_inquiry": "general",
}


# ─── Keyword-Based Fast Routing ───────────────────────────────────────────────

_ROUTING_KEYWORDS: dict[str, list[str]] = {
    "refund": [
        "refund", "money back", "return", "cancel my order",
        "cancellation", "cancel subscription", "want a refund",
        "get my money", "chargeback", "dispute this charge",
        "cancel my account", "not satisfied", "not happy with",
    ],
    "tech": [
        "not working", "error", "bug", "crash", "broken",
        "can't login", "integration", "api", "webhook",
        "slow", "loading", "won't connect", "debug",
        "troubleshoot", "fix", "issue with", "problem with",
        "setup", "install", "configure", "502", "500", "404",
        "timeout", "ssl", "certificate", "dns",
    ],
    "billing": [
        "charge", "invoice", "payment", "billed", "overcharged",
        "subscription fee", "plan change", "upgrade", "downgrade",
        "credit card", "failed payment", "receipt", "tax",
        "vat", "gst", "proration", "billing cycle",
    ],
}


def _keyword_route(message: str) -> str | None:
    """Fast keyword-based routing. Returns subgraph name or None."""
    msg_lower = message.lower()
    scores: dict[str, int] = {}

    for subgraph, keywords in _ROUTING_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in msg_lower:
                score += 1
        if score > 0:
            scores[subgraph] = score

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return None


async def _brain_route(message: str, state: dict[str, Any]) -> str:
    """Use FrameworkBrain for intelligent routing when keywords are ambiguous."""
    try:
        from parwa.frameworks.brain import FrameworkBrain
        brain = FrameworkBrain(node="SUBGRAPH_ROUTER", state=state)

        from parwa.subgraphs.prompts import SUBGRAPH_ROUTER_PROMPT
        prompt = SUBGRAPH_ROUTER_PROMPT.format(message=message)

        result = await brain.think(
            prompt=prompt,
            techniques=["chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Parse the output — should be one word: refund/tech/billing/general
        output = result.output.strip().lower()
        for valid in ("refund", "tech", "billing", "general"):
            if valid in output:
                return valid

        logger.warning("subgraph_router: brain returned unclear result '%s', defaulting to general", output)
        return "general"

    except Exception as exc:
        logger.warning("subgraph_router: brain routing failed: %s, falling back to keyword", exc)
        return _keyword_route(message) or "general"


class SubgraphRouter:
    """Routes tickets to the correct subgraph.

    Routing strategy (3-layer fallback):
      1. Intent-based: If intent is already in state, use the direct mapping
      2. Keyword-based: Fast pattern matching on the message text
      3. Brain-based: Use FrameworkBrain with CoT for ambiguous cases

    The router is fast (keyword) for clear cases and intelligent (brain)
    for ambiguous ones. Most tickets route in <10ms via keywords.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    async def route(self) -> str:
        """Determine which subgraph should handle this ticket.

        Returns:
            Subgraph name: "refund", "tech", "billing", or "general"
        """
        message = self.state.get("raw_message", "")

        # Layer 1: Intent-based routing (fastest, most accurate)
        intent = self.state.get("intent", "")
        if intent and intent in INTENT_SUBGRAPH_MAP:
            subgraph = INTENT_SUBGRAPH_MAP[intent]
            logger.info(
                "subgraph_router: intent='%s' → subgraph='%s'",
                intent, subgraph,
            )
            return subgraph

        # Layer 2: Keyword-based routing (fast, good for clear cases)
        keyword_result = _keyword_route(message)
        if keyword_result:
            logger.info(
                "subgraph_router: keyword match → subgraph='%s'",
                keyword_result,
            )
            return keyword_result

        # Layer 3: Brain-based routing (slower, handles ambiguity)
        brain_result = await _brain_route(message, self.state)
        logger.info(
            "subgraph_router: brain routing → subgraph='%s'",
            brain_result,
        )
        return brain_result


async def route_to_subgraph(state: dict[str, Any]) -> str:
    """Convenience function: route a ticket state to a subgraph.

    Args:
        state: The ticket state dict.

    Returns:
        Subgraph name: "refund", "tech", "billing", or "general"
    """
    router = SubgraphRouter(state)
    return await router.route()
