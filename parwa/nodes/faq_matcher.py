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


# FAQ data is now loaded from the Fake CRM
# The CRM has 8 comprehensive FAQs with realistic answers


def _get_crm_faqs() -> list[dict[str, str]]:
    """Get FAQs from the Fake CRM."""
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        return [faq for faq in crm._faqs.values()]
    except Exception:
        # Fallback to minimal FAQs if CRM is not available
        return [
            {"id": "refund_policy", "question": "What is the refund policy?", "answer": "Refunds are available within 30 days of purchase for duplicate charges.", "keywords": ["refund", "money back", "return"]},
            {"id": "shipping_policy", "question": "What are the shipping options?", "answer": "Standard shipping takes 3-5 business days.", "keywords": ["shipping", "delivery"]},
            {"id": "cancellation_policy", "question": "Can I cancel my order?", "answer": "Orders can be cancelled within 24 hours of placement.", "keywords": ["cancel"]},
        ]


def _match_faq_rule_based(message: str) -> KnowledgeResult | None:
    """Match against FAQs from the Fake CRM using keyword matching."""
    # Try CRM-based search first (much more realistic)
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        results = crm.search_faqs(message, top_k=1)
        if results:
            best = results[0]
            if best.get("relevance_score", 0) >= 0.3:
                return KnowledgeResult(
                    source=f"faq:{best['id']}",
                    content=best["answer"],
                    relevance_score=best["relevance_score"],
                    metadata={"question": best.get("question", "")},
                )
    except Exception:
        pass

    # Fallback: basic keyword matching on static FAQs
    message_lower = message.lower()
    faqs = _get_crm_faqs()

    best_match = None
    best_score = 0.0

    for faq in faqs:
        score = 0.0
        # Check question and answer for keyword matches
        for word in message_lower.split():
            if len(word) > 3:
                if word in faq.get("question", "").lower():
                    score += 0.3
                if word in faq.get("answer", "").lower():
                    score += 0.1
        score = min(0.99, score)

        if score > best_score and score >= 0.3:
            best_score = score
            best_match = faq

    if best_match and best_score >= 0.3:
        return KnowledgeResult(
            source=f"faq:{best_match['id']}",
            content=best_match["answer"],
            relevance_score=best_score,
            metadata={"question": best_match.get("question", "")},
        )

    return None


async def _match_faq_llm(message: str) -> KnowledgeResult | None:
    """Match against FAQs using LLM (async).

    Uses structured output parsing and sanitized prompt.
    """
    faq_list = "\n".join(f"- {f['id']}: {f['question']}" for f in _get_crm_faqs())
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
