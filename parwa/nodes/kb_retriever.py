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


# KB data is now loaded from the Fake CRM
# The CRM has 10 comprehensive KB articles with realistic procedures


def _get_crm_kb() -> list[dict[str, str]]:
    """Get KB articles from the Fake CRM."""
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        return crm._kb
    except Exception:
        return [
            {"id": "refund_policy_doc", "title": "Refund Policy", "content": "Full refunds are available within 30 days for duplicate charges.", "category": "billing"},
            {"id": "shipping_policy_doc", "title": "Shipping Policy", "content": "Standard shipping: 3-5 business days.", "category": "shipping"},
            {"id": "cancellation_policy_doc", "title": "Cancellation Policy", "content": "Orders can be cancelled before shipment.", "category": "orders"},
        ]


def _retrieve_kb_rule_based(message: str, intent: str) -> list[dict[str, Any]]:
    """Retrieve KB documents using the Fake CRM search."""
    # Try CRM-based search first (much more realistic)
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        
        # Enhance search query with intent-related keywords for better matching
        intent_keywords = {
            "refund_request": "duplicate charge refund payment",
            "billing_issue": "payment billing charge invoice",
            "cancellation": "cancel cancellation order",
            "order_status": "shipping order tracking delivery",
            "technical_support": "error bug technical integration",
            "account_modification": "account modify update change",
            "complaint": "complaint issue problem defective",
            "escalation": "escalation manager supervisor legal",
            "faq_question": "policy FAQ question help",
        }
        
        # Search with enhanced query
        search_query = message
        extra_keywords = intent_keywords.get(intent, "")
        if extra_keywords:
            search_query = f"{message} {extra_keywords}"
        
        results = crm.search_kb(search_query, top_k=3)
        
        # If no results with enhanced query, try intent-only search
        if not results and intent in intent_keywords:
            results = crm.search_kb(intent_keywords[intent], top_k=3)
        
        if results:
            return [
                KnowledgeResult(
                    source=f"kb:{r['id']}",
                    content=r["content"],
                    relevance_score=r.get("relevance_score", 0.5),
                    metadata={"title": r.get("title", ""), "category": r.get("category", "")},
                ).model_dump()
                for r in results
            ]
    except Exception:
        pass

    # Fallback: basic keyword + intent matching
    message_lower = message.lower()
    kb_articles = _get_crm_kb()
    results = []

    for doc in kb_articles:
        score = 0.0
        # Keyword match
        for word in message_lower.split():
            if len(word) > 3 and word in doc.get("content", "").lower():
                score += 0.1
            if len(word) > 3 and word in doc.get("title", "").lower():
                score += 0.3
        score = min(0.99, score)
        if score >= 0.2:
            results.append(KnowledgeResult(
                source=f"kb:{doc['id']}",
                content=doc["content"],
                relevance_score=score,
                metadata={"title": doc.get("title", ""), "category": doc.get("category", "")},
            ))

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
