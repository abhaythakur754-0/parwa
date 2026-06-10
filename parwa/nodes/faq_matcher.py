"""Node 3: FAQ_MATCHER — Checks if this is a known frequently asked question.

Knowledge Agent node. Matches the ticket against known FAQs
to enable quick resolution for common questions.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import KnowledgeResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.faq_matcher")


# Pre-built FAQ database for mock mode
_MOCK_FAQS: list[dict[str, str]] = [
    {"id": "refund_policy", "question": "What is the refund policy?", "answer": "Refunds are available within 30 days of purchase for duplicate charges.", "keywords": ["refund", "money back", "return"]},
    {"id": "shipping_time", "question": "How long does shipping take?", "answer": "Standard shipping takes 3-5 business days.", "keywords": ["shipping", "delivery", "how long"]},
    {"id": "cancel_order", "question": "How do I cancel my order?", "answer": "Orders can be cancelled within 24 hours of placement.", "keywords": ["cancel", "cancel order"]},
    {"id": "account_update", "question": "How do I update my account?", "answer": "Account settings can be updated from the Profile page.", "keywords": ["account", "update", "profile"]},
    {"id": "payment_methods", "question": "What payment methods are accepted?", "answer": "We accept Visa, Mastercard, PayPal, and Apple Pay.", "keywords": ["payment", "pay", "credit card"]},
]


def _match_faq_rule_based(message: str) -> KnowledgeResult | None:
    """Match against FAQs using keyword matching."""
    message_lower = message.lower()

    best_match = None
    best_score = 0.0

    for faq in _MOCK_FAQS:
        score = 0.0
        for kw in faq["keywords"]:
            if kw in message_lower:
                score += 0.3
        score = min(0.99, score)

        if score > best_score and score >= 0.3:
            best_score = score
            best_match = faq

    if best_match and best_score >= 0.3:
        return KnowledgeResult(
            source=f"faq:{best_match['id']}",
            content=best_match["answer"],
            relevance_score=best_score,
            metadata={"question": best_match["question"]},
        )

    return None


async def _match_faq_llm(message: str) -> KnowledgeResult | None:
    """Match against FAQs using LLM (async)."""
    faq_list = "\n".join(f"- {f['id']}: {f['question']}" for f in _MOCK_FAQS)
    prompt = (
        f"Match this customer message against our FAQs.\n\n"
        f"FAQs:\n{faq_list}\n\n"
        f"Customer message: {message}\n\n"
        f"Reply with ONLY: faq_id|relevance_score|answer or no_match|0.00|"
    )
    text = await ainvoke_llm(prompt)
    parts = text.strip().split("|")
    if parts[0] == "no_match":
        return None
    try:
        score = float(parts[1]) if len(parts) > 1 else 0.0
    except (ValueError, IndexError):
        score = 0.0
    if score < 0.3:
        return None
    return KnowledgeResult(
        source=f"faq:{parts[0]}",
        content=parts[2] if len(parts) > 2 else "",
        relevance_score=score,
    )


@safe_node("FAQ_MATCHER", fallback={"faq_match": None})
async def faq_matcher(state: dict[str, Any]) -> dict[str, Any]:
    """Match the ticket against known FAQs (async).

    Reads: raw_message, intent
    Writes: faq_match
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {"faq_match": None}

    result = _match_faq_rule_based(raw_message)

    if result is None and not MOCK_MODE:
        try:
            result = await _match_faq_llm(raw_message)
        except Exception as exc:
            # LLM failed — no FAQ match is acceptable (graceful degradation)
            logger.warning(
                "FAQ_MATCHER: LLM FAQ matching failed, "
                "no rule-based match available: %s",
                exc,
            )

    return {"faq_match": result.model_dump() if result else None}
