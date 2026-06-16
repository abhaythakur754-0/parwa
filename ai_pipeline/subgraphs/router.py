"""Subgraph Router — Routes tickets to the correct specialized subgraph.

v2 Improvements:
  - Expanded keyword lists (3x more keywords for tech)
  - Weighted keyword scoring (not just count)
  - "Can't/won't/doesn't work" pattern detection for tech
  - Cancellation → refund routing fix
  - API/integration questions correctly split between tech and general
  - Multi-signal confidence scoring

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


# ─── Keyword-Based Fast Routing (v2: weighted + expanded) ─────────────────────

_ROUTING_KEYWORDS: dict[str, list[str]] = {
    "refund": [
        # Direct refund signals (high confidence)
        "refund", "money back", "return", "cancel my order",
        "cancellation", "cancel subscription", "want a refund",
        "get my money", "chargeback", "dispute this charge",
        "cancel my account", "not satisfied", "not happy with",
        # v2: More refund signals
        "reimburse", "give me my money", "send my money back",
        "refund my", "money back guarantee", "return policy",
        "exchange", "send it back",
    ],
    "tech": [
        # Direct tech signals
        "not working", "error", "bug", "crash", "broken",
        "can't login", "integration", "api", "webhook",
        "slow", "loading", "won't connect", "debug",
        "troubleshoot", "fix", "issue with", "problem with",
        "setup", "install", "configure", "502", "500", "404",
        "timeout", "ssl", "certificate", "dns",
        # v2: "Can't/won't/doesn't" patterns (huge tech signal)
        "can't access", "cannot access", "won't load", "won't open",
        "won't start", "doesn't work", "doesn't load", "does not work",
        "can't connect", "cannot connect", "can't upload", "can't download",
        "keeps crashing", "keeps freezing", "keeps happening",
        "unable to", "failed to", "fails to",
        # v2: More technical terms
        "outage", "down", "server", "endpoint", "status code",
        "401", "403", "503", "408", "429", "504",
        "sdk", "cli", "library", "plugin", "extension",
        "authentication error", "permission denied", "access denied",
        "cors", "rate limit", "throttling", "quota exceeded",
        "webhook not", "event not", "callback failed",
        "mobile app", "iphone app", "android app",
        "sso", "saml", "oauth", "mfa", "2fa",
        "credentials invalid", "invalid credentials", "locked out",
        # v2: Performance-specific
        "slow loading", "takes forever", "spinning", "unresponsive",
        "hangs when", "freezes when", "lag when",
    ],
    "billing": [
        # Direct billing signals
        "charge", "invoice", "payment", "billed", "overcharged",
        "subscription fee", "plan change", "upgrade", "downgrade",
        "credit card", "failed payment", "receipt", "tax",
        "vat", "gst", "proration", "billing cycle",
        # v2: More billing signals
        "charged twice", "double charge", "unauthorized charge",
        "wrong amount", "different amount", "incorrect charge",
        "renewal", "auto-renew", "subscription renewed",
        "payment method", "card declined", "card expired",
        "prorated", "mid-cycle", "annual subscription",
        "receipt for", "tax purposes", "expense report",
    ],
}

# v2: Weighted keywords — some keywords are stronger signals
_KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {
    "refund": {
        "refund": 3.0, "money back": 2.5, "chargeback": 2.5, "return": 1.5,
        "cancel my order": 2.0, "cancel subscription": 1.8, "want a refund": 3.0,
        "get my money": 2.5, "not satisfied": 1.2, "reimburse": 2.5,
    },
    "tech": {
        "error": 2.0, "crash": 2.5, "bug": 2.0, "not working": 2.5,
        "won't load": 2.5, "can't access": 2.5, "keeps crashing": 3.0,
        "503": 2.5, "500": 2.5, "404": 2.0, "outage": 2.5,
        "api": 1.8, "webhook": 2.0, "integration": 1.5, "ssl": 2.0,
        "slow": 1.2, "timeout": 2.0, "credentials invalid": 2.5,
    },
    "billing": {
        "charged twice": 3.0, "double charge": 3.0, "overcharged": 2.5,
        "unauthorized charge": 2.5, "invoice": 2.0, "payment": 1.5,
        "billed": 2.0, "receipt": 1.5, "subscription fee": 2.0,
        "wrong amount": 2.5, "card declined": 2.0,
    },
}

# v2: Patterns that indicate tech vs general
_TECH_PATTERNS = [
    r"can'?t\s+(?:log(?:in|ged|ging)?|access|connect|upload|download|open|start|use|see|find)",
    r"won'?t\s+(?:load|open|start|connect|work|let me|accept)",
    r"doesn'?t\s+(?:work|load|show|connect|respond|recognize)",
    r"does not\s+(?:work|load|show|connect|respond)",
    r"keeps\s+(?:crashing|freezing|happening|saying|showing|giving)",
    r"(?:getting|received?)\s+(?:a|an)?\s*(?:error|500|503|404|401|403)",
    r"(?:app|application|site|website|dashboard|portal)\s+(?:crash|freez|hang|not|won|can)",
]


def _keyword_route(message: str) -> tuple[str | None, float]:
    """v2: Weighted keyword-based routing. Returns (subgraph_name, confidence).

    Confidence is normalized 0-1 based on total weight.
    """
    msg_lower = message.lower()
    scores: dict[str, float] = {}

    for subgraph, keywords in _ROUTING_KEYWORDS.items():
        weight_map = _KEYWORD_WEIGHTS.get(subgraph, {})
        score = 0.0
        for kw in keywords:
            if kw in msg_lower:
                score += weight_map.get(kw, 1.0)  # Default weight 1.0
        # Also check tech patterns
        if subgraph == "tech":
            for pattern in _TECH_PATTERNS:
                if re.search(pattern, msg_lower):
                    score += 2.0
        if score > 0:
            scores[subgraph] = score

    if not scores:
        return None, 0.0

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = min(scores[best] / 5.0, 1.0)  # Normalize: 5+ weight = 100% confidence

    # v2: Tie-breaking logic
    if len(scores) > 1:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1]

        # If scores are very close (within 30%), it's ambiguous → use brain routing
        if second_score / top_score > 0.7:
            return best, confidence * 0.6  # Reduce confidence for ambiguous cases

        # v2: Special rule: "cancel subscription" is refund, not billing
        if best == "billing" and any(kw in msg_lower for kw in ["cancel subscription", "cancel my subscription"]):
            if "refund" in scores and scores["refund"] > 0:
                return "refund", confidence

    return best, confidence


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
        result, _ = _keyword_route(message)
        return result or "general"


class SubgraphRouter:
    """Routes tickets to the correct subgraph.

    v2: 4-layer routing strategy:
      1. Intent-based: If intent is already in state, use the direct mapping
      2. Weighted keyword: Fast pattern matching with confidence scoring
      3. Pattern matching: Regex patterns for "can't X" / "won't X" tech signals
      4. Brain-based: Use FrameworkBrain with CoT for ambiguous cases

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

        # Layer 2: Weighted keyword routing (fast, good for clear cases)
        keyword_result, confidence = _keyword_route(message)
        if keyword_result and confidence >= 0.6:
            logger.info(
                "subgraph_router: keyword match → subgraph='%s' (confidence=%.2f)",
                keyword_result, confidence,
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
