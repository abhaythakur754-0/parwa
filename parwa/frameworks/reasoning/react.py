"""ReAct (Think-Act-Observe) — Reasoning with real data verification.

How it works:
  1. THINK: Generate a hypothesis about the solution
  2. ACT: Query real data (CRM, KB, FAQ) to verify
  3. OBSERVE: Compare the hypothesis against actual data
  4. If observation contradicts hypothesis → re-think with new evidence

What hallucination it catches:
  "Fabricated facts" — the observe step compares the answer against
  actual CRM/KB data. If the LLM made something up, the observation
  will catch the mismatch.

Activation:
  - Medium complexity and above (not on simple tickets)
  - Used in REASONING_ENGINE alongside CoT
"""

from __future__ import annotations

import json
import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.react")


class ReactTechnique(BaseTechnique):
    """ReAct (Think-Act-Observe) reasoning technique.

    Adds a verification layer on top of reasoning by checking the
    conclusion against real data sources. If the data contradicts
    the conclusion, the technique flags it.
    """

    _min_complexity = "medium"  # Only activates on medium+

    @property
    def name(self) -> str:
        return "react"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_PLANNER",
            "ACTION_EXECUTOR",
            "ACTION_VERIFIER",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 300  # Higher than CoT — involves observation step

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute ReAct (Think-Act-Observe) reasoning.

        The technique:
        1. Takes the existing reasoning conclusion from state
        2. Compares it against actual data (CRM, KB, FAQ)
        3. Flags contradictions or confirms alignment
        4. Returns a verified or corrected conclusion
        """
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")
        faq_match = state.get("faq_match")
        kb_results = state.get("kb_results", [])
        integration_data = state.get("integration_data", {})

        if MOCK_MODE:
            chain, output, confidence, verified = self._react_mock(
                intent, conclusion, faq_match, kb_results, integration_data
            )
        else:
            chain, output, confidence, verified = await self._react_llm(
                prompt, intent, conclusion, faq_match, kb_results,
                integration_data, ticket_id=ticket_id, variant=variant
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["react"],
            metadata={
                "verified": verified,
                "intent": intent,
                "had_conclusion": bool(conclusion),
            },
            token_estimate=self.token_cost_estimate,
        )

    def _react_mock(
        self,
        intent: str,
        conclusion: str,
        faq_match: dict | None,
        kb_results: list[dict],
        integration_data: dict,
    ) -> tuple[list[str], str, float, bool]:
        """Mock ReAct for testing."""
        chain = []
        verified = True

        # Step 1: THINK — What's the hypothesis?
        if conclusion:
            chain.append(f"THINK: Existing conclusion — {conclusion}")
        else:
            chain.append(f"THINK: No prior conclusion. Hypothesizing based on intent — {intent}")

        # Step 2: ACT — What data can we check?
        data_available = []
        if kb_results and isinstance(kb_results, list) and len(kb_results) > 0:
            data_available.append(f"KB: {len(kb_results)} document(s)")
        if integration_data and isinstance(integration_data, dict) and len(integration_data) > 0:
            data_available.append(f"CRM: {list(integration_data.keys())}")
        if faq_match and isinstance(faq_match, dict):
            data_available.append(f"FAQ: relevance={faq_match.get('relevance_score', 0):.2f}")

        chain.append(f"ACT: Checking data sources — {', '.join(data_available) if data_available else 'no data available'}")

        # Step 3: OBSERVE — Does data support the conclusion?
        if intent == "refund_request":
            has_charges = isinstance(integration_data, dict) and "charges" in integration_data
            if has_charges:
                chain.append("OBSERVE: CRM confirms duplicate charge data — conclusion ALIGNED")
                output = "ReAct verified: Customer refund eligibility confirmed by CRM charge data."
                confidence = 0.93
            else:
                chain.append("OBSERVE: No CRM charge data found — conclusion UNVERIFIED")
                output = "ReAct warning: Refund claim cannot be verified without CRM charge data."
                confidence = 0.50
                verified = False
        elif intent == "order_status":
            has_orders = isinstance(integration_data, dict) and "orders" in integration_data
            if has_orders:
                chain.append("OBSERVE: CRM has order data — conclusion ALIGNED")
                output = "ReAct verified: Order status available from CRM data."
                confidence = 0.90
            else:
                chain.append("OBSERVE: No order data in CRM — need to look up")
                output = "ReAct: Order status needs CRM lookup before confirming."
                confidence = 0.55
                verified = False
        else:
            chain.append("OBSERVE: Data is consistent with conclusion")
            output = f"ReAct verified: Conclusion consistent with available data for {intent}."
            confidence = 0.75

        return chain, output, confidence, verified

    async def _react_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        faq_match: dict | None,
        kb_results: list[dict],
        integration_data: dict,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, bool]:
        """Real LLM-based ReAct reasoning."""
        # Build evidence summary
        evidence_parts = []
        if faq_match and isinstance(faq_match, dict):
            evidence_parts.append(f"FAQ: {faq_match.get('content', '')}")
        if kb_results and isinstance(kb_results, list):
            for kb in kb_results[:2]:
                if isinstance(kb, dict):
                    evidence_parts.append(f"KB: {kb.get('content', '')[:100]}")
        if integration_data and isinstance(integration_data, dict):
            evidence_parts.append(f"CRM: {json.dumps(integration_data)[:200]}")

        evidence = "\n".join(evidence_parts) if evidence_parts else "No data available."

        system_instructions = (
            "You are a ReAct reasoning engine. Follow the Think-Act-Observe pattern.\n\n"
            f"Intent: {intent}\n"
            f"Current conclusion: {conclusion or 'None yet'}\n"
            f"Available data:\n{evidence}\n\n"
            "Steps:\n"
            "1. THINK: State your hypothesis\n"
            "2. ACT: Check the data above for verification\n"
            "3. OBSERVE: Does the data support or contradict the hypothesis?\n\n"
            "Format each step as: THINK: / ACT: / OBSERVE:\n"
            "If the data CONTRADICTS the conclusion, say OBSERVE: CONTRADICTION\n"
            "If the data SUPPORTS the conclusion, say OBSERVE: ALIGNED"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_REACT",
                ticket_id=ticket_id,
                variant=variant,
            )
            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]

            verified = not any("contradiction" in line.lower() for line in chain)
            output = chain[-1] if chain else "ReAct analysis complete"

            confidence = 0.85 if verified else 0.40

            return chain, output, confidence, verified

        except Exception as exc:
            logger.warning("ReAct LLM reasoning failed: %s — using fallback", exc)
            return (
                ["THINK: LLM call failed", "ACT: Cannot verify", "OBSERVE: UNVERIFIED"],
                "ReAct analysis incomplete due to LLM error",
                0.20,
                False,
            )
