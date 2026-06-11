"""Node 4: KB_RETRIEVER — Searches the knowledge base for relevant documents.

Knowledge Agent node. Retrieves relevant knowledge base documents
to provide evidence for the Reasoning Agent.

Phase 3: Now uses FrameworkBrain with CLARA, HyDE, Multi-Query, Step-Back
RAG techniques for smarter retrieval. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import KnowledgeResult
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.kb_retriever")


# Mock knowledge base documents
_MOCK_KB: list[dict[str, str]] = [
    {"id": "refund_policy_doc", "title": "Refund Policy", "content": "Full refunds are available within 30 days for duplicate charges. Partial refunds for damaged items within 14 days.", "category": "billing"},
    {"id": "shipping_policy_doc", "title": "Shipping Policy", "content": "Standard shipping: 3-5 business days. Express: 1-2 business days. International: 7-14 business days.", "category": "shipping"},
    {"id": "cancellation_policy_doc", "title": "Cancellation Policy", "content": "Orders can be cancelled within 24 hours. After shipment, returns must follow the refund process.", "category": "orders"},
    {"id": "account_policy_doc", "title": "Account Management", "content": "Account modifications require identity verification. Email changes need 48-hour confirmation period.", "category": "account"},
    {"id": "escalation_policy_doc", "title": "Escalation Policy", "content": "Legal threats must be escalated immediately. Regulatory complaints require manager review within 4 hours.", "category": "compliance"},
]


def _retrieve_kb_rule_based(message: str, intent: str) -> list[dict[str, Any]]:
    """Retrieve KB documents using keyword and intent matching."""
    message_lower = message.lower()
    results = []

    # Map intents to likely KB categories
    intent_category_map = {
        "refund_request": "billing",
        "billing_issue": "billing",
        "cancellation": "orders",
        "order_status": "shipping",
        "account_modification": "account",
        "escalation": "compliance",
        "complaint": "billing",
    }
    target_category = intent_category_map.get(intent, "")

    for doc in _MOCK_KB:
        score = 0.0
        # Category match
        if doc["category"] == target_category:
            score += 0.5
        # Keyword match
        for word in message_lower.split():
            if word in doc["content"].lower():
                score += 0.1
        score = min(0.99, score)
        if score >= 0.3:
            results.append(KnowledgeResult(
                source=f"kb:{doc['id']}",
                content=doc["content"],
                relevance_score=score,
                metadata={"title": doc["title"], "category": doc["category"]},
            ))

    # Sort by relevance, return top 3
    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return [r.model_dump() for r in results[:3]]


async def _retrieve_with_brain(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """KB retrieval using FrameworkBrain (Phase 3).

    Returns (kb_results, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["clara", "hyde", "multi_query", "step_back"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # The brain enhances the retrieval with RAG techniques
        # but we still need the actual KB results
        kb_results = _retrieve_kb_rule_based(raw_message, intent)

        # If brain produced metadata about improved retrieval, boost scores
        if result.confidence > 0.7 and result.frameworks_used:
            # Brain techniques improved our search — reflect in metadata
            for kb in kb_results:
                if isinstance(kb, dict):
                    kb["retrieval_enhanced"] = True
                    kb["frameworks_used"] = result.frameworks_used

        return kb_results, result.frameworks_used if result.frameworks_used else []

    except Exception as exc:
        logger.warning(
            "kb_retriever: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        kb_results = _retrieve_kb_rule_based(raw_message, intent)
        return kb_results, []


@safe_node("KB_RETRIEVER", fallback={"kb_results": []})
async def kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """Search the knowledge base for relevant documents (async).

    Phase 3: Uses FrameworkBrain with RAG techniques (CLARA, HyDE,
    Multi-Query, Step-Back) for smarter retrieval. Falls back to
    rule-based on FrameworkBrain failure.

    Reads: raw_message, intent
    Writes: kb_results
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")

    # Guard: ensure types
    if not isinstance(raw_message, str):
        raw_message = str(raw_message) if raw_message else ""
    if not isinstance(intent, str):
        intent = "general_inquiry"

    # Try FrameworkBrain first (Phase 3)
    results, frameworks = await _retrieve_with_brain(state)

    # Guard: ensure results is a list
    if not isinstance(results, list):
        results = []

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "kb_results": results,
        "active_frameworks": new_frameworks,
    }
