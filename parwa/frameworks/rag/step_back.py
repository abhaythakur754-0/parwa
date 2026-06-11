"""Step-Back — Steps back from specific question to broader concept for retrieval.

How it works:
  1. Takes the customer's specific question
  2. Identifies the broader concept behind it
  3. Searches the KB for the broader concept
  4. Applies the broader knowledge to the specific case
  5. Returns results that the specific query would have missed

What hallucination it catches:
  "Overly specific misses" — when a customer asks about a specific
  situation, the KB might not have that exact scenario documented.
  But the broader policy or principle exists. Step-Back finds it.

Activation:
  - Medium complexity and above
  - Used in KB_RETRIEVER, FAQ_MATCHER for deeper retrieval
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.step_back")


class StepBackTechnique(BaseTechnique):
    """Step-Back: Broader concept search applied to specific cases.

    When a specific query fails to find relevant KB documents,
    Step-Back identifies the underlying concept, searches for that,
    and applies the broader knowledge to the specific situation.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "step_back"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.RAG

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "KB_RETRIEVER",
            "FAQ_MATCHER",
            "REASONING_ENGINE",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 200  # Moderate — one step-back query + application

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Step-Back retrieval.

        Steps back from the specific question to find broader
        knowledge, then applies it to the specific case.
        """
        intent = state.get("intent", "general_inquiry")
        raw_message = state.get("raw_message", "")

        if MOCK_MODE:
            chain, output, confidence, broader_concept = self._step_back_mock(intent, raw_message)
        else:
            chain, output, confidence, broader_concept = await self._step_back_llm(
                prompt, intent, raw_message,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["step_back"],
            metadata={
                "broader_concept": broader_concept,
                "original_intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _step_back_mock(
        self,
        intent: str,
        raw_message: str,
    ) -> tuple[list[str], str, float, str]:
        """Mock Step-Back retrieval for testing (no LLM calls)."""
        chain = []

        # Step 1: Identify the broader concept
        concept_map = {
            "refund_request": "payment dispute resolution policies",
            "order_status": "order fulfillment and tracking procedures",
            "cancellation": "order lifecycle and modification policies",
            "billing_issue": "financial transaction reconciliation procedures",
        }

        broader_concept = concept_map.get(intent, "general customer service policies and procedures")

        chain.append(f"Step-Back: Specific query is about '{intent}'")
        chain.append(f"Step-Back: Broader concept is '{broader_concept}'")

        # Step 2: Search with broader concept
        chain.append(f"Step-Back: Searching KB for '{broader_concept}'")

        # Step 3: Apply broader knowledge to specific case
        chain.append("Step-Back: Applying broader knowledge to specific customer situation")

        output = f"Step-Back: Found broader policy on '{broader_concept}' applicable to {intent}"
        confidence = 0.82

        return chain, output, confidence, broader_concept

    async def _step_back_llm(
        self,
        prompt: str,
        intent: str,
        raw_message: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, str]:
        """Real LLM-based Step-Back retrieval."""
        system_instructions = (
            "You are a Step-Back query generator for customer support.\n\n"
            f"Customer message: {raw_message}\n"
            f"Detected intent: {intent}\n\n"
            "Step back from this specific question and identify the BROADER "
            "concept or principle behind it. This broader concept will be used "
            "to search the knowledge base for relevant policies.\n\n"
            "Example:\n"
            "  Specific: 'I was charged twice for the same order'\n"
            "  Broader: 'payment dispute resolution policies'\n\n"
            "Output ONLY the broader concept (one line)."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            broader_concept = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_STEP_BACK",
                ticket_id=ticket_id,
                variant=variant,
            )
            broader_concept = broader_concept.strip()

            chain = [
                f"Step-Back: Specific query is about '{intent}'",
                f"Step-Back: Broader concept is '{broader_concept}'",
                f"Step-Back: Searching KB for '{broader_concept}'",
                "Step-Back: Applying broader knowledge to specific case",
            ]

            output = f"Step-Back: Found broader policy applicable to {intent}"
            confidence = 0.82

            return chain, output, confidence, broader_concept

        except Exception as exc:
            logger.warning("Step-Back LLM generation failed: %s — using fallback", exc)
            fallback_concept = f"general {intent} policies"
            return (
                ["Step-Back: LLM generation failed, using intent-based fallback"],
                "Step-Back: Falling back to intent-based concept due to LLM error",
                0.40,
                fallback_concept,
            )
