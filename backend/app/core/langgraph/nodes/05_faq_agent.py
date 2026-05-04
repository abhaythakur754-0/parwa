"""
FAQ Agent Node — Group 4 Domain Agent (FAQ / General queries)

Specialized domain agent for handling FAQ, general inquiries,
greetings, and knowledge-base lookups. Extends BaseDomainAgent
with RAG retrieval capabilities for accurate, sourced responses.

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type,
          rag_documents_retrieved, rag_reranked, kb_documents_used

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import importlib

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_faq_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# FAQ Agent Implementation
# ──────────────────────────────────────────────────────────────


class FAQAgent(BaseDomainAgent):
    """
    FAQ Domain Agent — handles general queries, FAQs, greetings,
    and knowledge-base lookups.

    Specializes the base domain agent with:
      - FAQ-oriented system prompt
      - RAG retrieval from knowledge base
      - Document reranking for relevance
      - Source attribution in responses

    This agent is the default/fallback for all tiers and handles
    the most common customer interactions.
    """

    agent_name: str = "faq"

    system_prompt: str = (
        "You are a knowledgeable and friendly FAQ support agent. "
        "Your goal is to provide accurate, helpful answers based on "
        "the available knowledge base documents. Always cite your sources "
        "when using retrieved documents. If you cannot find a definitive "
        "answer, honestly say so and offer to escalate to a specialist. "
        "Maintain a warm, professional tone appropriate to the customer's "
        "sentiment. Keep responses concise and actionable."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "general_inquiry",
            "product_information",
            "account_management",
            "shipping_delivery",
            "returns_policy",
            "pricing_plans",
        ],
        "max_rag_documents": 5,
        "min_relevance_score": 0.6,
        "reranking_enabled": True,
        "fallback_to_general": True,
    }

    def _retrieve_rag_documents(
        self,
        message: str,
        tenant_id: str,
        variant_tier: str,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents from the RAG knowledge base.

        Uses the production rag_retrieval module when available.
        Falls back to empty results with a warning.

        Args:
            message: The PII-redacted message to search against.
            tenant_id: Tenant identifier (BC-001).
            variant_tier: Variant tier string.

        Returns:
            Dict with 'documents', 'reranked', 'doc_ids'.
        """
        try:
            from app.core.rag_retrieval import retrieve_documents  # type: ignore[import-untyped]

            max_docs = self.domain_knowledge.get("max_rag_documents", 5)
            min_score = self.domain_knowledge.get("min_relevance_score", 0.6)

            result = retrieve_documents(
                query=message,
                tenant_id=tenant_id,
                max_documents=max_docs,
                min_relevance_score=min_score,
                rerank=self.domain_knowledge.get("reranking_enabled", True),
            )

            documents = result.get("documents", [])
            reranked = result.get("reranked", False)
            doc_ids = [doc.get("doc_id", "") for doc in documents if doc.get("doc_id")]

            logger.info(
                "rag_retrieval_success",
                tenant_id=tenant_id,
                documents_retrieved=len(documents),
                reranked=reranked,
                doc_ids=doc_ids,
            )

            return {
                "documents": documents,
                "reranked": reranked,
                "doc_ids": doc_ids,
            }

        except ImportError:
            logger.warning(
                "rag_retrieval_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as rag_exc:
            logger.warning(
                "rag_retrieval_error",
                tenant_id=tenant_id,
                error=str(rag_exc),
            )

        # Fallback: no documents retrieved
        return {
            "documents": [],
            "reranked": False,
            "doc_ids": [],
        }

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add RAG-specific fields to the state update.

        Extends the base state update with:
          - rag_documents_retrieved: List of retrieved RAG documents
          - rag_reranked: Whether documents were reranked
          - kb_documents_used: List of KB document IDs used

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with additional RAG state fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        variant_tier = state.get("variant_tier", "mini")
        message = state.get("pii_redacted_message", "") or state.get("message", "")

        # Retrieve RAG documents for this query
        rag_result = self._retrieve_rag_documents(
            message=message,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        return {
            "rag_documents_retrieved": rag_result["documents"],
            "rag_reranked": rag_result["reranked"],
            "kb_documents_used": rag_result["doc_ids"],
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def faq_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    FAQ Agent Node — LangGraph agent node.

    Handles general inquiries, FAQ lookups, and knowledge-base
    queries. Uses RAG retrieval to find relevant documents and
    generates sourced responses.

    This is the entry point function registered in the LangGraph
    graph. It creates an FAQAgent instance and delegates execution.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        plus RAG retrieval fields.
    """
    tenant_id = state.get("tenant_id", "unknown")

    logger.info(
        "faq_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
    )

    try:
        agent = FAQAgent()
        return agent.run(state)
    except Exception as exc:
        logger.error(
            "faq_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": "",
            "agent_confidence": 0.0,
            "proposed_action": "respond",
            "action_type": "informational",
            "agent_reasoning": f"FAQ agent fatal error: {exc}",
            "agent_type": "faq",
            "rag_documents_retrieved": [],
            "rag_reranked": False,
            "kb_documents_used": [],
            "errors": [f"FAQ agent fatal error: {exc}"],
        }
