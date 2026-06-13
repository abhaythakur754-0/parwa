"""Node 4: KB_RETRIEVER — Searches the knowledge base for relevant documents.

Knowledge Agent node. Retrieves relevant knowledge base documents
to provide evidence for the Reasoning Agent.

Per PARWA Docs v6.0: The Knowledge Base uses RAG (Retrieval Augmented
Generation) with pgvector for semantic search. AI searches this knowledge
when reasoning about tickets.

Uses the KnowledgeBridge to connect to:
1. Real backend KnowledgeService (when available)
2. In-memory product docs (from kb_product_docs.md)
3. Fake CRM KB (last resort for legacy compatibility)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import KnowledgeResult
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.kb_retriever")


async def _retrieve_from_bridge(message: str, intent: str, company_id: str = "comp-test-001") -> list[dict[str, Any]]:
    """Retrieve KB documents using the KnowledgeBridge.

    This uses the real KnowledgeService when available, falls back to
    product docs, and finally to Fake CRM data.
    """
    try:
        from parwa.knowledge_bridge import get_knowledge_bridge
        bridge = get_knowledge_bridge(company_id=company_id)

        # Enhance search query with intent-related keywords for better matching
        intent_keywords = {
            "refund_request": "duplicate charge refund payment policy",
            "billing_issue": "payment billing charge invoice subscription",
            "cancellation": "cancel cancellation order policy",
            "order_status": "shipping order tracking delivery status",
            "technical_support": "error bug technical integration troubleshooting",
            "account_modification": "account modify update change billing address",
            "complaint": "complaint issue problem defective quality",
            "escalation": "escalation manager supervisor legal",
            "faq_question": "policy FAQ question help knowledge base",
        }

        search_query = message
        extra_keywords = intent_keywords.get(intent, "")
        if extra_keywords:
            search_query = f"{message} {extra_keywords}"

        results = await bridge.search(search_query, top_k=5)

        if not results and intent in intent_keywords:
            results = await bridge.search(intent_keywords[intent], top_k=3)

        if results:
            return [
                KnowledgeResult(
                    source=f"kb:{r.get('id', 'unknown')}",
                    content=r.get("content", ""),
                    relevance_score=r.get("relevance_score", 0.5),
                    metadata={
                        "title": r.get("title", ""),
                        "category": r.get("category", ""),
                    },
                ).model_dump()
                for r in results
            ]
    except Exception as exc:
        logger.warning("kb_retriever: KnowledgeBridge search failed: %s", exc)

    return []


def _retrieve_kb_rule_based(message: str, intent: str) -> list[dict[str, Any]]:
    """Fallback: Retrieve KB documents using Fake CRM search (synchronous)."""
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()

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

        search_query = message
        extra_keywords = intent_keywords.get(intent, "")
        if extra_keywords:
            search_query = f"{message} {extra_keywords}"

        results = crm.search_kb(search_query, top_k=3)

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

    # Last resort: basic keyword matching
    message_lower = message.lower()
    kb_articles = [
        {"id": "refund_policy", "title": "Refund Policy", "content": "Full refunds available within 30 days for duplicate charges. All refunds require manager approval per Control System rules.", "category": "billing"},
        {"id": "shipping_policy", "title": "Shipping Policy", "content": "Standard shipping: 3-5 business days. Express: 1-2 business days. Tracking provided for all shipments.", "category": "shipping"},
        {"id": "cancellation_policy", "title": "Cancellation Policy", "content": "Orders can be cancelled before shipment. After shipment, return policy applies. All cancellations require approval.", "category": "orders"},
        {"id": "variant_system", "title": "Variant System", "content": "Mini PARWA collects and verifies but never executes financial actions. PARWA recommends with reasoning. PARWA High provides strategic analysis and can execute after approval.", "category": "product"},
        {"id": "account_changes", "title": "Account Changes", "content": "Account modifications (billing, security, email, password) always require approval on all variants per Control System rules.", "category": "account"},
    ]

    results = []
    for doc in kb_articles:
        score = 0.0
        for word in message_lower.split():
            if len(word) > 3 and word in doc["content"].lower():
                score += 0.15
            if len(word) > 3 and word in doc["title"].lower():
                score += 0.3
        score = min(0.99, score)
        if score >= 0.1:
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
    Falls back to KnowledgeBridge/rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    company_id = state.get("company_id", "comp-test-001")

    # Always try KnowledgeBridge first (real KB + product docs)
    bridge_results = await _retrieve_from_bridge(raw_message, intent, company_id)
    if bridge_results:
        # Try FrameworkBrain for enhanced retrieval
        try:
            from parwa.frameworks.brain import FrameworkBrain

            brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
            result = await brain.think(
                prompt=raw_message,
                techniques=["clara", "hyde", "multi_query", "step_back"],
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
            )

            # If brain produced metadata about improved retrieval, boost scores
            if result.confidence > 0.7 and result.frameworks_used:
                for kb in bridge_results:
                    if isinstance(kb, dict):
                        kb["retrieval_enhanced"] = True
                        kb["frameworks_used"] = result.frameworks_used

            return bridge_results, result.frameworks_used if result.frameworks_used else []

        except Exception as exc:
            logger.warning(
                "kb_retriever: FrameworkBrain failed (%s), using bridge results directly",
                exc,
            )
            return bridge_results, []

    # Fall back to rule-based if bridge returned nothing
    kb_results = _retrieve_kb_rule_based(raw_message, intent)
    return kb_results, []


@safe_node("KB_RETRIEVER", fallback={"kb_results": []})
async def kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """Search the knowledge base for relevant documents (async).

    Phase 3: Uses FrameworkBrain with RAG techniques (CLARA, HyDE,
    Multi-Query, Step-Back) for smarter retrieval.
    Uses KnowledgeBridge for real KB + product docs access.
    Falls back to rule-based on any failure.

    Reads: raw_message, intent, company_id
    Writes: kb_results
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")

    # Guard: ensure types
    if not isinstance(raw_message, str):
        raw_message = str(raw_message) if raw_message else ""
    if not isinstance(intent, str):
        intent = "general_inquiry"

    # Try KnowledgeBridge + FrameworkBrain
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
