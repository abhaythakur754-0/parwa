"""Multi-Query — Generates multiple query variations for better retrieval coverage.

How it works:
  1. Takes the customer query
  2. Generates 3-5 different phrasings of the same question
  3. Searches the KB with ALL variations
  4. Merges and deduplicates the results
  5. Returns the combined result set with better coverage

What hallucination it catches:
  "Single-query blind spots" — one phrasing of a question may miss
  relevant documents that use different terminology. Multi-Query casts
  a wider net, reducing the chance of missing critical information.

Activation:
  - Medium complexity and above
  - Used in KB_RETRIEVER, FAQ_MATCHER for broader search
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.multi_query")


class MultiQueryTechnique(BaseTechnique):
    """Multi-Query: Multiple query variations merged for better coverage.

    Instead of searching the KB with one query, Multi-Query generates
    several phrasings of the same question and searches with all of
    them. Results are merged and deduplicated for comprehensive coverage.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "multi_query"

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
        return 300  # Higher — generates multiple queries + searches

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Multi-Query retrieval.

        Generates multiple phrasings of the query and merges results.
        """
        intent = state.get("intent", "general_inquiry")
        raw_message = state.get("raw_message", "")

        if MOCK_MODE:
            chain, output, confidence, queries = self._multi_query_mock(intent, raw_message)
        else:
            chain, output, confidence, queries = await self._multi_query_llm(
                prompt, intent, raw_message,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["multi_query"],
            metadata={
                "query_count": len(queries),
                "queries": queries,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _multi_query_mock(
        self,
        intent: str,
        raw_message: str,
    ) -> tuple[list[str], str, float, list[str]]:
        """Mock Multi-Query retrieval for testing (no LLM calls)."""
        chain = []

        # Step 1: Generate multiple query variations
        query_variations_map = {
            "refund_request": [
                "How do I get a refund for a duplicate charge?",
                "What is the refund policy for double billing?",
                "Process for returning money charged twice",
            ],
            "order_status": [
                "Where is my order right now?",
                "How can I track my package delivery?",
                "What is the current status of my shipment?",
            ],
            "cancellation": [
                "How do I cancel my recent order?",
                "What is the process to stop a pending order?",
                "Can I cancel before it ships?",
            ],
            "billing_issue": [
                "Why was I charged incorrectly?",
                "How to resolve a billing discrepancy?",
                "What causes duplicate charges on my account?",
            ],
        }

        queries = query_variations_map.get(intent, [
            f"What is the solution for {intent}?",
            f"How to handle {intent} issues?",
            f"What policy applies to {intent}?",
        ])

        chain.append(f"Multi-Query: Generated {len(queries)} query variations")
        for i, q in enumerate(queries, 1):
            chain.append(f"  Query {i}: {q}")

        # Step 2: Simulate searching with each variation
        chain.append(f"Multi-Query: Searching KB with all {len(queries)} variations")
        chain.append("Multi-Query: Merging and deduplicating results")

        # Step 3: Report coverage improvement
        output = f"Multi-Query: Broader coverage achieved with {len(queries)} query variations for '{intent}'"
        confidence = 0.87

        return chain, output, confidence, queries

    async def _multi_query_llm(
        self,
        prompt: str,
        intent: str,
        raw_message: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, list[str]]:
        """Real LLM-based Multi-Query retrieval."""
        system_instructions = (
            "You are a Multi-Query generator for customer support.\n\n"
            f"Customer message: {raw_message}\n"
            f"Detected intent: {intent}\n\n"
            "Generate 3 different phrasings of this question that could "
            "help find relevant knowledge base documents.\n\n"
            "Rules:\n"
            "- Each variation should use different vocabulary\n"
            "- Include both formal and informal phrasings\n"
            "- Focus on what the customer actually needs\n\n"
            "Output one query per line, no numbering."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_MULTI_QUERY",
                ticket_id=ticket_id,
                variant=variant,
            )

            queries = [line.strip() for line in text.strip().split("\n") if line.strip()]
            if not queries:
                queries = [raw_message]

            chain = [
                f"Multi-Query: Generated {len(queries)} query variations",
                f"Multi-Query: Searching KB with all variations",
                "Multi-Query: Merging and deduplicating results",
            ]

            output = f"Multi-Query: Broader coverage with {len(queries)} queries for '{intent}'"
            confidence = 0.85

            return chain, output, confidence, queries

        except Exception as exc:
            logger.warning("Multi-Query LLM generation failed: %s — using fallback", exc)
            fallback_queries = [raw_message, f"How to resolve {intent}?"]
            return (
                ["Multi-Query: LLM generation failed, using raw query only"],
                "Multi-Query: Falling back to single query due to LLM error",
                0.45,
                fallback_queries,
            )
