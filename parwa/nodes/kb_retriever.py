"""Node 4: KB_RETRIEVER — Searches the knowledge base for relevant documents.

Knowledge Agent node. Retrieves relevant knowledge base documents
to provide evidence for the Reasoning Agent.
"""

from __future__ import annotations

from typing import Any

from parwa.state import KnowledgeResult
from parwa.utils.node_base import safe_node


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


@safe_node("KB_RETRIEVER", fallback={"kb_results": []})
async def kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """Search the knowledge base for relevant documents (async).

    Reads: raw_message, intent
    Writes: kb_results
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")

    results = _retrieve_kb_rule_based(raw_message, intent)

    return {"kb_results": results}
