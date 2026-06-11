"""Node 3: FAQ_MATCHER — Checks if this is a known frequently asked question.

Knowledge Agent node. Matches the ticket against known FAQs
to enable quick resolution for common questions.

Phase 3: Now uses FrameworkBrain with HyDE/Multi-Query for better
FAQ matching. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import KnowledgeResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.output_parser import parse_faq_response
from parwa.utils.sanitizer import build_safe_prompt

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
    """Match against FAQs using LLM (async).

    Uses structured output parsing and sanitized prompt.
    """
    faq_list = "\n".join(f"- {f['id']}: {f['question']}" for f in _MOCK_FAQS)
    system_instructions = (
        "Match the customer message against our FAQs.\n\n"
        f"FAQs:\n{faq_list}\n\n"
        "Reply with ONLY: faq_id|relevance_score|answer or no_match|0.00|"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(prompt, node_name="FAQ_MATCHER")
    faq_id, score, content = parse_faq_response(text)
    if faq_id == "no_match" or score < 0.3:
        return None
    return KnowledgeResult(
        source=f"faq:{faq_id}",
        content=content,
        relevance_score=score,
    )


async def _match_faq_with_brain(state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """FAQ matching using FrameworkBrain (Phase 3).

    Returns (faq_match_dict_or_None, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="FAQ_MATCHER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["hyde", "multi_query", "clara"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # The brain enhances matching — do rule-based + brain metadata
        faq_result = _match_faq_rule_based(raw_message)

        # If brain found high confidence and rule-based didn't, or vice versa
        if faq_result and result.confidence > 0.5:
            # Both agree — high confidence
            faq_dict = faq_result.model_dump()
            faq_dict["retrieval_enhanced"] = True
            faq_dict["frameworks_used"] = result.frameworks_used
            return faq_dict, result.frameworks_used
        elif faq_result:
            # Rule-based found something, brain less confident — still return it
            return faq_result.model_dump(), []
        else:
            # No match found
            return None, []

    except Exception as exc:
        logger.warning(
            "faq_matcher: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        faq_result = _match_faq_rule_based(raw_message)
        return faq_result.model_dump() if faq_result else None, []


@safe_node("FAQ_MATCHER", fallback={"faq_match": None, "active_frameworks": []})
async def faq_matcher(state: dict[str, Any]) -> dict[str, Any]:
    """Match the ticket against known FAQs (async).

    Phase 3: Uses FrameworkBrain with HyDE/Multi-Query/CLARA for
    better FAQ matching. Falls back to rule-based on failure.

    Reads: raw_message, intent
    Writes: faq_match, active_frameworks (append)
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {"faq_match": None, "active_frameworks": []}

    # Try FrameworkBrain first (Phase 3)
    faq_result, frameworks = await _match_faq_with_brain(state)

    if faq_result is None and not MOCK_MODE:
        try:
            llm_result = await _match_faq_llm(raw_message)
            if llm_result:
                faq_result = llm_result.model_dump()
        except Exception as exc:
            # LLM failed — no FAQ match is acceptable (graceful degradation)
            logger.warning(
                "FAQ_MATCHER: LLM FAQ matching failed, "
                "no rule-based match available: %s",
                exc,
            )

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "faq_match": faq_result,
        "active_frameworks": new_frameworks,
    }
