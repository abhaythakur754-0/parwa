"""Chain of Thought (CoT) — Forces step-by-step reasoning before conclusion.

How it works:
  - Presents the problem and evidence to the LLM
  - Asks for explicit intermediate reasoning steps
  - Extracts each step as a separate chain entry
  - Extracts the final conclusion

What hallucination it catches:
  "Confident wrong answers" — the model can't skip steps and land on
  a hallucination. Each step must be logically grounded.

Activation:
  - Activates on ALL complexity levels (even simple tickets get CoT)
  - This is the baseline technique — always runs first
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.cot")


class ChainOfThoughtTechnique(BaseTechnique):
    """Chain of Thought reasoning technique.

    Forces step-by-step reasoning with explicit intermediate steps
    before reaching a conclusion. This is the baseline technique that
    runs on every ticket — even simple ones.
    """

    _min_complexity = "simple"  # Activates on ALL complexity levels

    @property
    def name(self) -> str:
        return "chain_of_thought"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "INTENT_CLASSIFIER",
            "FAQ_MATCHER",
            "KB_RETRIEVER",
            "INTEGRATION_LOOKUP",
            "ACTION_PLANNER",
            "ACTION_VERIFIER",
            "PROACTIVE_CHECKER",
            "PREDICTION_ENGINE",
            "PII_COMPLIANCE_GUARD",
            "RESPONSE_FORMATTER",
            "SENTIMENT_ANALYZER",
            "CONTEXT_MANAGER",
            "ESCALATION_DECISION",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 150  # Moderate — one LLM call with step-by-step reasoning

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Chain of Thought reasoning.

        Args:
            prompt: What to reason about.
            state: Current ticket state.
            ticket_id: Ticket ID for tracking.
            variant: Variant for budget allocation.

        Returns:
            TechniqueResult with chain of reasoning steps and conclusion.
        """
        intent = state.get("intent", "general_inquiry")
        faq_match = state.get("faq_match")
        kb_results = state.get("kb_results", [])
        integration_data = state.get("integration_data", {})

        # Build evidence context
        evidence_parts = []
        if faq_match and isinstance(faq_match, dict):
            score = faq_match.get("relevance_score", 0)
            if score > 0.3:
                evidence_parts.append(f"FAQ match (relevance {score:.0%}): {faq_match.get('content', '')}")
        if kb_results and isinstance(kb_results, list):
            for kb in kb_results[:2]:
                if isinstance(kb, dict):
                    evidence_parts.append(f"KB evidence: {kb.get('content', '')[:100]}")
        if integration_data and isinstance(integration_data, dict):
            evidence_parts.append(f"CRM data: {integration_data}")

        evidence = "\n".join(evidence_parts) if evidence_parts else "No specific evidence available."

        system_instructions = (
            "You are a step-by-step reasoning engine for customer support.\n"
            "Think through this problem one step at a time.\n\n"
            f"Customer intent: {intent}\n"
            f"Evidence:\n{evidence}\n\n"
            "Rules:\n"
            "- Each step must reference specific evidence or logic\n"
            "- Do not skip steps\n"
            "- End with: Conclusion: <your conclusion>\n"
            "- If evidence is insufficient, say so explicitly"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        if MOCK_MODE:
            chain, conclusion, confidence = self._reason_mock(intent, evidence)
        else:
            chain, conclusion, confidence = await self._reason_llm(
                safe_prompt, ticket_id=ticket_id, variant=variant
            )

        return TechniqueResult(
            output=conclusion,
            chain=chain,
            confidence=confidence,
            frameworks_used=["chain_of_thought"],
            metadata={"evidence_count": len(evidence_parts), "intent": intent},
            token_estimate=self.token_cost_estimate,
        )

    def _reason_mock(
        self, intent: str, evidence: str
    ) -> tuple[list[str], str, float]:
        """Mock CoT reasoning for testing (no LLM calls)."""
        chain = [
            f"Step 1: Analyzing customer intent — {intent}",
            f"Step 2: Reviewing available evidence",
            f"Step 3: Applying policy and logic",
        ]

        if intent == "refund_request":
            chain.append("Step 4: Duplicate charge confirmed in evidence")
            chain.append("Step 5: Policy allows refund within 30 days")
            conclusion = "Customer is eligible for a full refund. Evidence supports the claim."
            confidence = 0.95
        elif intent == "order_status":
            chain.append("Step 4: Order information available in CRM data")
            conclusion = "Order status can be provided from CRM data."
            confidence = 0.90
        elif intent == "cancellation":
            chain.append("Step 4: Cancellation request reviewed against policy")
            conclusion = "Cancellation request can be processed per policy."
            confidence = 0.88
        elif intent == "billing_issue":
            chain.append("Step 4: Billing discrepancy identified in charges")
            conclusion = "Billing discrepancy identified. Corrective action needed."
            confidence = 0.85
        else:
            chain.append("Step 4: General analysis based on available information")
            conclusion = "Issue analyzed. Appropriate response can be formulated."
            confidence = 0.70

        chain.append(f"Conclusion: {conclusion}")
        return chain, conclusion, confidence

    async def _reason_llm(
        self, prompt: str, *, ticket_id: str = "", variant: str = "parwa"
    ) -> tuple[list[str], str, float]:
        """Real LLM-based CoT reasoning."""
        try:
            text = await ainvoke_llm(
                prompt,
                node_name="FRAMEWORKBRAIN_COT",
                ticket_id=ticket_id,
                variant=variant,
            )
            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]

            conclusion = ""
            for line in chain:
                if line.lower().startswith("conclusion:"):
                    conclusion = line[len("conclusion:"):].strip()
                    break

            if not conclusion and chain:
                conclusion = chain[-1]

            confidence = 0.80  # Default confidence for LLM output
            if "insufficient" in conclusion.lower() or "uncertain" in conclusion.lower():
                confidence = 0.40

            return chain, conclusion, confidence

        except Exception as exc:
            logger.warning("CoT LLM reasoning failed: %s — using fallback", exc)
            return [f"Step 1: LLM reasoning failed"], "Analysis incomplete due to LLM error", 0.20
