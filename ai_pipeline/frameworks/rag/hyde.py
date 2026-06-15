"""HyDE (Hypothetical Document Embedding) — RAG technique.

How it works:
  1. Takes the customer query
  2. Generates a hypothetical answer to the query
  3. Uses the hypothetical answer as a search query against the KB
  4. The hypothetical answer is semantically closer to actual KB docs
     than the original question, improving retrieval quality

What hallucination it catches:
  "Missed relevant documents" — standard keyword search misses docs
  that answer the question differently. HyDE's hypothetical answer
  bridges the vocabulary gap between questions and documents.

Activation:
  - Simple complexity and above (even simple tickets benefit)
  - Used in KB_RETRIEVER, FAQ_MATCHER, CONTEXT_MANAGER
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.hyde")


class HyDETechnique(BaseTechnique):
    """HyDE: Hypothetical Document Embedding for better KB matching.

    Instead of searching the KB with the customer's raw question,
    HyDE first generates a hypothetical answer, then searches using
    that answer. This bridges the vocabulary gap between questions
    and documents, improving retrieval quality significantly.
    """

    _min_complexity = "simple"

    @property
    def name(self) -> str:
        return "hyde"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.RAG

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "KB_RETRIEVER",
            "FAQ_MATCHER",
            "CONTEXT_MANAGER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 250  # Moderate — generates hypothetical doc + searches

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute HyDE retrieval.

        Generates a hypothetical answer to the customer's question,
        then uses it to find better KB matches.
        """
        intent = state.get("intent", "general_inquiry")
        raw_message = state.get("raw_message", "")

        if MOCK_MODE:
            chain, output, confidence, hypo_doc = self._hyde_mock(intent, raw_message)
        else:
            chain, output, confidence, hypo_doc = await self._hyde_llm(
                prompt, intent, raw_message,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["hyde"],
            metadata={
                "hypothetical_document": hypo_doc,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _hyde_mock(
        self,
        intent: str,
        raw_message: str,
    ) -> tuple[list[str], str, float, str]:
        """Mock HyDE retrieval for testing (no LLM calls)."""
        chain = []

        # Step 1: Generate hypothetical document
        chain.append(f"HyDE: Generating hypothetical answer for '{intent}'")

        hypothetical_docs = {
            "refund_request": "Refunds are processed for duplicate charges within 30 days. The customer should provide the transaction date and amount. Full refunds are issued to the original payment method within 5-7 business days.",
            "order_status": "Order status can be tracked using the order number. Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days. The tracking link is sent via email upon shipment.",
            "cancellation": "Orders can be cancelled within 24 hours of placement. After shipment, the customer must follow the return process. Cancellation is confirmed via email within 1 hour.",
            "billing_issue": "Billing discrepancies are investigated by comparing charges against the order history. If a duplicate charge is found, it is refunded automatically. The customer should report within 30 days.",
        }

        hypo_doc = hypothetical_docs.get(intent, "The customer's issue can be resolved by reviewing the relevant policy and taking appropriate action based on the evidence available in the system.")

        chain.append(f"HyDE: Hypothetical document generated ({len(hypo_doc)} chars)")

        # Step 2: Use hypothetical doc for search (simulated)
        chain.append("HyDE: Searching KB with hypothetical document as query")
        chain.append("HyDE: Hypothetical document matches are more semantically aligned than raw query")

        output = f"HyDE improved retrieval: Found relevant documents using hypothetical answer for '{intent}'"
        confidence = 0.88

        return chain, output, confidence, hypo_doc

    async def _hyde_llm(
        self,
        prompt: str,
        intent: str,
        raw_message: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, str]:
        """Real LLM-based HyDE retrieval."""
        system_instructions = (
            "You are a HyDE (Hypothetical Document Embedding) generator.\n\n"
            f"Customer question: {raw_message}\n"
            f"Detected intent: {intent}\n\n"
            "Generate a HYPOTHETICAL ANSWER to this question as if you were "
            "a knowledge base document. This hypothetical document will be used "
            "to search the real KB for semantically similar content.\n\n"
            "The hypothetical answer should:\n"
            "- Use vocabulary similar to KB documents (formal, policy-like)\n"
            "- Cover the likely solution or policy relevant to the question\n"
            "- Be 2-3 sentences long\n\n"
            "Output ONLY the hypothetical document text."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            hypo_doc = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_HYDE",
                ticket_id=ticket_id,
                variant=variant,
            )
            hypo_doc = hypo_doc.strip()

            chain = [
                f"HyDE: Generated hypothetical document ({len(hypo_doc)} chars)",
                f"HyDE: Searching KB with hypothetical document for better matches",
            ]

            output = f"HyDE improved retrieval using hypothetical document for '{intent}'"
            confidence = 0.85

            return chain, output, confidence, hypo_doc

        except Exception as exc:
            logger.warning("HyDE LLM generation failed: %s — using fallback", exc)
            fallback_doc = f"Standard policy applies for {intent} requests."
            return (
                ["HyDE: LLM generation failed, using raw query instead"],
                "HyDE: Falling back to standard query due to LLM error",
                0.40,
                fallback_doc,
            )
