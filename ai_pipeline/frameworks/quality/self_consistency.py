"""Self-Consistency — Majority vote across multiple answers.

How it works:
  1. Generates multiple (3-5) independent answers to the same question
  2. Compares the answers for consistency
  3. Selects the answer that appears most often (majority vote)
  4. If all answers disagree, flags low confidence

What hallucination it catches:
  "Single-run hallucinations" — a single LLM run might hallucinate,
  but it's unlikely that 3-5 independent runs all hallucinate the
  same wrong answer. Consistency across runs = high confidence.

Activation:
  - Complex and critical complexity (expensive — multiple LLM calls)
  - Used in QUALITY_SCORER for verification, REASONING_ENGINE for key decisions
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.self_consistency")

# Number of independent samples to generate
NUM_SAMPLES = 3


class SelfConsistencyTechnique(BaseTechnique):
    """Self-Consistency: Majority vote across multiple answers.

    Generates multiple independent answers and picks the one that
    appears most often. Consistent answers = high confidence.
    Inconsistent answers = low confidence flag.
    """

    _min_complexity = "complex"

    @property
    def name(self) -> str:
        return "self_consistency"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.QUALITY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "QUALITY_SCORER",
            "REASONING_ENGINE",
            "RESPONSE_FORMATTER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 600  # High — multiple LLM calls (3 samples)

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Self-Consistency check.

        Generates multiple independent answers and checks for
        agreement via majority vote.
        """
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")

        if MOCK_MODE:
            chain, output, confidence, agreement_count = self._self_consistency_mock(intent, conclusion)
        else:
            chain, output, confidence, agreement_count = await self._self_consistency_llm(
                prompt, intent, conclusion,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["self_consistency"],
            metadata={
                "num_samples": NUM_SAMPLES,
                "agreement_count": agreement_count,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _self_consistency_mock(
        self,
        intent: str,
        conclusion: str,
    ) -> tuple[list[str], str, float, int]:
        """Mock Self-Consistency check for testing (no LLM calls)."""
        chain = []

        # Simulate generating 3 independent answers
        answers_map = {
            "refund_request": [
                "Customer is eligible for a full refund.",
                "Full refund should be processed for duplicate charge.",
                "Customer qualifies for refund per 30-day policy.",
            ],
            "order_status": [
                "Order status can be provided from CRM data.",
                "Tracking information is available for this order.",
                "Order is in transit and can be tracked.",
            ],
            "cancellation": [
                "Order can be cancelled within 24 hours.",
                "Cancellation is possible before shipment.",
                "Order cancellation is eligible per policy.",
            ],
        }

        answers = answers_map.get(intent, [
            f"Issue can be resolved for {intent}.",
            f"Standard procedure applies for {intent}.",
            f"Resolution available for {intent} request.",
        ])

        chain.append(f"Self-Consistency: Generated {NUM_SAMPLES} independent answers")
        for i, ans in enumerate(answers, 1):
            chain.append(f"  Sample {i}: {ans}")

        # Check agreement — in mock mode, all 3 agree on the general direction
        # Simulate different levels of agreement based on intent
        agreement_count = NUM_SAMPLES  # All agree in mock mode

        chain.append(f"Self-Consistency: {agreement_count}/{NUM_SAMPLES} answers agree")

        if agreement_count >= 2:
            chain.append("Self-Consistency: Majority agreement reached — high confidence")
            output = f"Self-Consistency: Majority ({agreement_count}/{NUM_SAMPLES}) agrees on resolution for '{intent}'"
            confidence = 0.92
        else:
            chain.append("Self-Consistency: No majority agreement — low confidence")
            output = f"Self-Consistency: Disagreement detected ({agreement_count}/{NUM_SAMPLES}) for '{intent}'"
            confidence = 0.40

        return chain, output, confidence, agreement_count

    async def _self_consistency_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, int]:
        """Real LLM-based Self-Consistency check."""
        system_instructions = (
            "You are a customer support reasoning engine.\n\n"
            f"Intent: {intent}\n"
            f"Current conclusion: {conclusion or 'None yet'}\n\n"
            "Provide your independent assessment of this situation.\n"
            "Be concise — one sentence with your conclusion."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)
        answers = []

        try:
            # Generate multiple independent samples
            for i in range(NUM_SAMPLES):
                text = await ainvoke_llm(
                    safe_prompt,
                    node_name=f"FRAMEWORKBRAIN_SC_{i+1}",
                    ticket_id=ticket_id,
                    variant=variant,
                )
                answers.append(text.strip())

            # Check for agreement (simple keyword overlap)
            chain = [f"Self-Consistency: Generated {len(answers)} independent answers"]

            # Count how many answers share key terms
            all_words = []
            for ans in answers:
                all_words.extend(ans.lower().split())

            # Simple majority: count answers that share 50%+ keywords with the first
            if answers:
                first_words = set(answers[0].lower().split())
                agreement_count = 0
                for ans in answers:
                    ans_words = set(ans.lower().split())
                    overlap = len(first_words & ans_words) / max(len(first_words), 1)
                    if overlap >= 0.5:
                        agreement_count += 1
            else:
                agreement_count = 0

            chain.append(f"Self-Consistency: {agreement_count}/{NUM_SAMPLES} answers agree")

            if agreement_count >= 2:
                output = f"Self-Consistency: Majority agreement for '{intent}'"
                confidence = 0.88
            else:
                output = f"Self-Consistency: Low agreement for '{intent}' — needs review"
                confidence = 0.45

            return chain, output, confidence, agreement_count

        except Exception as exc:
            logger.warning("Self-Consistency LLM check failed: %s — using fallback", exc)
            return (
                ["Self-Consistency: LLM check failed, cannot verify consistency"],
                "Self-Consistency: Cannot verify — LLM error",
                0.30,
                0,
            )
