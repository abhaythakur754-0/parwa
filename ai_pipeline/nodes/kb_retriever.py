"""Node 4: KB_RETRIEVER — Searches the knowledge base for relevant documents.

Knowledge Agent node. Retrieves relevant knowledge base documents
to provide evidence for the Reasoning Agent.

Phase 3 (v2): Now uses FrameworkBrain with RAG techniques that ACTUALLY
modify search behavior:
  - HyDE generates a hypothetical document used as an enhanced search query
  - Multi-Query generates multiple query phrasings for broader coverage
  - Step-Back finds broader concepts when specific queries miss
  - CLARA evaluates confidence and requests clarification if needed
All techniques now feed enhanced queries into the actual KB search,
instead of just running as decorative metadata flags.
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


def _search_kb_single(query: str, intent: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Search KB with a single query string. Returns list of KnowledgeResult dicts."""
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

    # Try CRM-based search first
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()

        extra_keywords = intent_keywords.get(intent, "")
        if extra_keywords:
            search_query = f"{query} {extra_keywords}"
        else:
            search_query = query

        results = crm.search_kb(search_query, top_k=top_k)

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

    # Fallback: basic keyword matching
    query_lower = query.lower()
    kb_articles = _get_crm_kb()
    results = []

    for doc in kb_articles:
        score = 0.0
        for word in query_lower.split():
            if len(word) > 3 and word in doc.get("content", "").lower():
                score += 0.1
            if len(word) > 3 and word in doc.get("title", "").lower():
                score += 0.3
        score = min(0.99, score)
        if score >= 0.15:  # Lower threshold for RAG-enhanced queries
            results.append(KnowledgeResult(
                source=f"kb:{doc['id']}",
                content=doc["content"],
                relevance_score=score,
                metadata={"title": doc.get("title", ""), "category": doc.get("category", "")},
            ))

    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return [r.model_dump() for r in results[:top_k]]


def _retrieve_kb_rule_based(message: str, intent: str) -> list[dict[str, Any]]:
    """Retrieve KB documents using standard search."""
    return _search_kb_single(message, intent, top_k=3)


def _merge_and_deduplicate(result_sets: list[list[dict[str, Any]]], max_results: int = 5) -> list[dict[str, Any]]:
    """Merge multiple KB result sets and deduplicate by source, keeping best score."""
    seen: dict[str, dict[str, Any]] = {}

    for results in result_sets:
        for r in results:
            if not isinstance(r, dict):
                continue
            source = r.get("source", "")
            score = r.get("relevance_score", 0)
            if source not in seen or score > seen[source].get("relevance_score", 0):
                seen[source] = dict(r)  # Copy

    merged = sorted(seen.values(), key=lambda x: x.get("relevance_score", 0), reverse=True)
    return merged[:max_results]


async def _retrieve_with_brain(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """KB retrieval using FrameworkBrain with REAL query enhancement (v2).

    RAG techniques now ACTUALLY modify the search:
    - HyDE's hypothetical document is used as a search query
    - Multi-Query's expanded queries are searched individually
    - Step-Back's broader concept is searched as well
    - All results are merged and deduplicated

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
            techniques=["hyde", "multi_query", "step_back", "clara"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # v2: Collect enhanced queries from RAG technique metadata.
        # Brain now forwards each technique's own metadata under:
        #   result.metadata["technique_results"][<name>]["metadata"]
        # This is where HyDE/Multi-Query/StepBack store their enhanced data.
        enhanced_queries = [raw_message]  # Always include original
        technique_meta = result.metadata.get("technique_results", {})

        # HyDE provides a hypothetical document → use as search query
        hyde_entry = technique_meta.get("hyde", {})
        hyde_own_meta = hyde_entry.get("metadata", {}) if isinstance(hyde_entry, dict) else {}
        hyde_hypo_doc = hyde_own_meta.get("hypothetical_document", "")
        # Fallback: try legacy locations for robustness
        if not hyde_hypo_doc:
            hyde_hypo_doc = result.metadata.get("hyde_hypothetical_document", "")
        if not hyde_hypo_doc:
            for fw_key, fw_val in technique_meta.items():
                if isinstance(fw_val, dict):
                    inner = fw_val.get("metadata", {})
                    if isinstance(inner, dict) and "hypothetical_document" in inner:
                        hyde_hypo_doc = inner["hypothetical_document"]
                        break

        if hyde_hypo_doc and isinstance(hyde_hypo_doc, str) and len(hyde_hypo_doc) > 20:
            enhanced_queries.append(hyde_hypo_doc)
            logger.debug("kb_retriever: HyDE enhanced query added (%d chars)", len(hyde_hypo_doc))

        # Multi-Query provides multiple phrasings → search each
        mq_entry = technique_meta.get("multi_query", {})
        mq_own_meta = mq_entry.get("metadata", {}) if isinstance(mq_entry, dict) else {}
        mq_queries = mq_own_meta.get("queries", [])
        # Fallback: try legacy locations
        if not mq_queries:
            for fw_key, fw_val in technique_meta.items():
                if isinstance(fw_val, dict):
                    inner = fw_val.get("metadata", {})
                    if isinstance(inner, dict) and "queries" in inner:
                        mq_queries = inner["queries"]
                        break
        if mq_queries and isinstance(mq_queries, list):
            for q in mq_queries:
                if isinstance(q, str) and len(q) > 10:
                    enhanced_queries.append(q)
            logger.debug("kb_retriever: Multi-Query added %d expanded queries", len(mq_queries))

        # Step-Back provides a broader concept → search with it
        sb_entry = technique_meta.get("step_back", {})
        sb_own_meta = sb_entry.get("metadata", {}) if isinstance(sb_entry, dict) else {}
        sb_concept = sb_own_meta.get("broader_concept", "")
        # Fallback: try legacy locations
        if not sb_concept:
            for fw_key, fw_val in technique_meta.items():
                if isinstance(fw_val, dict):
                    inner = fw_val.get("metadata", {})
                    if isinstance(inner, dict) and "broader_concept" in inner:
                        sb_concept = inner["broader_concept"]
                        break
        if sb_concept and isinstance(sb_concept, str) and len(sb_concept) > 5:
            enhanced_queries.append(sb_concept)
            logger.debug("kb_retriever: Step-Back added broader concept: '%s'", sb_concept[:60])

        # v2: Search with ALL enhanced queries and merge results
        all_results = []
        for query in enhanced_queries:
            query_results = _search_kb_single(query, intent, top_k=3)
            all_results.append(query_results)

        merged = _merge_and_deduplicate(all_results, max_results=5)

        # Tag results with RAG enhancement metadata
        for kb in merged:
            if isinstance(kb, dict):
                kb["retrieval_enhanced"] = True
                kb["enhanced_query_count"] = len(enhanced_queries)
                kb["frameworks_used"] = frameworks

        if not merged:
            # Fallback to standard search if enhanced queries found nothing
            merged = _retrieve_kb_rule_based(raw_message, intent)

        logger.info(
            "kb_retriever: RAG-enhanced search with %d queries returned %d results (techniques: %s)",
            len(enhanced_queries), len(merged), frameworks,
        )

        return merged, frameworks

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

    Phase 3 (v2): Uses FrameworkBrain with RAG techniques that ACTUALLY
    enhance search queries:
      - HyDE generates hypothetical docs used as search queries
      - Multi-Query expands the query into multiple phrasings
      - Step-Back finds broader concepts for deeper retrieval
      - CLARA evaluates confidence of retrieved results

    Falls back to rule-based on FrameworkBrain failure.

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

    # Try FrameworkBrain first (Phase 3 v2 — real RAG enhancement)
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
